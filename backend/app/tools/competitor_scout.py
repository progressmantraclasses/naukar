"""
CompetitorScout — token-minimal web browsing tool for competition analysis.

Design principle: browsing and data extraction cost ZERO tokens.
- Free DuckDuckGo search + page scraping (via SmartWebSearcher, tier 1)
- Deterministic regex/heuristic extraction of pricing, features, pros/cons
- The only LLM spend happens later: 1 tiny competitor-discovery call (only if
  competitor names are not present in the user input) + 1 synthesis call.

Usage:
    scout = CompetitorScout(task_id, on_progress=callback)
    scan = await scout.run("competitor analysis for my CRM vs HubSpot")
    # scan.matrix_md → deterministic markdown competitor matrix
"""
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, List, Optional
from urllib.parse import urlparse

import structlog

from app.core.config import settings
from app.tools.web_searcher import smart_web_searcher

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Task detection (deterministic — no LLM call)
# ---------------------------------------------------------------------------
_COMPETITION_SIGNALS = (
    "competitor", "competition", "competitive analysis", "competitive landscape",
    "market comparison", "alternatives to", "alternatives for", " vs ", " vs.",
    "versus", "compare", "rivals", "benchmark against", "market landscape",
)


def is_competition_task(user_input: str) -> bool:
    """Cheap keyword check to route a task to the Competition Scout fast path."""
    text = f" {user_input.lower()} "
    return any(sig in text for sig in _COMPETITION_SIGNALS)


# ---------------------------------------------------------------------------
# Deterministic name extraction from the user's own request
# ---------------------------------------------------------------------------
_NAME_RE = r"[A-Za-z0-9][A-Za-z0-9 .+\-&]{1,40}"
_STOPWORD_SPLIT_RE = re.compile(
    r"\s+(?:vs\.?|versus|and|with|to|for|against|or|compared)\s+", re.I
)


def _clean_name(name: str) -> str:
    name = _STOPWORD_SPLIT_RE.split(name.strip())[0].strip()
    return re.sub(r"[.,;:!?\)\(]+$", "", name).strip()


def extract_named_competitors(user_input: str) -> tuple[Optional[str], List[str]]:
    """
    Pull competitor names out of the user text with regex.
    Returns (own_product, competitor_names). Zero tokens spent.
    """
    text = user_input.strip()
    raw: List[str] = []
    own: Optional[str] = None

    # Own product first: "for my SaaS X" / "my product X"
    m = re.search(
        rf"(?:for\s+)?(?:my|our)\s+(?:product|app|saas|startup|tool|platform|"
        rf"company|crm|project|business|service)\s+(?:called\s+)?({_NAME_RE})",
        text, re.I,
    )
    if m:
        own = _clean_name(m.group(1)) or None

    # Quoted names: "HubSpot", 'Zoho'
    raw += re.findall(r'"([^"]{2,40})"', text)
    raw += re.findall(r"'([A-Z][^']{1,39})'", text)

    # alternatives to X / alternatives for X
    for m in re.finditer(rf"alternatives?\s+(?:to|for)\s+({_NAME_RE})", text, re.I):
        raw.append(m.group(1))

    # vs X / versus X
    for m in re.finditer(rf"\b(?:vs\.?|versus)\s+({_NAME_RE})", text, re.I):
        raw.append(m.group(1))

    # X vs Y — also capture the LEFT side: the last capitalized phrase right
    # before "vs". re.search (not finditer) so the match can't start mid-word.
    m = re.search(r"([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,2})\s+(?:vs\.?|versus)\b", text)
    if m:
        prefix = text[: m.start(1)].rstrip()
        if not re.search(r"\b(?:my|our)$", prefix, re.I):
            raw.append(m.group(1))

    # compare A vs B | compare A with B | compare A, B
    for m in re.finditer(
        rf"compare\s+({_NAME_RE}?)\s*(?:,|and|with|to|vs\.?|versus)\s+({_NAME_RE})",
        text, re.I,
    ):
        raw += [g for g in m.groups() if g]

    # "and Zoho" / ", Coda" style extra competitors in compare/vs contexts
    if re.search(r"\b(?:compare|vs\.?|versus|alternatives?|competitors?)\b", text, re.I):
        for m in re.finditer(rf"\band\s+({_NAME_RE})", text, re.I):
            raw.append(m.group(1))
        for m in re.finditer(rf",\s*(?:and\s+)?({_NAME_RE})", text, re.I):
            raw.append(m.group(1))

    names: List[str] = []
    seen = set()
    for candidate in raw:
        n = _clean_name(candidate)
        # "my X" / "our X" refers to the user's own product, never a competitor
        m2 = re.match(r"^(?:my|our)\s+(.+)$", n, re.I)
        if m2:
            if not own:
                own = m2.group(1).strip()
            continue
        key = n.lower()
        if len(n) < 2 or key in seen:
            continue
        if own and key == own.lower():
            continue
        seen.add(key)
        names.append(n)
    return own, names[:6]


