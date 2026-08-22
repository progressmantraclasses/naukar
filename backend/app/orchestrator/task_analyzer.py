"""
Task Intelligence Engine — analyzes raw user input and extracts structured metadata.
Uses an LLM to understand: what the task is, what skills/tools are needed, complexity signals.
"""
import json
import structlog
from app.llm.registry import llm_registry
from app.llm.provider import LLMRequest, Message
from app.tasks.models import TaskAnalysis, ComplexityProfile
from app.core.config import settings

log = structlog.get_logger()

ANALYSIS_SYSTEM_PROMPT = """You are the Task Intelligence Engine for an Autonomous AI Workforce Platform.

Your job is to deeply analyze a user's task request and extract structured metadata.
Think like a senior project manager at a top consulting firm.

IMPORTANT: Return ONLY valid JSON. No markdown, no explanation.

The JSON must match this exact schema:
{
  "title": "Short descriptive title (max 80 chars)",
  "task_type": "e.g. Research+Report, Code+Debug, Analysis, Creative, Communication",
  "description": "What this task fundamentally requires (2-3 sentences)",
  "required_skills": ["skill1", "skill2", ...],
  "required_tools": ["web_search", "browser", "python", "file", etc.],
  "required_knowledge": ["domain1", "domain2", ...],
  "expected_output_format": "report|code|analysis|email|presentation|plan|summary|other",
  "complexity": {
    "complexity_score": 0.0-1.0,
    "risk_score": 0.0-1.0,
    "reasoning_requirement": 0.0-1.0,
    "research_requirement": 0.0-1.0,
    "tool_requirement": 0.0-1.0,
    "accuracy_requirement": 0.0-1.0
  },
  "estimated_workload_minutes": integer,
  "subtask_count_estimate": integer,
  "needs_research": true/false,
  "needs_review": true/false,
  "risk_level": "low|medium|high"
}

Scoring guidance:
- complexity_score: 0.1 = summarize a sentence, 0.5 = analyze a dataset, 0.9 = build a full system
- risk_score: potential for harm if wrong (financial advice = high, summarize text = low)
- reasoning_requirement: how much logical inference is needed
- research_requirement: how much external information gathering is needed
- tool_requirement: how many/complex tools are needed (0 = just LLM, 1 = many external tools)
- accuracy_requirement: how critical it is to be factually correct

Examples:
- "Summarize this text" → complexity=0.1, subtasks=1, needs_research=false
- "Create competitor analysis for SaaS" → complexity=0.7, subtasks=5-8, needs_research=true
- "Build a React website" → complexity=0.85, subtasks=6-10, needs_research=false, tool_requirement=0.8
"""


class TaskIntelligenceEngine:
    """Analyzes a user task and produces a structured TaskAnalysis."""

    def __init__(self):
        self._model = settings.MODEL_SMART  # groq/compound

    async def analyze(self, task_id: str, user_input: str) -> TaskAnalysis:
        log.info("task_analysis_started", task_id=task_id)

        request = LLMRequest(
            messages=[Message(role="user", content=f"Analyze this task:\n\n{user_input}")],
            model=self._model,
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=1500,
            json_mode=True,
            task_id=task_id,
        )

        provider = llm_registry.get_provider(self._model)
        response = await provider.generate(request)

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            log.error("task_analysis_json_error", raw=response.content[:200])
            data = self._fallback_analysis(user_input)

        complexity = ComplexityProfile(**data.get("complexity", {}))

        analysis = TaskAnalysis(
            task_id=task_id,
            user_input=user_input,
            title=data.get("title", user_input[:80]),
            task_type=data.get("task_type", "General"),
            description=data.get("description", ""),
            required_skills=data.get("required_skills", []),
            required_tools=data.get("required_tools", []),
            required_knowledge=data.get("required_knowledge", []),
            expected_output_format=data.get("expected_output_format", "report"),
            complexity=complexity,
            estimated_workload_minutes=data.get("estimated_workload_minutes", 15),
            subtask_count_estimate=data.get("subtask_count_estimate", 3),
            needs_research=data.get("needs_research", False),
            needs_review=data.get("needs_review", True),
            risk_level=data.get("risk_level", "low"),
        )

        log.info(
            "task_analysis_complete",
            task_id=task_id,
            complexity=complexity.complexity_score,
            subtasks=analysis.subtask_count_estimate,
            risk=analysis.risk_level,
        )
        return analysis

    def _fallback_analysis(self, user_input: str) -> dict:
        """Minimal fallback if JSON parsing fails."""
        length = len(user_input.split())
        complexity = min(0.3 + length / 200, 0.9)
        return {
            "title": user_input[:80],
            "task_type": "General",
            "description": "General task requiring AI assistance.",
            "required_skills": ["reasoning", "writing"],
            "required_tools": [],
            "required_knowledge": [],
            "expected_output_format": "report",
            "complexity": {
                "complexity_score": complexity,
                "risk_score": 0.2,
                "reasoning_requirement": complexity,
                "research_requirement": 0.3,
                "tool_requirement": 0.1,
                "accuracy_requirement": 0.7,
            },
            "estimated_workload_minutes": 10,
            "subtask_count_estimate": 2,
            "needs_research": False,
            "needs_review": False,
            "risk_level": "low",
        }
