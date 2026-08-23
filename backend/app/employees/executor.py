"""
EmployeeExecutor — runs a TaskStep using the assigned employee and selected model.
Handles the actual LLM call, context injection, retry on failure, and result extraction.
"""
import json
import time
import structlog
from typing import List, Optional, Dict

from app.llm.gateway import ai_gateway
from app.llm.provider import LLMRequest, Message
from app.tasks.models import TaskStep, Employee, TaskAnalysis, StepStatus, EmployeeStatus
from app.router.model_router import DynamicModelRouter
from app.core.config import settings
from app.workforce.role_catalog import role_playbook
from app.security.validators import PromptSanitizer

log = structlog.get_logger()

# Keywords in step objectives that suggest web research is needed
_RESEARCH_KEYWORDS = {
    "research", "search", "find", "gather", "collect", "look up", "investigate",
    "analyze", "trends", "market", "data", "statistics", "report", "survey",
    "competitor", "industry", "latest", "current", "recent", "news", "information",
}

EMPLOYEE_SYSTEM_TEMPLATE = """You are {role} — an AI specialist working on a project.

Your objective: {objective}

Your responsibilities:
{responsibilities}

Role playbook:
{playbook}

Requested tools (reference only; no live tools are connected): {tools}

Work ethic:
- Be thorough and accurate
- Provide clear, structured output
- If you're uncertain, say so explicitly with your confidence level
- Focus ONLY on your assigned step — do not do work that belongs to others
- Do not call, invent, or simulate tool functions. If a requested tool is unavailable, state the limitation and continue using reasoning from the supplied context.
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
        model = self._router.select_model(employee, step, analysis, attempt=attempt)
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

        # ── Build prompts ──────────────────────────────────────────────────
        system_prompt = EMPLOYEE_SYSTEM_TEMPLATE.format(
            role=employee.role,
            objective=employee.objective,
            responsibilities="\n".join(f"- {r}" for r in employee.responsibilities),
            playbook=role_playbook(employee.role),
            tools=", ".join(employee.tools) if employee.tools else "None (reasoning only)",
            quality_requirement=employee.quality_requirement,
        ) + _SECURITY_SUFFIX  # always append security rules

        user_message = self._build_user_message(step, prior_results, web_context=web_context)

        request = LLMRequest(
            messages=[Message(role="user", content=user_message)],
            model=model,
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=3000,
            task_id=step.task_id,
            employee_id=employee.id,
            step_id=step.id,
        )

        log.info(
            "step_executing",
            task_id=step.task_id,
            step=step.step_index,
            role=employee.role,
            model=model,
            attempt=attempt,
            web_context_chars=len(web_context),
        )

        response = await ai_gateway.generate(request)

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
        self, step: TaskStep, prior_results: Dict[str, str], web_context: str = ""
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
        if not analysis.needs_research:
            return False
        objective_lower = step.objective.lower()
        return any(kw in objective_lower for kw in _RESEARCH_KEYWORDS)

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
            await smart_web_searcher.emit_event(
                task_id=step.task_id,
                result=result,
                step_label=f"Step {step.step_index}: {step.objective[:50]}",
            )
            return result
        except Exception as exc:
            log.warning("web_search_in_executor_failed", error=str(exc), step=step.step_index)
            return None