# ---------------------------------------------------------------------------
# Deterministic fact extraction (regex + keyword counting — no tokens)
# ---------------------------------------------------------------------------
_PRICE_RE = re.compile(
    r"\$\s?\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?\s?(?:/\s?(?:mo|month|user|yr|year)\b"
    r"|\b(?:per month|per user|per year|a month|monthly|yearly|annually)\b)",
    re.I,
)
_FREE_RE = re.compile(r"\bfree\s+(?:trial|plan|tier|forever|version|to start)\b", re.I)

FEATURE_KEYWORDS = [
    "ai", "api", "analytics", "automation", "collaboration", "dashboard",
    "integrations", "mobile", "reporting", "security", "templates", "real-time",
    "cloud", "export", "customization", "workflows", "notifications",
    "scheduling", "payments", "crm", "chat", "onboarding",
]
POSITIVE_WORDS = [
    "easy", "intuitive", "powerful", "fast", "reliable", "affordable",
    "excellent", "robust", "flexible", "user-friendly", "seamless",
    "comprehensive", "well-designed", "responsive",
]
NEGATIVE_WORDS = [
    "expensive", "slow", "complex", "confusing", "limited", "buggy",
    "poor support", "lacks", "difficult", "steep learning curve",
    "overwhelming", "pricey", "outdated",
]


@dataclass
class CompetitorProfile:
    name: str
    website: str = ""
    pricing: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    sources: List[dict] = field(default_factory=list)  # [{url, title}]
    sites_checked: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "website": self.website,
            "pricing": self.pricing,
            "features": self.features,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "sources": self.sources[:6],
            "sites_checked": self.sites_checked,
        }


@dataclass
class CompetitionScanResult:
    user_input: str
    own_product: Optional[str] = None
    competitors: List[CompetitorProfile] = field(default_factory=list)
    matrix_md: str = ""
    sites_browsed: int = 0
    llm_calls_used: int = 0          # discovery call (0 or 1); synthesis is separate
    discovery_source: str = "input"  # "input" | "llm"
    estimated_tokens_saved: int = 0
    latency_ms: int = 0


def _extract_prices(text: str) -> List[str]:
    found = [re.sub(r"\s+", " ", p).strip() for p in _PRICE_RE.findall(text)]
    free = _FREE_RE.findall(text)
    seen, out = set(), []
    for p in found + [f.lower().strip() for f in free]:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
        if len(out) >= 6:
            break
    return out


def _extract_keywords(text: str, vocabulary: List[str], cap: int) -> List[str]:
    lower = text.lower()
    scored = []
    for kw in vocabulary:
        count = len(re.findall(rf"\b{re.escape(kw)}\b", lower))
        if count > 0:
            scored.append((count, kw))
    scored.sort(reverse=True)
    return [kw for _, kw in scored[:cap]]


def _most_common_domain(sources: List[dict]) -> str:
    counts: dict = {}
    for s in sources:
        try:
            host = urlparse(s.get("url", "")).netloc.lower()
            host = host.removeprefix("www.")
            if host:
                counts[host] = counts.get(host, 0) + 1
        except Exception:
            continue
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# Scout
# ---------------------------------------------------------------------------
ProgressCallback = Callable[[str, str, Optional[CompetitorProfile]], Awaitable[None]]


