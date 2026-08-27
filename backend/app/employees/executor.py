"""
EmployeeExecutor — runs a TaskStep using the assigned employee and selected model.
Handles the actual LLM call, context injection, retry on failure, and result extraction.
"""
import json
import re
import time
import structlog
from typing import List, Optional, Dict

from app.llm.gateway import ai_gateway
from app.llm.provider import LLMRequest, Message
from app.tasks.models import TaskStep, Employee, TaskAnalysis, StepStatus, EmployeeStatus
from app.router.model_router import DynamicModelRouter
from app.core.config import settings
from app.core.events import Event, EventType, event_bus
from app.workforce.role_catalog import role_playbook
from app.security.validators import PromptSanitizer

log = structlog.get_logger()

# Max LLM→tool→LLM round-trips per step (keeps token spend bounded)
MAX_MCP_TOOL_TURNS = 4

# Keywords in step objectives that suggest web research is needed
_RESEARCH_KEYWORDS = {
    "research", "search", "find", "gather", "collect", "look up", "investigate",
    "analyze", "trends", "market", "data", "statistics", "report", "survey",
    "competitor", "industry", "latest", "current", "recent", "news", "information",
}

# Strong fetch/download intent — web search runs even if the analyzer
# thought needs_research=false (LLMs often treat "find me X" as a how-to
# they already know, which silently skipped research).
_FETCH_RE = re.compile(
    r"\b(?:download|fetch|pdf|textbook|book|price|prices|latest|current|news|today|website|official)\b"
    r"|get me|look up|search for",
    re.IGNORECASE,
)
_DOWNLOAD_RE = re.compile(
    r"\bdownload\b|\bsave\b|get (?:me |us )?(?:the |a |an )?(?:file|pdf|book|copy)",
    re.IGNORECASE,
)
_STOPWORDS = {
    "the", "a", "an", "for", "and", "or", "of", "in", "to", "with", "please",
    "pls", "me", "my", "us", "it", "find", "get", "download", "save", "book",
    "pdf", "file", "copy", "official", "website",
}

EMPLOYEE_SYSTEM_TEMPLATE = """You are {role} — an AI specialist working on a project.

Your objective: {objective}

Your responsibilities:
{responsibilities}

Role playbook:
{playbook}

Requested tools: {tools}
{tool_note}

Work ethic:
- Be thorough and accurate
- Provide clear, structured output
- If you're uncertain, say so explicitly with your confidence level
- Focus ONLY on your assigned step — do not do work that belongs to others
{tool_conduct}
- End your response with: CONFIDENCE: [0.0-1.0] — your confidence in your output

Quality requirement for this step: {quality_requirement:.0%}
"""

# Security suffix appended to ALL system prompts
_SECURITY_SUFFIX = PromptSanitizer.injection_guard_system_suffix()


