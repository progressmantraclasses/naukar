"""
TaskDecomposer — converts a task analysis + workforce plan into a DAG of TaskSteps.
Each step is a concrete work unit assigned to a specific employee.
"""
import json
import structlog
from typing import List, Dict

from app.llm.gateway import ai_gateway
from app.llm.provider import LLMRequest, Message
from app.tasks.models import TaskAnalysis, WorkforcePlan, TaskStep, Employee
from app.core.config import settings

log = structlog.get_logger()

DECOMPOSER_SYSTEM_PROMPT = """You are the Task Decomposer for an Autonomous AI Workforce Platform.

Given a task analysis and the workforce team, break the task into concrete, ordered work steps.
Each step is assigned to one employee by their role.

RULES:
1. Steps must be concrete and actionable — not vague
2. Order steps logically: research before analysis, analysis before writing, writing before review
3. Steps that can run simultaneously get the same dependency list (empty)
4. Every step must be assigned to exactly one role from the provided team
5. Include verification/review steps if the team has a reviewer

Return ONLY valid JSON:
{
  "steps": [
    {
      "step_index": 0,
      "objective": "Clear one-sentence objective for this step",
      "description": "What the employee should do and produce",
      "assigned_role": "Exact role name from team",
      "dependencies": [],
      "required_tools": ["tool1"],
      "quality_threshold": 0.75-0.95,
      "context_from_steps": []
    }
  ]
}

Note: dependencies is a list of step_index integers that must complete before this step starts.
context_from_steps lists step_index integers whose results should be passed to this step.
"""


class TaskDecomposer:
    """
    Breaks a task into a DAG of concrete steps assigned to specific employees.
    """

    def __init__(self):
        self._model = settings.MODEL_SMART

    async def decompose(
        self,
        analysis: TaskAnalysis,
        plan: WorkforcePlan,
        employees: List[Employee],
    ) -> List[TaskStep]:
        log.info("task_decomposition_started", task_id=analysis.task_id)

        prompt = self._build_prompt(analysis, plan, employees)
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            model=self._model,
            system_prompt=DECOMPOSER_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2500,
            json_mode=True,
            task_id=analysis.task_id,
        )

        response = await ai_gateway.generate(request)

        try:
            data = json.loads(response.content)
            raw_steps = data.get("steps", [])
        except json.JSONDecodeError:
            log.error("decomposition_json_error", raw=response.content[:300])
            raw_steps = self._fallback_steps(analysis, employees)

        role_to_employee: Dict[str, Employee] = {e.role: e for e in employees}
        steps = []
        for raw in raw_steps:
            role = raw.get("assigned_role", "")
            emp = role_to_employee.get(role) or employees[0]
            step = TaskStep(
                task_id=analysis.task_id,
                step_index=raw.get("step_index", len(steps)),
                objective=raw.get("objective", "Execute step"),
                description=raw.get("description", ""),
                assigned_employee_id=emp.id,
                assigned_employee_role=emp.role,
                dependencies=[str(d) for d in raw.get("dependencies", [])],
                required_tools=raw.get("required_tools", []),
                quality_threshold=raw.get("quality_threshold", 0.80),
                context_from_steps=[str(c) for c in raw.get("context_from_steps", [])],
            )
            steps.append(step)

        log.info("task_decomposition_complete", task_id=analysis.task_id, num_steps=len(steps))
        return steps

    def _build_prompt(
        self, analysis: TaskAnalysis, plan: WorkforcePlan, employees: List[Employee]
    ) -> str:
        team_description = "\n".join(
            f"  - {e.role}: {e.objective}" for e in employees
        )
        return f"""Task: {analysis.user_input}

Task Analysis:
- Type: {analysis.task_type}
- Complexity: {analysis.complexity.complexity_score:.2f}
- Needs Research: {analysis.needs_research}
- Expected Output: {analysis.expected_output_format}

Available Team:
{team_description}

Workforce Topology: {plan.topology}

Decompose this task into concrete sequential/parallel steps for this team."""

    def _fallback_steps(
        self, analysis: TaskAnalysis, employees: List[Employee]
    ) -> List[dict]:
        """Simple fallback: one step per employee in sequence."""
        steps = []
        for i, emp in enumerate(employees):
            steps.append({
                "step_index": i,
                "objective": emp.objective,
                "description": f"Complete your assigned work as {emp.role}",
                "assigned_role": emp.role,
                "dependencies": [i - 1] if i > 0 else [],
                "required_tools": emp.tools,
                "quality_threshold": emp.quality_requirement,
                "context_from_steps": [i - 1] if i > 0 else [],
            })
        return steps
