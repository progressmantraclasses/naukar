"""Reusable role profiles used to create consistent task-scoped employees."""
from typing import Dict, Optional
from app.tasks.models import EmployeeDefinition


ROLE_CATALOG: Dict[str, EmployeeDefinition] = {
    "project lead": EmployeeDefinition(role="Project Lead", objective="Coordinate the team and deliver the task outcome.", responsibilities=["Clarify scope", "Sequence work", "Integrate results", "Manage risks"], skills=["project management", "requirements analysis", "prioritization", "decision making"], tools=["document editor"], quality_requirement=0.90, hierarchy_level=0),
    "research specialist": EmployeeDefinition(role="Research Specialist", objective="Collect relevant, current and well-supported information.", responsibilities=["Define research questions", "Gather evidence", "Compare sources", "Record assumptions"], skills=["research methodology", "source evaluation", "information synthesis", "fact checking"], tools=["web search", "browser"], quality_requirement=0.88, hierarchy_level=1, reports_to_role="Project Lead"),
    "market researcher": EmployeeDefinition(role="Market Researcher", objective="Assess market structure, demand and competitive conditions.", responsibilities=["Segment the market", "Estimate demand", "Identify trends", "Document sources"], skills=["market research", "market sizing", "trend analysis", "competitive intelligence"], tools=["web search", "spreadsheet"], quality_requirement=0.88, hierarchy_level=1, reports_to_role="Project Lead"),
    "competitive intelligence analyst": EmployeeDefinition(role="Competitive Intelligence Analyst", objective="Compare competitors and identify strategic advantages.", responsibilities=["Build competitor matrix", "Compare positioning", "Track differentiators", "Identify threats"], skills=["competitive analysis", "SWOT analysis", "pricing analysis", "strategic research"], tools=["web search", "spreadsheet"], quality_requirement=0.90, hierarchy_level=1, reports_to_role="Project Lead"),
    "data analyst": EmployeeDefinition(role="Data Analyst", objective="Transform raw information into accurate findings.", responsibilities=["Clean data", "Validate calculations", "Find patterns", "Explain limitations"], skills=["data cleaning", "quantitative analysis", "statistics", "insight generation"], tools=["spreadsheet", "python"], quality_requirement=0.90, hierarchy_level=1, reports_to_role="Project Lead"),
    "data scientist": EmployeeDefinition(role="Data Scientist", objective="Build rigorous models and derive evidence-based predictions.", responsibilities=["Prepare datasets", "Select methods", "Test assumptions", "Explain model confidence"], skills=["machine learning", "statistical modeling", "feature engineering", "model evaluation"], tools=["python", "notebook"], quality_requirement=0.92, hierarchy_level=1, reports_to_role="Project Lead"),
    "business analyst": EmployeeDefinition(role="Business Analyst", objective="Translate business needs into actionable analysis and requirements.", responsibilities=["Map processes", "Identify gaps", "Define acceptance criteria", "Recommend improvements"], skills=["business analysis", "process mapping", "requirements engineering", "stakeholder analysis"], tools=["document editor", "spreadsheet"], quality_requirement=0.88, hierarchy_level=1, reports_to_role="Project Lead"),
    "product strategist": EmployeeDefinition(role="Product Strategist", objective="Shape product direction around user and market value.", responsibilities=["Define product opportunities", "Prioritize outcomes", "Assess product-market fit", "Set strategic bets"], skills=["product strategy", "roadmapping", "customer discovery", "prioritization"], tools=["document editor", "spreadsheet"], quality_requirement=0.90, hierarchy_level=1, reports_to_role="Project Lead"),
    "product manager": EmployeeDefinition(role="Product Manager", objective="Convert user needs into a coherent product plan.", responsibilities=["Define goals", "Write requirements", "Prioritize backlog", "Align stakeholders"], skills=["product management", "user stories", "roadmapping", "prioritization"], tools=["document editor", "project tracker"], quality_requirement=0.88, hierarchy_level=1, reports_to_role="Project Lead"),
    "ux researcher": EmployeeDefinition(role="UX Researcher", objective="Understand user behavior, needs and usability barriers.", responsibilities=["Define research plan", "Analyze user needs", "Identify friction", "Summarize evidence"], skills=["user research", "interview analysis", "usability testing", "behavioral synthesis"], tools=["browser", "document editor"], quality_requirement=0.88, hierarchy_level=1, reports_to_role="Project Lead"),
    "ux designer": EmployeeDefinition(role="UX Designer", objective="Design clear and usable user experiences.", responsibilities=["Map user flows", "Create interaction concepts", "Resolve usability issues", "Specify states"], skills=["interaction design", "user flows", "information architecture", "usability"], tools=["design software", "document editor"], quality_requirement=0.88, hierarchy_level=1, reports_to_role="Product Manager"),
    "ui designer": EmployeeDefinition(role="UI Designer", objective="Create a consistent and accessible visual interface.", responsibilities=["Define visual hierarchy", "Choose typography", "Create component guidance", "Check accessibility"], skills=["visual design", "design systems", "typography", "accessibility"], tools=["design software"], quality_requirement=0.88, hierarchy_level=1, reports_to_role="Product Manager"),
    "content strategist": EmployeeDefinition(role="Content Strategist", objective="Plan content that supports audience and business goals.", responsibilities=["Define content pillars", "Map audience needs", "Set voice and tone", "Plan distribution"], skills=["content strategy", "audience analysis", "editorial planning", "brand voice"], tools=["document editor", "web search"], quality_requirement=0.86, hierarchy_level=1, reports_to_role="Project Lead"),
    "technical writer": EmployeeDefinition(role="Technical Writer", objective="Explain technical information clearly and accurately.", responsibilities=["Structure documentation", "Define terminology", "Write procedures", "Review for clarity"], skills=["technical writing", "information architecture", "editing", "developer documentation"], tools=["document editor"], quality_requirement=0.90, hierarchy_level=1, reports_to_role="Project Lead"),
    "copywriter": EmployeeDefinition(role="Copywriter", objective="Write concise persuasive copy for the intended audience.", responsibilities=["Clarify message", "Write drafts", "Match brand voice", "Improve calls to action"], skills=["copywriting", "persuasion", "editing", "brand voice"], tools=["document editor"], quality_requirement=0.84, hierarchy_level=1, reports_to_role="Project Lead"),
    "editor": EmployeeDefinition(role="Editor", objective="Improve structure, clarity, correctness and consistency.", responsibilities=["Edit structure", "Correct language", "Remove repetition", "Enforce style"], skills=["copy editing", "proofreading", "technical accuracy", "style guides"], tools=["document editor"], quality_requirement=0.92, hierarchy_level=1, reports_to_role="Project Lead"),
    "seo specialist": EmployeeDefinition(role="SEO Specialist", objective="Improve discoverability through search-focused content decisions.", responsibilities=["Research search intent", "Map keywords", "Recommend on-page structure", "Assess competition"], skills=["SEO", "keyword research", "search intent", "content optimization"], tools=["web search", "spreadsheet"], quality_requirement=0.86, hierarchy_level=1, reports_to_role="Content Strategist"),
    "software architect": EmployeeDefinition(role="Software Architect", objective="Design a maintainable and reliable technical solution.", responsibilities=["Define boundaries", "Evaluate tradeoffs", "Design interfaces", "Document decisions"], skills=["system architecture", "API design", "scalability", "technical decision making"], tools=["document editor", "diagramming tool"], quality_requirement=0.94, hierarchy_level=1, reports_to_role="Project Lead"),
    "backend engineer": EmployeeDefinition(role="Backend Engineer", objective="Implement reliable server-side behavior and integrations.", responsibilities=["Design services", "Implement APIs", "Handle errors", "Write tests"], skills=["backend development", "API design", "databases", "testing"], tools=["code editor", "terminal"], quality_requirement=0.92, hierarchy_level=1, reports_to_role="Software Architect"),
    "frontend engineer": EmployeeDefinition(role="Frontend Engineer", objective="Build accessible, responsive and maintainable interfaces.", responsibilities=["Implement components", "Manage state", "Handle loading and errors", "Test interactions"], skills=["frontend development", "React", "accessibility", "responsive design"], tools=["code editor", "browser", "terminal"], quality_requirement=0.92, hierarchy_level=1, reports_to_role="Software Architect"),
    "full stack engineer": EmployeeDefinition(role="Full Stack Engineer", objective="Deliver cohesive end-to-end product functionality.", responsibilities=["Implement UI", "Implement services", "Connect data flows", "Verify integration"], skills=["full stack development", "API integration", "databases", "testing"], tools=["code editor", "terminal", "browser"], quality_requirement=0.92, hierarchy_level=1, reports_to_role="Software Architect"),
    "qa engineer": EmployeeDefinition(role="QA Engineer", objective="Verify that the solution behaves correctly and reliably.", responsibilities=["Write test cases", "Exercise edge cases", "Report defects", "Verify fixes"], skills=["quality assurance", "test planning", "regression testing", "bug analysis"], tools=["browser", "terminal"], quality_requirement=0.92, hierarchy_level=1, reports_to_role="Project Lead"),
    "security analyst": EmployeeDefinition(role="Security Analyst", objective="Identify and reduce security risks in the proposed solution.", responsibilities=["Threat model", "Review access control", "Check data handling", "Recommend mitigations"], skills=["security analysis", "threat modeling", "OWASP", "risk assessment"], tools=["code editor", "terminal"], quality_requirement=0.95, hierarchy_level=1, reports_to_role="Software Architect"),
    "devops engineer": EmployeeDefinition(role="DevOps Engineer", objective="Make delivery, deployment and operations dependable.", responsibilities=["Define environments", "Automate delivery", "Add observability", "Plan recovery"], skills=["CI/CD", "cloud infrastructure", "containers", "observability"], tools=["terminal", "code editor"], quality_requirement=0.90, hierarchy_level=1, reports_to_role="Software Architect"),
    "database engineer": EmployeeDefinition(role="Database Engineer", objective="Design efficient, consistent and recoverable data storage.", responsibilities=["Model data", "Optimize queries", "Define migrations", "Plan backup strategy"], skills=["database design", "SQL", "data integrity", "performance tuning"], tools=["terminal", "database client"], quality_requirement=0.93, hierarchy_level=1, reports_to_role="Software Architect"),
    "financial analyst": EmployeeDefinition(role="Financial Analyst", objective="Evaluate costs, economics and financial implications.", responsibilities=["Build assumptions", "Model scenarios", "Check calculations", "Explain sensitivity"], skills=["financial modeling", "unit economics", "forecasting", "sensitivity analysis"], tools=["spreadsheet"], quality_requirement=0.94, hierarchy_level=1, reports_to_role="Project Lead"),
    "legal analyst": EmployeeDefinition(role="Legal Analyst", objective="Identify legal considerations and areas needing professional counsel.", responsibilities=["Identify obligations", "Summarize risks", "Compare options", "Flag uncertainty"], skills=["legal research", "contract analysis", "compliance", "risk communication"], tools=["web search", "document editor"], quality_requirement=0.95, hierarchy_level=1, reports_to_role="Project Lead"),
    "operations specialist": EmployeeDefinition(role="Operations Specialist", objective="Design practical processes for repeatable execution.", responsibilities=["Map workflows", "Define handoffs", "Identify bottlenecks", "Write procedures"], skills=["operations management", "process improvement", "SOP writing", "capacity planning"], tools=["document editor", "spreadsheet"], quality_requirement=0.86, hierarchy_level=1, reports_to_role="Project Lead"),
    "project coordinator": EmployeeDefinition(role="Project Coordinator", objective="Keep work organized, visible and on schedule.", responsibilities=["Track actions", "Coordinate handoffs", "Maintain status", "Escalate blockers"], skills=["coordination", "scheduling", "documentation", "follow-through"], tools=["project tracker", "document editor"], quality_requirement=0.84, hierarchy_level=1, reports_to_role="Project Lead"),
    "presentation designer": EmployeeDefinition(role="Presentation Designer", objective="Turn findings into a clear and persuasive visual narrative.", responsibilities=["Structure slides", "Create visual hierarchy", "Select charts", "Ensure consistency"], skills=["presentation design", "data storytelling", "visual hierarchy", "information design"], tools=["presentation software", "design software"], quality_requirement=0.90, hierarchy_level=1, reports_to_role="Project Lead"),
    "communications specialist": EmployeeDefinition(role="Communications Specialist", objective="Adapt information into clear audience-appropriate communication.", responsibilities=["Define audience", "Choose message hierarchy", "Draft communication", "Check tone"], skills=["business communication", "audience adaptation", "editing", "message framing"], tools=["document editor"], quality_requirement=0.86, hierarchy_level=1, reports_to_role="Project Lead"),
    "fact checker": EmployeeDefinition(role="Fact Checker", objective="Verify claims, sources and numerical statements before delivery.", responsibilities=["Trace claims", "Check source quality", "Validate numbers", "Record uncertainty"], skills=["fact checking", "source verification", "citation review", "critical thinking"], tools=["web search", "spreadsheet"], quality_requirement=0.95, hierarchy_level=1, reports_to_role="Project Lead"),
    "quality reviewer": EmployeeDefinition(role="Quality Reviewer", objective="Independently validate completeness, accuracy and presentation quality.", responsibilities=["Review against requirements", "Find gaps", "Check reasoning", "Approve or request changes"], skills=["quality assurance", "critical review", "requirements validation", "attention to detail"], tools=["document editor"], quality_requirement=0.95, hierarchy_level=1, reports_to_role="Project Lead"),
}


