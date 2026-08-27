"""Live smoke test: browse real competitor sites (free tier) without any LLM call.
Uses a task that already names competitors so discovery needs 0 LLM tokens.
Tolerant of network failures — prints what it gathered.
"""
import asyncio

from app.tools.competitor_scout import CompetitorScout


async def main():
    user_input = "competitor analysis for Slack vs Microsoft Teams"
    scout = CompetitorScout(task_id="smoke-test")
    scan = await scout.run(user_input)

    print("=== SMOKE TEST RESULT ===")
    print("own_product:", scan.own_product)
    print("competitors found:", [c.name for c in scan.competitors])
    print("sites_browsed:", scan.sites_browsed)
    print("llm_calls_used:", scan.llm_calls_used)
    print("latency_ms:", scan.latency_ms)
    for c in scan.competitors:
        print(
            f"- {c.name}: sites={c.sites_checked} pricing={c.pricing[:3]} "
            f"features={c.features[:4]} website={c.website}"
        )
    print("--- MATRIX ---")
    print(scan.matrix_md or "(empty)")

    # Discovery path: no competitors named -> exactly 1 tiny LLM call
    names_only = await CompetitorScout(task_id="smoke-discovery")._discover_via_llm(
        "competition analysis for a project management SaaS startup"
    )
    print("=== DISCOVERY PATH ===")
    print("discovered:", names_only)
    print("=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
