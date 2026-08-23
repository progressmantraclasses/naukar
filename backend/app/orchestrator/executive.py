"""
ExecutiveOrchestrator — the brain of the system.
Runs the complete autonomous loop:
  receive_task → analyze → plan_workforce → create_employees →
  decompose → schedule → execute → monitor → quality_check →
  adapt_if_needed → deliver

This is the only component that coordinates all others.
"""
import asyncio
import time
import structlog
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus, Event, EventType
from app.core.config import settings
from app.orchestrator.task_analyzer import TaskIntelligenceEngine
from app.workforce.planner import WorkforcePlanner
from app.workforce.factory import EmployeeFactory
from app.tasks.decomposer import TaskDecomposer
from app.employees.executor import EmployeeExecutor
from app.evaluation.quality import QualityController
from app.router.model_router import DynamicModelRouter
from app.llm.gateway import bind_usage_session
from app.tasks.models import (
    TaskAnalysis, WorkforcePlan, Employee, TaskStep,
    TaskStatus, EmployeeStatus, StepStatus, QualityResult
)
from app.db import models as db_models

log = structlog.get_logger()


async def _emit(task_id: str, event_type: EventType, payload: dict):
    """Helper to emit and log events."""
    await event_bus.publish(Event(event_type=event_type, task_id=task_id, payload=payload))


