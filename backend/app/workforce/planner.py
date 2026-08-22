"""
WorkforcePlanner — the most important component.
Given a task analysis, it decides: what roles to create, hierarchy, and topology.
It thinks like a senior project manager: "If a human company had to do this, what team would it need?"
"""
import json
import structlog
from typing import List

from app.llm.registry import llm_registry
from app.llm.provider import LLMRequest, Message
from app.tasks.models import (
    TaskAnalysis, WorkforcePlan, EmployeeDefinition, WorkforceTopology
)
from app.core.config import settings
from app.workforce.role_catalog import apply_role_profile, ROLE_CATALOG

log = structlog.get_logger()

PLANNER_SYSTEM_PROMPT = """You are the Workforce Planner for an Autonomous AI Workforce Platform.

Your job: Given a task analysis, design the minimum viable team of AI employees needed to complete the task successfully.

CRITICAL RULES:
1. MINIMUM WORKFORCE PRINCIPLE — Do NOT over-hire. Use the smallest team that can reliably succeed.
   - Simple task (complexity < 0.3): 1-2 employees, no manager needed
   - Medium task (complexity 0.3-0.6): 2-4 employees, maybe 1 manager
   - Complex task (complexity > 0.6): 3-8 employees with hierarchy
   - Very complex (complexity > 0.85): Up to 10 employees with directors/managers/specialists
2. Roles must EMERGE from the task — never hard-code. Think: "what would a real company do?"
3. Each role needs a clear, distinct objective. No duplicate roles.
4. Every specialist should have a clear manager or report to the project lead.
5. If review is needed, include an independent reviewer (different from the main workers).
6. Prefer role titles from the role catalog below so every employee receives a proven skill set.

Return ONLY valid JSON in this exact format:
{
  "topology": "sequential|parallel|hierarchical|iterative",
  "rationale": "Why this team structure for this specific task",
  "roles": [
    {
      "role": "Role Title",
      "objective": "Clear one-sentence objective",
      "responsibilities": ["resp1", "resp2", "resp3"],
      "skills": ["skill1", "skill2"],
      "tools": ["tool1", "tool2"],
      "quality_requirement": 0.0-1.0,
      "hierarchy_level": 0 (top) | 1 | 2 (bottom),
      "reports_to_role": "Role Title of manager or null"
    }
  ]
}

Topology guide:
- sequential: one employee's output feeds the next (A→B→C)
- parallel: multiple employees work simultaneously, results merged
- hierarchical: manager coordinates specialists (most common for complex tasks)
- iterative: worker+reviewer loop until quality passes

Examples:
- "Summarize this PDF" → 1 role: Document Analyst, topology: sequential
- "Create market research report" → hierarchical: Project Lead + Researchers + Analyst + Writer + Reviewer
- "Fix this bug" → sequential: Code Analyst → Debug Engineer → QA → Reviewer
- "Draft a quick email" → 1 role: Communication Specialist (maybe + reviewer if risk=high)

IMPORTANT: The roles array is ordered by creation order. List the manager/lead FIRST.
"""


