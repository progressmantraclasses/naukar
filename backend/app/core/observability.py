"""Low-overhead process metrics for operational feedback and cost tuning."""
from collections import defaultdict
from threading import Lock


class Metrics:
    def __init__(self):
        self._values = defaultdict(float)
        self._lock = Lock()

    def increment(self, name: str, value: float = 1.0):
        with self._lock:
            self._values[name] += value

    def observe(self, name: str, value: float):
        self.increment(f"{name}_sum", value)
        self.increment(f"{name}_count")

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            result = dict(self._values)
        if result.get("llm_requests_total"):
            result["average_cost_per_request"] = result.get("llm_cost_total", 0) / result["llm_requests_total"]
            result["average_latency"] = result.get("llm_latency_sum", 0) / result["llm_latency_count"]
        if result.get("llm_requests_total"):
            result["cache_hit_rate"] = result.get("cache_hits_total", 0) / result["llm_requests_total"]
            result["semantic_cache_hit_rate"] = result.get("semantic_cache_hits_total", 0) / result["llm_requests_total"]
        return result


metrics = Metrics()