class ExecutiveOrchestrator:
    """
    Autonomous orchestration loop. One instance per task.
    """

    MAX_STEP_RETRIES = 3
    MAX_FINAL_RETRIES = 2

    def __init__(self, db: AsyncSession):
        self._db = db
        self._analyzer = TaskIntelligenceEngine()
        self._planner = WorkforcePlanner()
        self._decomposer = TaskDecomposer()
        self._executor = EmployeeExecutor()
        self._quality = QualityController()
        self._router = DynamicModelRouter()

    # -----------------------------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------------------------
    async def run(self, task_id: str, user_input: str, user_id: str = "anonymous") -> str:
        """
        Full autonomous loop. Returns the final result string.
        """
        start_time = time.monotonic()
        bind_usage_session(self._db, user_id)
        log.info("orchestrator_started", task_id=task_id)

        # Update DB status
        await self._update_task_status(task_id, TaskStatus.ANALYZING)

        try:
            # ── PHASE 1: Understand the task ──────────────────────────────
            await _emit(task_id, EventType.THINKING, {
                "message": "Understanding your task and analyzing what needs to be done..."
            })
            analysis = await self._analyzer.analyze(task_id, user_input)
            await _emit(task_id, EventType.TASK_ANALYZED, {
                "title": analysis.title,
                "task_type": analysis.task_type,
                "complexity": analysis.complexity.complexity_score,
                "required_skills": analysis.required_skills,
                "required_tools": analysis.required_tools,
                "subtask_estimate": analysis.subtask_count_estimate,
                "risk_level": analysis.risk_level,
            })
            await self._save_task_analysis(task_id, analysis)

            # ── PHASE 2: Design the workforce ────────────────────────────
            await self._update_task_status(task_id, TaskStatus.PLANNING)
            await _emit(task_id, EventType.THINKING, {
                "message": f"Designing the optimal team for this task (complexity: {analysis.complexity.complexity_score:.0%})..."
            })
            plan = await self._planner.plan(analysis)
            await _emit(task_id, EventType.WORKFORCE_CREATED, {
                "topology": plan.topology,
                "roles": [{"role": r.role, "objective": r.objective, "level": r.hierarchy_level}
                          for r in plan.roles],
                "rationale": plan.rationale,
            })

            # ── PHASE 3: Create employees ─────────────────────────────────
            factory = EmployeeFactory(task_id)
            employees = factory.create_from_plan(plan)
            for emp in employees:
                await self._save_employee(emp)
                await _emit(task_id, EventType.EMPLOYEE_CREATED, {
                    "employee_id": emp.id,
                    "role": emp.role,
                    "objective": emp.objective,
                    "skills": emp.skills,
                    "tools": emp.tools,
                    "hierarchy_level": emp.hierarchy_level,
                    "manager_id": emp.manager_id,
                    "status": emp.status.value if hasattr(emp.status, 'value') else emp.status,
                })

            # ── PHASE 4: Decompose into steps ─────────────────────────────
            await _emit(task_id, EventType.THINKING, {
                "message": "Planning execution strategy and assigning work..."
            })
            steps = await self._decomposer.decompose(analysis, plan, employees)
            for step in steps[:settings.MAX_STEPS]:
                await self._save_step(step)
                await _emit(task_id, EventType.TASK_ASSIGNED, {
                    "step_id": step.id,
                    "step_index": step.step_index,
                    "objective": step.objective,
                    "assigned_role": step.assigned_employee_role,
                    "assigned_employee_id": step.assigned_employee_id,
                    "dependencies": step.dependencies,
                })

            # ── PHASE 5: Execute ──────────────────────────────────────────
            await self._update_task_status(task_id, TaskStatus.EXECUTING)
            prior_results: Dict[str, str] = {}
            employee_map = {e.id: e for e in employees}

            for step in steps:
                if time.monotonic() - start_time > settings.MAX_RUNTIME_SECONDS:
                    raise TimeoutError("Maximum task runtime exceeded")
                if step.step_index >= settings.MAX_STEPS:
                    step.status = StepStatus.SKIPPED
                    continue
                await self._execute_step_with_retry(
                    step=step,
                    employee_map=employee_map,
                    analysis=analysis,
                    prior_results=prior_results,
                    factory=factory,
                )
                if step.result:
                    prior_results[step.id] = step.result

            # ── PHASE 6: Assemble final result ────────────────────────────
            await self._update_task_status(task_id, TaskStatus.REVIEWING)
            final_result = await self._assemble_final_result(
                analysis=analysis,
                steps=steps,
                prior_results=prior_results,
                employees=employees,
            )

            # ── PHASE 7: Final quality gate ───────────────────────────────
            await _emit(task_id, EventType.THINKING, {
                "message": "Running final quality review of all completed work..."
            })
            qc = await self._quality.evaluate_final(user_input, final_result, analysis)
            await _emit(task_id, EventType.QUALITY_CHECKED, {
                "score": qc.score,
                "passed": qc.passed,
                "issues": qc.issues,
                "feedback": qc.feedback,
                "stage": "final",
            })

            retry_count = 0
            while not qc.passed and retry_count < self.MAX_FINAL_RETRIES:
                retry_count += 1
                await _emit(task_id, EventType.TASK_REPLANNED, {
                    "reason": f"Final quality failed ({qc.score:.0%}): {qc.feedback}",
                    "retry": retry_count,
                })
                final_result = await self._fix_final_result(
                    analysis, final_result, qc, prior_results
                )
                qc = await self._quality.evaluate_final(user_input, final_result, analysis)

            # ── DONE ─────────────────────────────────────────────────────
            elapsed = int((time.monotonic() - start_time) * 1000)
            await self._complete_task(task_id, final_result, qc.score)
            await _emit(task_id, EventType.FINAL_RESULT_READY, {
                "result": final_result,
                "quality_score": qc.score,
                "elapsed_ms": elapsed,
                "num_employees": len(employees),
                "num_steps": len(steps),
            })

            # ── Emit token usage summary ─────────────────────────────────
            from app.llm.token_tracker import token_tracker
            token_tracker.print_final_summary(task_id)
            summary = token_tracker.get_summary(task_id)
            if summary:
                await _emit(task_id, EventType.TASK_TOKEN_SUMMARY, summary.to_dict())

            log.info(
                "orchestrator_completed",
                task_id=task_id,
                quality=qc.score,
                elapsed_ms=elapsed,
            )
            return final_result

        except Exception as e:
            log.exception("orchestrator_error", task_id=task_id, error=str(e))
            await self._fail_task(task_id, str(e))
            await _emit(task_id, EventType.TASK_FAILED, {
                "error": str(e),
                "task_id": task_id,
            })
            raise

    # -----------------------------------------------------------------------
    # STEP EXECUTION WITH RETRY + CASCADE
    # -----------------------------------------------------------------------
    async def _execute_step_with_retry(
        self,
        step: TaskStep,
        employee_map: Dict[str, Employee],
        analysis: TaskAnalysis,
        prior_results: Dict[str, str],
        factory: EmployeeFactory,
    ):
        """Execute one step with quality-gated retry and model cascade."""
        employee = employee_map.get(step.assigned_employee_id)
        if not employee:
            log.error("employee_not_found", step_id=step.id, emp_id=step.assigned_employee_id)
            return

        await _emit(step.task_id, EventType.STEP_STARTED, {
            "step_id": step.id,
            "step_index": step.step_index,
            "objective": step.objective,
            "employee_id": employee.id,
            "role": employee.role,
        })
        await _emit(step.task_id, EventType.EMPLOYEE_STATUS_CHANGED, {
            "employee_id": employee.id,
            "role": employee.role,
            "status": "working",
            "current_task": step.objective,
        })

        for attempt in range(self.MAX_STEP_RETRIES):
            result, confidence, model = await self._executor.execute(
                step=step,
                employee=employee,
                analysis=analysis,
                prior_results=prior_results,
                attempt=attempt,
            )

            await _emit(step.task_id, EventType.LLM_CALLED, {
                "employee_id": employee.id,
                "role": employee.role,
                "model": model,
                "step_index": step.step_index,
                "confidence": confidence,
            })

            # Quality gate
            qc = await self._quality.evaluate(step, employee, result, analysis)
            await _emit(step.task_id, EventType.QUALITY_CHECKED, {
                "step_id": step.id,
                "step_index": step.step_index,
                "score": qc.score,
                "passed": qc.passed,
                "issues": qc.issues,
                "employee_id": employee.id,
                "stage": "step",
            })

            if qc.passed or attempt == self.MAX_STEP_RETRIES - 1:
                step.result = result
                step.confidence = confidence
                step.model = model
                step.status = StepStatus.COMPLETED
                await self._update_step(step)
                await _emit(step.task_id, EventType.STEP_COMPLETED, {
                    "step_id": step.id,
                    "step_index": step.step_index,
                    "quality_score": qc.score,
                    "confidence": confidence,
                    "model": model,
                })
                await _emit(step.task_id, EventType.EMPLOYEE_STATUS_CHANGED, {
                    "employee_id": employee.id,
                    "role": employee.role,
                    "status": "completed",
                    "confidence": confidence,
                    "last_action": f"Completed: {step.objective[:60]}",
                })
                break
            else:
                step.retry_count = attempt + 1
                log.warning(
                    "step_quality_fail_retrying",
                    step=step.step_index,
                    score=qc.score,
                    attempt=attempt,
                )
                await _emit(step.task_id, EventType.EMPLOYEE_STATUS_CHANGED, {
                    "employee_id": employee.id,
                    "role": employee.role,
                    "status": "retrying",
                    "reason": f"Quality {qc.score:.0%} < {step.quality_threshold:.0%}",
                })

    # -----------------------------------------------------------------------
    # FINAL RESULT ASSEMBLY
    # -----------------------------------------------------------------------
    async def _assemble_final_result(
        self,
        analysis: TaskAnalysis,
        steps: List[TaskStep],
        prior_results: Dict[str, str],
        employees: List[Employee],
    ) -> str:
        """
        Use an LLM to intelligently synthesize all step results into the final deliverable.
        """
        from app.llm.gateway import ai_gateway
        from app.llm.provider import LLMRequest, Message

        completed_parts = []
        for step in steps:
            if step.result and step.status == StepStatus.COMPLETED:
                completed_parts.append(
                    f"### {step.assigned_employee_role}: {step.objective}\n{step.result}"
                )

        all_work = "\n\n".join(completed_parts)
        if not all_work:
            return "Task completed. No output was generated."

        prompt = f"""You are a senior project manager synthesizing work from multiple specialists.

User's original request: {analysis.user_input}
Expected output format: {analysis.expected_output_format}

Work completed by the team:
---
{all_work[:6000]}
---

Synthesize all this work into a single, coherent, well-structured final deliverable for the user.
Use clean Markdown formatting: a clear title, a short executive summary, descriptive headings,
bulleted lists for recommendations, and Markdown tables only when comparing structured data.
Keep paragraphs short, avoid repeated points, and label assumptions and source limitations clearly.
Do not mention the internal process or team structure.
The user should receive the final result as if it came from a single expert."""

        from app.core.config import settings
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            model=settings.MODEL_SMART,
            temperature=0.4,
            max_tokens=4000,
        )
        response = await ai_gateway.generate(request)
        return response.content

    async def _fix_final_result(
        self,
        analysis: TaskAnalysis,
        current_result: str,
        qc: QualityResult,
        prior_results: Dict[str, str],
    ) -> str:
        """Attempt to fix the final result based on QC feedback."""
        from app.llm.gateway import ai_gateway
        from app.llm.provider import LLMRequest, Message

        prompt = f"""The following output was reviewed and found lacking.

User request: {analysis.user_input}

Current output:
---
{current_result[:4000]}
---

Quality issues found:
{chr(10).join(f"- {issue}" for issue in qc.issues)}

Reviewer feedback: {qc.feedback}

Please revise and improve the output to address all issues."""

        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            model=settings.MODEL_SMART,
            temperature=0.3,
            max_tokens=4000,
        )
        response = await ai_gateway.generate(request)
        return response.content

    # -----------------------------------------------------------------------
    # DATABASE HELPERS
    # -----------------------------------------------------------------------
    async def _update_task_status(self, task_id: str, status: TaskStatus):
        from sqlalchemy import update
        await self._db.execute(
            update(db_models.Task)
            .where(db_models.Task.id == task_id)
            .values(status=status.value, started_at=datetime.now(timezone.utc))
        )
        await self._db.commit()

    async def _save_task_analysis(self, task_id: str, analysis: TaskAnalysis):
        from sqlalchemy import update
        await self._db.execute(
            update(db_models.Task)
            .where(db_models.Task.id == task_id)
            .values(
                title=analysis.title,
                task_type=analysis.task_type,
                complexity_score=analysis.complexity.complexity_score,
                risk_score=analysis.complexity.risk_score,
                reasoning_requirement=analysis.complexity.reasoning_requirement,
                research_requirement=analysis.complexity.research_requirement,
                tool_requirement=analysis.complexity.tool_requirement,
                accuracy_requirement=analysis.complexity.accuracy_requirement,
                required_skills=analysis.required_skills,
                required_tools=analysis.required_tools,
            )
        )
        await self._db.commit()

    async def _save_employee(self, emp: Employee):
        db_emp = db_models.Employee(
            id=emp.id,
            task_id=emp.task_id,
            role=emp.role,
            objective=emp.objective,
            responsibilities=emp.responsibilities,
            skills=emp.skills,
            tools=emp.tools,
            quality_requirement=emp.quality_requirement,
            hierarchy_level=emp.hierarchy_level,
            manager_id=emp.manager_id,
            status="idle",
        )
        self._db.add(db_emp)
        await self._db.commit()

    async def _save_step(self, step: TaskStep):
        db_step = db_models.TaskStep(
            id=step.id,
            task_id=step.task_id,
            step_index=step.step_index,
            objective=step.objective,
            description=step.description,
            assigned_employee_id=step.assigned_employee_id,
            dependencies=step.dependencies,
            required_tools=step.required_tools,
            quality_threshold=step.quality_threshold,
            status="pending",
        )
        self._db.add(db_step)
        await self._db.commit()

    async def _update_step(self, step: TaskStep):
        from sqlalchemy import update
        await self._db.execute(
            update(db_models.TaskStep)
            .where(db_models.TaskStep.id == step.id)
            .values(
                status=step.status.value,
                result=step.result,
                confidence=step.confidence,
                model_used=step.model,
                retry_count=step.retry_count,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await self._db.commit()

    async def _complete_task(self, task_id: str, result: str, quality_score: float):
        from sqlalchemy import update
        await self._db.execute(
            update(db_models.Task)
            .where(db_models.Task.id == task_id)
            .values(
                status=TaskStatus.COMPLETED.value,
                final_result=result,
                quality_score=quality_score,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await self._db.commit()

    async def _fail_task(self, task_id: str, error: str):
        from sqlalchemy import update
        await self._db.execute(
            update(db_models.Task)
            .where(db_models.Task.id == task_id)
            .values(
                status=TaskStatus.FAILED.value,
                error_message=error,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await self._db.commit()