class WorkforcePlanner:
    """
    Given a TaskAnalysis, produces a WorkforcePlan with the optimal team.
    LLM-driven planning + deterministic validation.
    """

    def __init__(self):
        self._model = settings.MODEL_SMART

    async def plan(self, analysis: TaskAnalysis) -> WorkforcePlan:
        log.info("workforce_planning_started", task_id=analysis.task_id)

        prompt = self._build_prompt(analysis)
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            model=self._model,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            temperature=0.4,
            max_tokens=2000,
            json_mode=True,
            task_id=analysis.task_id,
        )

        provider = llm_registry.get_provider(self._model)
        response = await provider.generate(request)

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            log.error("workforce_plan_json_error", raw=response.content[:300])
            data = self._fallback_plan(analysis)

        roles = [EmployeeDefinition(**r) for r in data.get("roles", [])]
        roles = self._validate_and_fix(roles, analysis)

        plan = WorkforcePlan(
            task_id=analysis.task_id,
            topology=WorkforceTopology(data.get("topology", "sequential")),
            roles=roles,
            rationale=data.get("rationale", ""),
            estimated_cost_usd=self._estimate_cost(roles, analysis),
        )

        log.info(
            "workforce_plan_complete",
            task_id=analysis.task_id,
            topology=plan.topology,
            num_roles=len(plan.roles),
            roles=[r.role for r in plan.roles],
        )
        return plan

    def _build_prompt(self, analysis: TaskAnalysis) -> str:
        return f"""Task to plan workforce for:

User Request: {analysis.user_input}

Task Analysis:
- Type: {analysis.task_type}
- Description: {analysis.description}
- Complexity: {analysis.complexity.complexity_score:.2f}
- Risk: {analysis.risk_level}
- Required Skills: {', '.join(analysis.required_skills)}
- Required Tools: {', '.join(analysis.required_tools)}
- Needs Research: {analysis.needs_research}
- Needs Review: {analysis.needs_review}
- Estimated Subtasks: {analysis.subtask_count_estimate}
- Expected Output: {analysis.expected_output_format}

Preferred role catalog: {", ".join(profile.role for profile in ROLE_CATALOG.values())}

Design the optimal minimum workforce team for this task.
Remember: complexity={analysis.complexity.complexity_score:.2f} means you should create approximately {self._suggested_team_size(analysis.complexity.complexity_score)} employees."""

    def _suggested_team_size(self, complexity: float) -> str:
        if complexity < 0.25:
            return "1"
        elif complexity < 0.45:
            return "2"
        elif complexity < 0.60:
            return "3"
        elif complexity < 0.75:
            return "4-5"
        elif complexity < 0.85:
            return "5-7"
        else:
            return "6-10"

    def _validate_and_fix(
        self, roles: List[EmployeeDefinition], analysis: TaskAnalysis
    ) -> List[EmployeeDefinition]:
        """Ensure the plan is sane: no duplicates, max cap, reviewer if needed."""
        # Normalize generated roles against the reusable capability catalog.
        roles = [apply_role_profile(role) for role in roles]

        # Deduplicate roles by title
        seen = set()
        unique_roles = []
        for r in roles:
            key = r.role.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_roles.append(r)

        # Cap at max
        max_emp = settings.MAX_EMPLOYEES_PER_TASK
        if len(unique_roles) > max_emp:
            unique_roles = unique_roles[:max_emp]

        # Add reviewer if needed and not present
        if analysis.needs_review and not any("review" in r.role.lower() or "qa" in r.role.lower() for r in unique_roles):
            unique_roles.append(EmployeeDefinition(
                role="Quality Reviewer",
                objective="Review all work products for quality, accuracy, and completeness",
                responsibilities=["Review all outputs", "Identify gaps", "Ensure standards met"],
                skills=["critical thinking", "quality assurance", "verification"],
                tools=[],
                quality_requirement=0.90,
                hierarchy_level=max(r.hierarchy_level for r in unique_roles),
                reports_to_role=unique_roles[0].role if unique_roles else None,
            ))

        return unique_roles

    def _estimate_cost(self, roles: List[EmployeeDefinition], analysis: TaskAnalysis) -> float:
        """Rough cost estimate based on number of roles × complexity."""
        base_cost_per_role = 0.05
        return len(roles) * base_cost_per_role * (1 + analysis.complexity.complexity_score)

    def _fallback_plan(self, analysis: TaskAnalysis) -> dict:
        """Minimal fallback plan if LLM fails."""
        complexity = analysis.complexity.complexity_score
        if complexity < 0.4:
            roles = [
                {
                    "role": "Task Specialist",
                    "objective": f"Complete the task: {analysis.user_input[:100]}",
                    "responsibilities": ["Understand requirements", "Execute task", "Deliver result"],
                    "skills": analysis.required_skills[:3],
                    "tools": analysis.required_tools[:2],
                    "quality_requirement": analysis.complexity.accuracy_requirement,
                    "hierarchy_level": 0,
                    "reports_to_role": None,
                }
            ]
            topology = "sequential"
        else:
            roles = [
                {
                    "role": "Project Lead",
                    "objective": "Coordinate and oversee all work",
                    "responsibilities": ["Plan work", "Coordinate team", "Review results"],
                    "skills": ["project management", "coordination"],
                    "tools": [],
                    "quality_requirement": 0.85,
                    "hierarchy_level": 0,
                    "reports_to_role": None,
                },
                {
                    "role": "Specialist",
                    "objective": f"Execute the core work: {analysis.user_input[:80]}",
                    "responsibilities": ["Research", "Execute", "Produce output"],
                    "skills": analysis.required_skills[:3],
                    "tools": analysis.required_tools[:3],
                    "quality_requirement": analysis.complexity.accuracy_requirement,
                    "hierarchy_level": 1,
                    "reports_to_role": "Project Lead",
                },
                {
                    "role": "Quality Reviewer",
                    "objective": "Review and validate all work",
                    "responsibilities": ["Review outputs", "Check accuracy", "Approve delivery"],
                    "skills": ["quality assurance", "verification"],
                    "tools": [],
                    "quality_requirement": 0.90,
                    "hierarchy_level": 1,
                    "reports_to_role": "Project Lead",
                },
            ]
            topology = "hierarchical"

        return {"topology": topology, "rationale": "Fallback plan", "roles": roles}