class CompetitorScout:
    """
    Browses the web for each competitor using the FREE search tier and builds
    a competitor matrix with deterministic extraction. No LLM tokens are spent
    inside this class except the optional tiny competitor-discovery call.
    """

    MAX_COMPETITORS = 5

    def __init__(self, task_id: str, on_progress: Optional[ProgressCallback] = None):
        self.task_id = task_id
        self._on_progress = on_progress

    async def run(self, user_input: str) -> CompetitionScanResult:
        start = time.monotonic()
        result = CompetitionScanResult(user_input=user_input)

        # ── 1. Discover competitor names (deterministic first) ─────────────
        own_product, names = extract_named_competitors(user_input)
        result.own_product = own_product

        if len(names) < 2:
            discovered = await self._discover_via_llm(user_input)
            if discovered:
                result.llm_calls_used += 1
                result.discovery_source = "llm"
                existing = {n.lower() for n in names}
                for d in discovered:
                    if d.lower() not in existing:
                        names.append(d)
                        existing.add(d.lower())

        names = names[: self.MAX_COMPETITORS]
        log.info(
            "competition_scout_targets",
            task_id=self.task_id,
            own=own_product,
            competitors=names,
            discovery=result.discovery_source,
        )
        if not names:
            result.latency_ms = int((time.monotonic() - start) * 1000)
            return result

        # ── 2. Browse every competitor in parallel (free tier) ─────────────
        profiles = await asyncio.gather(
            *(self._scan_competitor(name) for name in names),
            return_exceptions=True,
        )
        for p in profiles:
            if isinstance(p, CompetitorProfile):
                result.competitors.append(p)
                result.sites_browsed += p.sites_checked
                # Raw scraped text never reaches the LLM wholesale → tokens saved
                result.estimated_tokens_saved += 1200

        # ── 3. Build deterministic matrix ──────────────────────────────────
        result.matrix_md = self._build_matrix(result)
        result.latency_ms = int((time.monotonic() - start) * 1000)

        log.info(
            "competition_scan_complete",
            task_id=self.task_id,
            competitors=len(result.competitors),
            sites_browsed=result.sites_browsed,
            llm_calls_used=result.llm_calls_used,
            latency_ms=result.latency_ms,
        )
        return result

    async def _discover_via_llm(self, user_input: str) -> List[str]:
        """ONE tiny LLM call to name competitors — only when user didn't name them."""
        try:
            from app.llm.gateway import ai_gateway
            from app.llm.provider import LLMRequest, Message

            request = LLMRequest(
                messages=[Message(role="user", content=f"Task: {user_input[:400]}")],
                model=settings.MODEL_FAST,
                system_prompt=(
                    'Identify direct competitors for the task. Return ONLY JSON: '
                    '{"competitors": ["name1","name2","name3","name4"]}. '
                    'Pick the 4 most well-known direct competitors. No extra text.'
                ),
                temperature=0.2,
                max_tokens=120,
                json_mode=True,
                task_id=self.task_id,
                task_type="competition_discovery",
            )
            response = await ai_gateway.generate(request)
            data = json.loads(response.content)
            names = [str(n).strip() for n in data.get("competitors", []) if str(n).strip()]
            return names[:4]
        except Exception as exc:
            log.warning("competitor_discovery_llm_failed", error=str(exc))
            return []

    async def _scan_competitor(self, name: str) -> CompetitorProfile:
        """Browse pricing + review pages for one competitor using the free tier."""
        if self._on_progress:
            await self._on_progress(name, "browsing", None)

        profile = CompetitorProfile(name=name)
        texts: List[str] = []
        queries = [
            f"{name} pricing plans cost",
            f"{name} features review pros cons",
        ]
        for q in queries:
            res = await smart_web_searcher.search(q, min_sites=4, task_id=self.task_id)
            texts.append(res.text)
            profile.sources.extend(
                {"url": s.get("url", ""), "title": s.get("title", "")}
                for s in res.sources[:4]
            )
            profile.sites_checked += res.sites_checked
            try:
                await smart_web_searcher.emit_event(
                    task_id=self.task_id,
                    result=res,
                    step_label=f"Scout browsing: {name}",
                )
            except Exception:
                pass

        merged = "\n".join(t for t in texts if t)[:12000]
        profile.pricing = _extract_prices(merged)
        profile.features = _extract_keywords(merged, FEATURE_KEYWORDS, cap=6)
        profile.strengths = _extract_keywords(merged, POSITIVE_WORDS, cap=4)
        profile.weaknesses = _extract_keywords(merged, NEGATIVE_WORDS, cap=4)
        profile.website = _most_common_domain(profile.sources)

        if self._on_progress:
            await self._on_progress(name, "done", profile)
        return profile

    @staticmethod
    def _build_matrix(result: CompetitionScanResult) -> str:
        """Deterministic markdown competitor matrix — no LLM needed."""
        lines = [
            "| Competitor | Starting Pricing | Key Features | Strengths | Weaknesses | Sites Checked |",
            "|---|---|---|---|---|---|",
        ]
        for c in result.competitors:
            pricing = "; ".join(c.pricing[:3]) if c.pricing else "not found"
            features = ", ".join(c.features[:5]) if c.features else "—"
            strengths = ", ".join(c.strengths[:3]) if c.strengths else "—"
            weaknesses = ", ".join(c.weaknesses[:3]) if c.weaknesses else "—"
            lines.append(
                f"| {c.name} | {pricing} | {features} | {strengths} | {weaknesses} | {c.sites_checked} |"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic task analysis for the fast path (saves the analyzer LLM call)
# ---------------------------------------------------------------------------
def deterministic_competition_analysis(task_id: str, user_input: str):
    """Build a TaskAnalysis without any LLM call — competition tasks are well-known."""
    from app.tasks.models import TaskAnalysis, ComplexityProfile

    return TaskAnalysis(
        task_id=task_id,
        user_input=user_input,
        title=f"Competition Analysis: {user_input[:60].strip()}",
        task_type="Research+Competitive Analysis",
        description="Browse competitor websites, extract pricing and feature data, and deliver a competition analysis.",
        required_skills=["competitive analysis", "web research", "market intelligence"],
        required_tools=["web search", "browser"],
        required_knowledge=["competitor pricing", "feature comparison", "market positioning"],
        expected_output_format="report",
        complexity=ComplexityProfile(
            complexity_score=0.55,
            risk_score=0.20,
            reasoning_requirement=0.60,
            research_requirement=0.90,
            tool_requirement=0.60,
            accuracy_requirement=0.85,
        ),
        estimated_workload_minutes=20,
        subtask_count_estimate=1,
        needs_research=True,
        needs_review=True,
        risk_level="low",
    )
