"""
DynamicModelRouter — selects the optimal model for each task step.
Uses complexity, role, accuracy requirement, and historical performance metrics.
Implements model cascade: cheapest capable → escalate if fail.
"""
import structlog
from typing import Optional
from app.tasks.models import TaskStep, Employee, TaskAnalysis
from app.core.config import settings

log = structlog.get_logger()

# Ordered from cheapest/fastest to most capable/expensive
MODEL_CASCADE = [
    "groq/compound-mini",
    "groq/compound",
]

# Role → preferred model tier (0=fast, 1=smart, 2=heavy)
ROLE_TIER_HINTS = {
    "reviewer": 1,
    "quality": 1,
    "analyst": 1,
    "researcher": 0,
    "writer": 0,
    "manager": 1,
    "lead": 1,
    "director": 1,
    "engineer": 1,
    "architect": 2,
    "strategist": 1,
    "specialist": 0,
}


def _role_tier(role: str) -> int:
    """Get model tier hint based on role name keywords."""
    role_lower = role.lower()
    for keyword, tier in ROLE_TIER_HINTS.items():
        if keyword in role_lower:
            return tier
    return 0  # default: fast model


class DynamicModelRouter:
    """
    Selects the right model for a given employee + task step.
    
    Priority:
    1. Quality requirement (high → smarter model)
    2. Reasoning requirement
    3. Role hints
    4. Complexity score
    5. Historical performance (future: query model_metrics table)
    """

    def select_model(
        self,
        employee: Employee,
        step: TaskStep,
        analysis: TaskAnalysis,
        attempt: int = 0,
        tools_required: bool = False,
    ) -> str:
        """
        Select model for this step execution attempt.
        attempt=0 → cheapest capable, attempt=1 → next tier, etc.
        """
        # Cascade index = max of all signals + attempt
        base_tier = self._compute_base_tier(employee, step, analysis)
        if tools_required:
            # groq/compound-mini rejects tool schemas with HTTP 400 —
            # never send MCP tool calls to a non-tool-calling model.
            base_tier = max(base_tier, 1)
        cascade_index = min(base_tier + attempt, len(MODEL_CASCADE) - 1)
        model = MODEL_CASCADE[cascade_index]

        log.debug(
            "model_selected",
            role=employee.role,
            model=model,
            base_tier=base_tier,
            attempt=attempt,
            quality_req=step.quality_threshold,
        )
        return model

    def _compute_base_tier(
        self,
        employee: Employee,
        step: TaskStep,
        analysis: TaskAnalysis,
    ) -> int:
        """
        Return 0 (fast), 1 (smart), 2 (heavy) based on multiple signals.
        """
        signals = []

        # Quality requirement
        q = step.quality_threshold
        if q >= 0.90:
            signals.append(1)
        elif q >= 0.75:
            signals.append(0)
        else:
            signals.append(0)

        # Reasoning requirement
        r = analysis.complexity.reasoning_requirement
        if r >= 0.75:
            signals.append(1)
        elif r >= 0.50:
            signals.append(0)

        # Research / tool complexity
        t = analysis.complexity.tool_requirement
        if t >= 0.70:
            signals.append(1)

        # Overall complexity
        c = analysis.complexity.complexity_score
        if c >= 0.80:
            signals.append(1)
        elif c >= 0.50:
            signals.append(0)

        # Role hint
        signals.append(_role_tier(employee.role))

        # Risk
        if analysis.risk_level == "high":
            signals.append(1)

        # Take the max signal
        return max(signals) if signals else 0

    def next_cascade_model(self, current_model: str) -> Optional[str]:
        """Get the next model in the cascade (for retries on quality failure)."""
        try:
            idx = MODEL_CASCADE.index(current_model)
            if idx + 1 < len(MODEL_CASCADE):
                return MODEL_CASCADE[idx + 1]
        except ValueError:
            pass
        return None  # already at the top of cascade
