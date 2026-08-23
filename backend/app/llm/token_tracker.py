"""
TokenTracker — centralized token usage tracking per task.
Tracks every LLM call: model, tokens, cost, latency.
Emits TOKEN_USAGE events to the frontend.
Prints beautiful formatted boxes to the terminal.
"""
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import structlog

log = structlog.get_logger()

# ANSI colors for terminal output
_C = {
    "cyan":    "\033[96m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "magenta": "\033[95m",
    "blue":    "\033[94m",
    "red":     "\033[91m",
    "white":   "\033[97m",
    "dim":     "\033[2m",
    "bold":    "\033[1m",
    "reset":   "\033[0m",
}

_BOX_WIDTH = 58


@dataclass
class TokenUsageEntry:
    task_id: str
    step_label: str            # e.g. "Task Analysis", "Step 1: Research Market"
    model: str
    source: str                # "llm" | "cache" | "web"
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    timestamp: float = field(default_factory=time.time)
    web_sites_checked: int = 0
    web_sites_used: int = 0
    tokens_saved_by_web: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


@dataclass
class TokenSummary:
    task_id: str
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    cache_hits: int = 0
    llm_calls: int = 0
    web_searches: int = 0
    web_sites_checked: int = 0
    tokens_saved_by_web: int = 0
    entries: List[TokenUsageEntry] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def avg_latency_ms(self) -> int:
        if self.llm_calls == 0:
            return 0
        return self.total_latency_ms // max(self.llm_calls, 1)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "cache_hits": self.cache_hits,
            "llm_calls": self.llm_calls,
            "web_searches": self.web_searches,
            "web_sites_checked": self.web_sites_checked,
            "tokens_saved_by_web": self.tokens_saved_by_web,
            "entries": [e.to_dict() for e in self.entries],
        }


def _fmt_cost(usd: float) -> str:
    if usd == 0.0:
        return "$0.000000"
    return f"${usd:.6f}"


def _fmt_tokens(n: int) -> str:
    return f"{n:,}"


def _print_token_box(entry: TokenUsageEntry, cumulative: TokenSummary):
    """Print a beautiful formatted token usage box to terminal."""
    w = _BOX_WIDTH
    sep = "─" * w

    src_label = {
        "llm":   "🤖 LLM API Call",
        "cache": "⚡ Cache Hit (FREE)",
        "web":   "🌐 Web Search",
    }.get(entry.source, entry.source.upper())

    src_color = {"llm": "cyan", "cache": "green", "web": "magenta"}.get(entry.source, "white")

    def row(label: str, value: str, color: str = "white"):
        pad = w - len(label) - len(value)
        print(
            f"{_C['blue']}│{_C['reset']} "
            f"{_C['dim']}{label}{_C['reset']}"
            f"{' ' * max(pad, 1)}"
            f"{_C[color]}{_C['bold']}{value}{_C['reset']}"
            f" {_C['blue']}│{_C['reset']}"
        )

    print(f"\n{_C['blue']}{_C['bold']}┌─ TOKEN USAGE {'─' * (w - 14)}┐{_C['reset']}")
    step_label = entry.step_label[:w - 2]
    print(
        f"{_C['blue']}│{_C['reset']} "
        f"{_C['bold']}{_C['white']}{step_label:<{w - 2}}{_C['reset']}"
        f"{_C['blue']}│{_C['reset']}"
    )
    print(f"{_C['blue']}├{sep}┤{_C['reset']}")

    row("Model", entry.model, "cyan")
    row("Source", src_label, src_color)

    if entry.web_sites_checked > 0:
        row("Web Sites Checked", str(entry.web_sites_checked), "magenta")
        row("Web Sites Used", str(entry.web_sites_used), "magenta")
        row("Tokens Saved (web)", f"~{_fmt_tokens(entry.tokens_saved_by_web)}", "green")

    print(f"{_C['blue']}├{sep}┤{_C['reset']}")
    row("Prompt Tokens", _fmt_tokens(entry.prompt_tokens), "yellow")
    row("Completion Tokens", _fmt_tokens(entry.completion_tokens), "yellow")
    row("Total Tokens", _fmt_tokens(entry.total_tokens), "white")
    row("Cost (this call)", _fmt_cost(entry.cost_usd), "green")
    row("Latency", f"{entry.latency_ms}ms", "blue")

    print(f"{_C['blue']}├{sep}┤{_C['reset']}")
    row("── Cumulative ──────────", "", "dim")
    row("Total Tokens", _fmt_tokens(cumulative.total_tokens), "white")
    row("Total Cost", _fmt_cost(cumulative.total_cost_usd), "green")
    row("LLM Calls", str(cumulative.llm_calls), "cyan")
    row("Cache Hits", str(cumulative.cache_hits), "green")
    row("Web Searches", str(cumulative.web_searches), "magenta")

    print(f"{_C['blue']}└{'─' * w}┘{_C['reset']}\n")


