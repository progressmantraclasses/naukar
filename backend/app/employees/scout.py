"""
CompetitionScoutWorker — the "super worker" fast path for competition tasks.

Instead of hiring a 4-8 employee workforce, ONE Competition Scout does the
entire job with minimum tokens:
  1. Browse competitor websites      → FREE (DuckDuckGo tier, zero tokens)
  2. Extract pricing/features        → deterministic regex (zero tokens)
  3. Competitor discovery (optional) → 1 tiny cheap-model call, only if the
                                       user did not name the competitors
  4. Synthesize the final report     → 1 single LLM call on compact data

Total: ~2 LLM calls vs 15-30 in the standard workforce pipeline.
"""
import structlog

from app.core.config import settings
from app.core.events import event_bus, Event, EventType
from app.llm.gateway import ai_gateway
from app.llm.provider import LLMRequest, Message
from app.tasks.models import Employee
from app.tools.competitor_scout import CompetitorScout, CompetitionScanResult

log = structlog.get_logger()

_SYNTH_SYSTEM = (
    "You are a senior competitive intelligence analyst. "
    "Write concise, factual, well-structured competition analyses. "
    "Only use facts present in the provided research data — never invent "
    "numbers or features. Label anything uncertain."
)


class CompetitionScoutWorker:
    """Runs the whole competition task as a single token-minimal super worker."""

    async def run(
        self,
        task_id: str,
        user_input: str,
        employee: Employee,
    ) -> tuple[str, str, float, CompetitionScanResult]:
        """
        Returns (final_report, model_used, confidence, scan_result).
        """
        self._task_id = task_id
        # ── 1. Browse + deterministic extraction (zero tokens) ─────────────
        scout = CompetitorScout(task_id=task_id, on_progress=self._emit_progress)
        scan = await scout.run(user_input)

        await event_bus.publish(Event(
            event_type=EventType.COMPETITOR_MATRIX_READY,
            task_id=task_id,
            payload={
                "own_product": scan.own_product,
                "profiles": [c.to_dict() for c in scan.competitors],
                "matrix_md": scan.matrix_md,
                "sites_browsed": scan.sites_browsed,
                "llm_calls_used": scan.llm_calls_used,
                "discovery_source": scan.discovery_source,
                "estimated_tokens_saved": scan.estimated_tokens_saved,
                "latency_ms": scan.latency_ms,
            },
        ))

        if not scan.competitors:
            # Nothing found on the web — deliver an honest minimal report.
            return (
                "## Competition Analysis\n\n"
                "No competitor data could be gathered from the web for this request. "
                "Please include competitor names in the task (e.g. \"compare X vs Y\") "
                "and try again.",
                "none", 0.3, scan,
            )

        # ── 2. Single synthesis call on compact extracted data ─────────────
        employee.last_action = "Synthesizing competition report"
        model = settings.MODEL_SMART
        prompt = self._build_synthesis_prompt(user_input, scan)

        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            model=model,
            system_prompt=_SYNTH_SYSTEM,
            temperature=0.4,
            max_tokens=1600,
            task_id=task_id,
            employee_id=employee.id,
            task_type="competition_analysis",
        )
        response = await ai_gateway.generate(request)

        report, confidence = self._parse_response(response.content, scan)
        log.info(
            "competition_scout_synthesis_done",
            task_id=task_id,
            model=response.model,
            tokens_in=response.prompt_tokens,
            tokens_out=response.completion_tokens,
            confidence=confidence,
        )
        return report, response.model, confidence, scan

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_synthesis_prompt(user_input: str, scan: CompetitionScanResult) -> str:
        parts = [f"User request: {user_input}"]
        if scan.own_product:
            parts.append(f"Subject product/business: {scan.own_product}")
        parts.append(
            f"A scout browsed {scan.sites_browsed} web pages (free tier) and "
            "extracted the following data deterministically:\n"
        )
        parts.append(scan.matrix_md)
        for c in scan.competitors:
            if c.pricing:
                parts.append(f"- {c.name} pricing signals: {'; '.join(c.pricing[:4])}")
        parts.append(
            "\nWrite the competition analysis in Markdown:\n"
            "1. Executive summary (max 3 bullets)\n"
            "2. Competitor comparison table\n"
            "3. Per-competitor snapshot (pricing, strengths, weaknesses — max 3 bullets each)\n"
            "4. Market gaps and opportunities\n"
            "5. Recommended positioning\n"
            "Use ONLY the provided facts. Max ~700 words.\n"
            "End with: CONFIDENCE: [0.0-1.0]"
        )
        return "\n".join(parts)

    @staticmethod
    def _parse_response(content: str, scan: CompetitionScanResult) -> tuple[str, float]:
        """Strip the trailing CONFIDENCE line; default confidence from data coverage."""
        result = content.strip()
        lines = result.split("\n")
        confidence = 0.85 if len(scan.competitors) >= 3 else 0.70
        for i, line in enumerate(reversed(lines)):
            stripped = line.strip()
            if stripped.upper().startswith("CONFIDENCE:"):
                try:
                    val = stripped.split(":", 1)[1].strip().split("-")[0].strip()
                    confidence = max(0.0, min(1.0, float(val)))
                    result = "\n".join(lines[: -(i + 1)]).strip()
                except ValueError:
                    pass
                break
        return result, confidence

    async def _emit_progress(
        self,
        name: str,
        status: str,
        profile,
    ):
        """Live browsing progress for the frontend Competition panel."""
        try:
            payload = {"name": name, "status": status}
            if profile is not None:
                payload["profile"] = profile.to_dict()
            await event_bus.publish(Event(
                event_type=EventType.COMPETITOR_SCAN_PROGRESS,
                task_id=getattr(self, "_task_id", ""),
                payload=payload,
            ))
        except Exception as exc:
            log.warning("competition_progress_event_failed", error=str(exc))