class EmployeeExecutor:
    """
    Executes a single task step using an employee + model.
    Handles context from prior steps, retry logic, and confidence extraction.
    """

    def __init__(self):
        self._router = DynamicModelRouter()

    async def execute(
        self,
        step: TaskStep,
        employee: Employee,
        analysis: TaskAnalysis,
        prior_results: Dict[str, str],  # step_id → result text
        attempt: int = 0,
    ) -> tuple[str, float, str]:
        """
        Execute a step. Returns (result_text, confidence, model_used).
        Before calling LLM, attempts web search for research-type steps.
        """
        # ── Live MCP tools (user-connected servers) ─────────────────────────────
        # Selected before the model so the router can pick a tool-calling model.
        mcp_tools = self._select_mcp_tools(step, analysis)
        tool_schemas = self._build_tool_schemas(mcp_tools) if mcp_tools else None

        model = self._router.select_model(
            employee, step, analysis, attempt=attempt,
            tools_required=bool(tool_schemas),
        )
        employee.current_model = model
        employee.status = EmployeeStatus.WORKING
        employee.current_task = step.objective

        # ── Web Search (free, pre-LLM) ─────────────────────────────────────
        web_context = ""
        web_search_result = None
        if self._needs_web_search(step, employee, analysis):
            web_search_result = await self._do_web_search(
                step=step,
                employee=employee,
                analysis=analysis,
            )
            if web_search_result and web_search_result.text:
                web_context = web_search_result.to_context_block()
            # If the user asked to download something, actually fetch the
            # best direct file URL found by the search into the workspace.
            if web_search_result and _DOWNLOAD_RE.search(
                f"{step.objective} {analysis.user_input}"
            ):
                dl_block = await self._maybe_download_file(
                    step, web_search_result, user_input=analysis.user_input
                )
                if dl_block:
                    web_context = f"{web_context}\n{dl_block}"

        # ── Build prompts ──────────────────────────────────────────────────
        system_prompt = EMPLOYEE_SYSTEM_TEMPLATE.format(
            role=employee.role,
            objective=employee.objective,
            responsibilities="\n".join(f"- {r}" for r in employee.responsibilities),
            playbook=role_playbook(employee.role),
            tools=", ".join(employee.tools) if employee.tools else "None (reasoning only)",
            tool_note=self._tool_note(mcp_tools),
            tool_conduct=self._tool_conduct(mcp_tools),
            quality_requirement=employee.quality_requirement,
        ) + _SECURITY_SUFFIX  # always append security rules

        user_message = self._build_user_message(
            step, prior_results, web_context=web_context, mcp_tools=mcp_tools
        )

        messages = [Message(role="user", content=user_message)]
        request = LLMRequest(
            messages=messages,
            model=model,
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=3000,
            task_id=step.task_id,
            employee_id=employee.id,
            step_id=step.id,
            tools=tool_schemas,
            cacheable=not bool(tool_schemas),
            # Fresh web research context must never be answered from a stale
            # semantic cache entry (it replayed old "please clarify" answers).
            freshness_required=bool(web_context),
        )

        log.info(
            "step_executing",
            task_id=step.task_id,
            step=step.step_index,
            role=employee.role,
            model=model,
            attempt=attempt,
            web_context_chars=len(web_context),
            mcp_tools=len(mcp_tools),
        )

        response = await ai_gateway.generate(request)

        # MCP tool loop: run requested tool calls, feed results back
        turn = 0
        while response.tool_calls and turn < MAX_MCP_TOOL_TURNS:
            turn += 1
            messages.append(Message(
                role="assistant", content=response.content or "",
                raw={"role": "assistant", "content": response.content or "",
                     "tool_calls": response.tool_calls},
            ))
            for call in response.tool_calls:
                output = await self._run_mcp_tool(step, call)
                messages.append(Message(
                    role="tool", content=output,
                    raw={"role": "tool", "tool_call_id": call["id"], "content": output},
                ))
            follow_up = LLMRequest(
                messages=messages,
                model=model,
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=3000,
                task_id=step.task_id,
                employee_id=employee.id,
                step_id=step.id,
                tools=tool_schemas,
                cacheable=False,
            )
            response = await ai_gateway.generate(follow_up)

        result, confidence = self._parse_response(response.content)
        employee.confidence = confidence
        employee.last_action = f"Completed step {step.step_index}: {step.objective[:60]}"

        log.info(
            "step_completed",
            task_id=step.task_id,
            step=step.step_index,
            confidence=confidence,
            tokens_out=response.completion_tokens,
            cost=response.cost_usd,
        )

        return result, confidence, model

    def _build_user_message(
        self, step: TaskStep, prior_results: Dict[str, str], web_context: str = "",
        mcp_tools: List = None,
    ) -> str:
        parts = [
            f"## Your Task\n{step.objective}",
            f"\n{step.description}" if step.description else "",
        ]

        # Inject web research context FIRST (before prior steps)
        if web_context:
            # Wrap with PromptSanitizer to prevent injection via scraped web content
            safe_web_context = PromptSanitizer.sanitize_external(web_context, source="web_search")
            parts.append(f"\n{safe_web_context}")

        # Inject relevant context from prior steps
        if step.context_from_steps and prior_results:
            parts.append("\n## Context from Previous Steps")
            for ctx_id in step.context_from_steps:
                if ctx_id in prior_results:
                    snippet = prior_results[ctx_id][:2000]
                    parts.append(f"\n---\n{snippet}")

        if mcp_tools:
            parts.append(
                f"\n## Live Tools (connected via MCP)\n"
                f"{', '.join(t.name for t in mcp_tools[:12])}\n"
                f"Call these tools whenever they help you complete the task."
            )
        else:
            parts.append(
                f"\n## Requested Tools (not connected)\n"
                f"{', '.join(step.required_tools) if step.required_tools else 'None'}"
            )
            parts.append(
                "\nNo live tools connected. Use task details, web context above, and previous-step results."
            )
        parts.append(f"\n## Quality Threshold\nYour output must meet {step.quality_threshold:.0%} quality. Be thorough.")
        parts.append("\n\nNow complete your task. End with: CONFIDENCE: [0.0-1.0]")

        return "\n".join(parts)

    def _parse_response(self, content: str) -> tuple[str, float]:
        """Extract result and confidence from employee response."""
        confidence = 0.75  # default
        result = content.strip()

        # Look for CONFIDENCE: at end
        lines = content.strip().split("\n")
        for i, line in enumerate(reversed(lines)):
            stripped = line.strip()
            if stripped.upper().startswith("CONFIDENCE:"):
                try:
                    val = stripped.split(":", 1)[1].strip()
                    # Handle ranges like "0.85" or "0.8-0.9"
                    val = val.split("-")[0].strip()
                    confidence = float(val)
                    confidence = max(0.0, min(1.0, confidence))
                    # Remove the confidence line from result
                    result = "\n".join(lines[:-(i + 1)]).strip()
                except ValueError:
                    pass
                break

        return result, confidence

    def _needs_web_search(self, step: TaskStep, employee: Employee, analysis: TaskAnalysis) -> bool:
        """Determine if this step benefits from web search."""
        # Deterministic backstop: explicit fetch/download intent always
        # researches, regardless of what the analyzer LLM guessed.
        if _FETCH_RE.search(f"{step.objective} {analysis.user_input}"):
            return True
        if not analysis.needs_research:
            return False
        objective_lower = step.objective.lower()
        return any(kw in objective_lower for kw in _RESEARCH_KEYWORDS)

    async def _maybe_download_file(
        self, step: TaskStep, result, user_input: str = ""
    ) -> str:
        """Download the best direct file URL from search results, if any."""
        try:
            from app.tools.downloader import (
                find_file_urls, rank_urls, download_file, discover_file_urls
            )
            urls = find_file_urls(result.sources, result.text)
            def _hints(text: str) -> List[str]:
                return [
                    w for w in re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
                    if w not in _STOPWORDS
                ]
            if not urls:
                # Second pass: ask the searcher explicitly for direct file links,
                # keyed on the user's own words (step objectives are often too
                # procedural to surface direct PDF URLs).
                try:
                    from app.tools.web_searcher import smart_web_searcher
                    hint_words = _hints(user_input) or _hints(result.query or step.objective)
                    base_q = " ".join(hint_words[:5]) or (result.query or step.objective)[:80]
                    # Note: appending "download" makes Bing return browser
                    # download pages instead of the requested document.
                    extra = await smart_web_searcher.search(
                        query=f"{base_q} pdf", min_sites=5
                    )
                    urls = find_file_urls(extra.sources, extra.text)
                    # Landing pages (index listings) usually hold the real file
                    # hrefs — crawl them to harvest direct file links.
                    if not urls:
                        urls = await discover_file_urls(extra.sources)
                except Exception:
                    urls = []
            if not urls:
                # Last resort: crawl the original search landing pages.
                try:
                    urls = await discover_file_urls(result.sources)
                except Exception:
                    urls = []
            if not urls:
                return ""
            hints = (_hints(user_input) + _hints(result.query or ""))[:6]
            # Try the top ranked candidates in order — some hosts fail with
            # transient SSL/connection errors while mirrors of the same file work.
            info = None
            last_err: Exception | None = None
            for cand in rank_urls(urls, hints)[:4]:
                try:
                    info = await download_file(cand)
                    break
                except Exception as exc:
                    last_err = exc
            if not info:
                raise last_err or RuntimeError("no candidate URL could be downloaded")
            return (
                f"\n## Downloaded File (already saved for the user)\n"
                f"Path: {info['path']}\nSize: {info['bytes'] // 1024} KB\n"
                f"Source: {info['url']}\n"
                f"Tell the user this exact local path in your final answer."
            )
        except Exception as exc:
            log.warning("auto_download_failed", step=step.step_index, error=str(exc)[:200])
            return (
                "\n## Download Attempt\n"
                f"Automatic download failed ({str(exc)[:150]}). "
                "Give the user the best direct source links instead."
            )

    async def _do_web_search(self, step: TaskStep, employee: Employee, analysis: TaskAnalysis):
        """Run SmartWebSearcher and emit a WEB_SEARCH_RESULT event."""
        try:
            from app.tools.web_searcher import smart_web_searcher
            # Build a focused search query from step objective + task context
            query = f"{step.objective[:100]} {' '.join(analysis.required_knowledge[:3])}".strip()
            log.info("web_search_starting", query=query[:60], step=step.step_index)
            result = await smart_web_searcher.search(
                query=query,
                min_sites=5,
                task_id=step.task_id,
            )
            # Count the search in token analytics (source="web" increments the
            # Web Searches counter; previously nothing was ever recorded here).
            try:
                from app.llm.token_tracker import token_tracker
                if step.task_id:
                    token_tracker.record(
                        task_id=step.task_id,
                        step_label=f"Step {step.step_index}: {step.objective[:50]}",
                        model=f"web-search/{result.tier_used}",
                        source="web",
                        prompt_tokens=0,
                        completion_tokens=0,
                        cost_usd=0.0,
                        latency_ms=result.latency_ms,
                        web_sites_checked=result.sites_checked,
                        web_sites_used=result.sites_used,
                        tokens_saved_by_web=result.estimated_tokens_saved,
                    )
            except Exception:
                pass
            await smart_web_searcher.emit_event(
                task_id=step.task_id,
                result=result,
                step_label=f"Step {step.step_index}: {step.objective[:50]}",
            )
            return result
        except Exception as exc:
            log.warning("web_search_in_executor_failed", error=str(exc), step=step.step_index)
            return None

    # ── MCP integration ────────────────────────────────────────────────────────
    def _select_mcp_tools(self, step: TaskStep, analysis: TaskAnalysis) -> List:
        """Pick connected MCP tools relevant to this step (auto routing)."""
        try:
            from app.mcp.manager import mcp_manager
            text = f"{analysis.title} {analysis.user_input} {step.objective}"
            return mcp_manager.relevant_tools(text)
        except Exception as exc:
            log.warning("mcp_tool_selection_failed", error=str(exc))
            return []

    @staticmethod
    def _build_tool_schemas(mcp_tools: List) -> List[dict]:
        """Convert discovered MCP tools into OpenAI-format tool schemas."""
        schemas = []
        for t in mcp_tools:
            schema = t.input_schema or {"type": "object", "properties": {}}
            schema.setdefault("type", "object")
            schema.setdefault("properties", {})
            # MCP schemas may use keys Groq rejects — keep only the safe subset
            schema = {
                k: v for k, v in schema.items()
                if k in ("type", "properties", "required", "items", "enum", "description")
            }
            schemas.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": (f"[{t.server_name}] {t.description}")[:600],
                    "parameters": schema,
                },
            })
        return schemas

    @staticmethod
    def _tool_note(mcp_tools: List) -> str:
        if mcp_tools:
            return (
                "LIVE tools are connected via MCP: "
                + ", ".join(t.name for t in mcp_tools[:12])
                + ". Call them whenever they help — real data beats guessing."
            )
        return "No live tools are connected for this step."

    @staticmethod
    def _tool_conduct(mcp_tools: List) -> str:
        if mcp_tools:
            return (
                "- Use the connected live tools to fetch real data. If a tool fails, "
                "note the error and continue with the data you have."
            )
        return (
            "- Do not call, invent, or simulate tool functions. If a requested tool "
            "is unavailable, state the limitation and continue using reasoning "
            "from the supplied context."
        )

    async def _run_mcp_tool(self, step: TaskStep, call: dict) -> str:
        """Execute one model-requested MCP tool call; never raises."""
        from app.mcp.manager import mcp_manager

        name = call.get("function", {}).get("name", "")
        try:
            arguments = json.loads(call.get("function", {}).get("arguments") or "{}")
            if not isinstance(arguments, dict):
                arguments = {}
        except Exception:
            arguments = {}

        tool = mcp_manager.find_tool(name)
        await event_bus.publish(Event(
            event_type=EventType.MCP_TOOL_CALLED,
            task_id=step.task_id,
            payload={
                "tool": name,
                "server": tool.server_name if tool else "",
                "arguments": arguments,
                "status": "calling",
            },
        ))

        start = time.monotonic()
        try:
            if not tool:
                raise RuntimeError(f"Unknown tool: {name}")
            output = await mcp_manager.call_tool(tool.server_id, name, arguments)
            status = "done"
        except Exception as exc:
            output = f"TOOL_ERROR: {str(exc)[:500]}"
            status = "error"
            log.warning("mcp_tool_call_failed", tool=name, error=str(exc)[:200])

        latency_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "mcp_tool_called",
            task_id=step.task_id, tool=name, status=status,
            latency_ms=latency_ms, output_chars=len(output),
        )
        await event_bus.publish(Event(
            event_type=EventType.MCP_TOOL_CALLED,
            task_id=step.task_id,
            payload={
                "tool": name,
                "server": tool.server_name if tool else "",
                "status": status,
                "latency_ms": latency_ms,
                "output_preview": output[:300],
            },
        ))
        # Cap tool output so one huge payload cannot blow the context
        return output[:12_000]