class TokenTracker:
    """
    Singleton token usage tracker.
    Accumulates per task_id. Prints terminal boxes. Returns summaries.
    """

    def __init__(self):
        self._summaries: Dict[str, TokenSummary] = {}

    def _get_summary(self, task_id: str) -> TokenSummary:
        if task_id not in self._summaries:
            self._summaries[task_id] = TokenSummary(task_id=task_id)
        return self._summaries[task_id]

    def record(
        self,
        task_id: str,
        step_label: str,
        model: str,
        source: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        latency_ms: int,
        web_sites_checked: int = 0,
        web_sites_used: int = 0,
        tokens_saved_by_web: int = 0,
    ) -> TokenUsageEntry:
        """Record a token usage event and update cumulative summary."""
        entry = TokenUsageEntry(
            task_id=task_id,
            step_label=step_label,
            model=model,
            source=source,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            web_sites_checked=web_sites_checked,
            web_sites_used=web_sites_used,
            tokens_saved_by_web=tokens_saved_by_web,
        )

        summary = self._get_summary(task_id)
        summary.entries.append(entry)
        summary.total_prompt_tokens += prompt_tokens
        summary.total_completion_tokens += completion_tokens
        summary.total_cost_usd += cost_usd
        summary.total_latency_ms += latency_ms
        summary.web_sites_checked += web_sites_checked
        summary.tokens_saved_by_web += tokens_saved_by_web

        if source == "cache":
            summary.cache_hits += 1
        elif source == "web":
            summary.web_searches += 1
        else:
            summary.llm_calls += 1

        # Print terminal box
        _print_token_box(entry, summary)

        return entry

    def get_summary(self, task_id: str) -> Optional[TokenSummary]:
        return self._summaries.get(task_id)

    def get_entries(self, task_id: str) -> List[TokenUsageEntry]:
        s = self._summaries.get(task_id)
        return s.entries if s else []

    def reset(self, task_id: str):
        self._summaries.pop(task_id, None)

    def print_final_summary(self, task_id: str):
        """Print a final cumulative summary after task completes."""
        s = self._summaries.get(task_id)
        if not s:
            return
        w = _BOX_WIDTH + 4
        print(f"\n{_C['green']}{_C['bold']}{'═' * w}{_C['reset']}")
        print(f"{_C['green']}{_C['bold']}  TASK COMPLETE — TOKEN SUMMARY{_C['reset']}")
        print(f"{_C['green']}{_C['bold']}{'═' * w}{_C['reset']}")
        print(f"  Total Tokens Used  : {_C['yellow']}{_C['bold']}{_fmt_tokens(s.total_tokens)}{_C['reset']}")
        print(f"  Total Cost (USD)   : {_C['green']}{_C['bold']}{_fmt_cost(s.total_cost_usd)}{_C['reset']}")
        print(f"  LLM API Calls      : {_C['cyan']}{s.llm_calls}{_C['reset']}")
        print(f"  Cache Hits         : {_C['green']}{s.cache_hits}{_C['reset']}")
        print(f"  Web Searches       : {_C['magenta']}{s.web_searches}{_C['reset']}")
        print(f"  Web Sites Checked  : {_C['magenta']}{s.web_sites_checked}{_C['reset']}")
        print(f"  Tokens Saved (Web) : {_C['green']}{_fmt_tokens(s.tokens_saved_by_web)}{_C['reset']}")
        print(f"  Avg Latency/Call   : {_C['blue']}{s.avg_latency_ms}ms{_C['reset']}")
        print(f"{_C['green']}{_C['bold']}{'═' * w}{_C['reset']}\n")


# Global singleton
token_tracker = TokenTracker()