def get_role_profile(role: str) -> Optional[EmployeeDefinition]:
    """Return a copy of the canonical profile for an exact or close role name."""
    key = " ".join(role.lower().strip().split())
    profile = ROLE_CATALOG.get(key)
    if profile:
        return profile.model_copy(deep=True)
    for catalog_key, candidate in ROLE_CATALOG.items():
        if catalog_key in key or key in catalog_key:
            return candidate.model_copy(deep=True)
    return None


def apply_role_profile(definition: EmployeeDefinition) -> EmployeeDefinition:
    """Keep task-specific wording while enforcing canonical role capabilities."""
    profile = get_role_profile(definition.role)
    if not profile:
        return definition
    definition.role = profile.role
    definition.responsibilities = profile.responsibilities
    definition.skills = profile.skills
    definition.tools = profile.tools
    definition.quality_requirement = max(definition.quality_requirement, profile.quality_requirement)
    if definition.hierarchy_level == 0 and profile.hierarchy_level > 0:
        definition.hierarchy_level = profile.hierarchy_level
    if not definition.reports_to_role:
        definition.reports_to_role = profile.reports_to_role
    if not definition.objective or definition.objective == "Execute step":
        definition.objective = profile.objective
    return definition


def role_playbook(role: str) -> str:
    """Build concise role-specific operating instructions for an LLM employee."""
    profile = get_role_profile(role)
    if not profile:
        return "Use the assigned objective and responsibilities as the operating guide."

    skills = ", ".join(profile.skills)
    responsibilities = "\n".join(f"- {item}" for item in profile.responsibilities)
    return (
        f"Role capability focus: {skills}\n"
        f"Required working responsibilities:\n{responsibilities}\n"
        "Use the capability focus to make decisions, explain assumptions, "
        "and produce evidence for each important conclusion."
    )
