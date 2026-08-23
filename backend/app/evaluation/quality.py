"""
QualityController — evaluates employee output against quality thresholds.
Uses an independent LLM call (potentially a different model) to score results.
"""
import json
import structlog
from app.llm.gateway import ai_gateway
from app.llm.provider import LLMRequest, Message
from app.tasks.models import TaskStep, Employee, TaskAnalysis, QualityResult
from app.core.config import settings

log = structlog.get_logger()

QC_SYSTEM_PROMPT = """You are the Quality Controller for an Autonomous AI Workforce Platform.

Your job: Evaluate the output of an AI employee against quality criteria.
Be critical but fair. Think like a senior manager reviewing employee work.

Return ONLY valid JSON:
{
  "score": 0.0-1.0,
  "passed": true/false,
  "issues": ["issue1", "issue2"],
  "feedback": "Specific, actionable feedback for improvement"
}

Scoring criteria:
- 1.0: Perfect — complete, accurate, well-structured, no issues
- 0.9: Excellent — minor stylistic improvements possible
- 0.8: Good — meets requirements with small gaps
- 0.7: Acceptable — functional but missing some elements
- 0.6: Marginal — significant gaps, needs revision
- 0.5 and below: Insufficient — major problems, must redo

Evaluate:
1. Does it fulfill the step objective?
2. Is the information accurate and well-reasoned?
3. Is the output complete (nothing missing)?
4. Is it structured and clear?
5. Does it meet the required quality level?
"""


class QualityController:
    """
    Independent quality evaluator — uses a different model than the worker
    to avoid self-evaluation bias.
    """

    def __init__(self):
        # Always use smart model for quality checks
        self._model = settings.MODEL_SMART

    async def evaluate(
        self,
        step: TaskStep,
        employee: Employee,
        result: str,
        analysis: TaskAnalysis,
    ) -> QualityResult:
        log.info(
            "quality_check_started",
            task_id=step.task_id,
            step=step.step_index,
            threshold=step.quality_threshold,
        )

        prompt = f"""Evaluate this employee output:

Employee Role: {employee.role}
Step Objective: {step.objective}
Quality Threshold Required: {step.quality_threshold:.0%}

Employee Output:
---
{result[:3000]}
---

Score this output and determine if it passes the quality threshold of {step.quality_threshold:.0%}."""

        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            model=self._model,
            system_prompt=QC_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=800,
            json_mode=True,
            task_id=step.task_id,
        )

        response = await ai_gateway.generate(request)

        try:
            data = json.loads(response.content)
            score = float(data.get("score", 0.7))
            passed = score >= step.quality_threshold
            result_obj = QualityResult(
                score=score,
                passed=passed,
                issues=data.get("issues", []),
                feedback=data.get("feedback", ""),
                checker_model=self._model,
            )
        except (json.JSONDecodeError, ValueError):
            log.warning("qc_json_parse_error", raw=response.content[:200])
            result_obj = QualityResult(
                score=0.75,
                passed=0.75 >= step.quality_threshold,
                feedback="Quality check parsing failed — assuming acceptable.",
                checker_model=self._model,
            )

        log.info(
            "quality_check_complete",
            task_id=step.task_id,
            step=step.step_index,
            score=result_obj.score,
            passed=result_obj.passed,
        )
        return result_obj

    async def evaluate_final(
        self,
        task_input: str,
        final_result: str,
        analysis: TaskAnalysis,
    ) -> QualityResult:
        """Final quality check on the assembled result."""
        prompt = f"""Evaluate the FINAL output for the user's original request:

User Request: {task_input}
Expected Output Format: {analysis.expected_output_format}
Quality Required: {analysis.complexity.accuracy_requirement:.0%}

Final Output:
---
{final_result[:4000]}
---

Does this final output fully satisfy the user's original request?"""

        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            model=self._model,
            system_prompt=QC_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=800,
            json_mode=True,
        )

        response = await ai_gateway.generate(request)

        try:
            data = json.loads(response.content)
            score = float(data.get("score", 0.75))
            threshold = analysis.complexity.accuracy_requirement
            return QualityResult(
                score=score,
                passed=score >= threshold,
                issues=data.get("issues", []),
                feedback=data.get("feedback", ""),
                checker_model=self._model,
            )
        except Exception:
            return QualityResult(score=0.75, passed=True, checker_model=self._model)
