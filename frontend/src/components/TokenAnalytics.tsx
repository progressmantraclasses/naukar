import React, { useMemo } from "react"
import { useTaskStore } from "../store/taskStore"
import type { TokenUsageEntry, WebSearchResult } from "../store/taskStore"

function fmtCost(usd: number): string {
  if (usd === 0) return "$0.000000"
  return "$" + usd.toFixed(6)
}
function fmtTokens(n: number): string {
  return n.toLocaleString()
}
function srcLabel(source: string): { label: string; color: string; bg: string } {
  switch (source) {
    case "cache": return { label: "Cache Hit", color: "#4ade80", bg: "rgba(74,222,128,0.12)" }
    case "web":   return { label: "Web Search", color: "#c084fc", bg: "rgba(192,132,252,0.12)" }
    default:      return { label: "LLM API",    color: "#38bdf8", bg: "rgba(56,189,248,0.12)" }
  }
}
function tierLabel(tier: string): string {
  if (tier === "ddg")    return "DuckDuckGo (Free)"
  if (tier === "tavily") return "Tavily API"
  return tier
}

function SummaryCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid " + color + "33", borderRadius: 14, padding: "18px 20px", minWidth: 150, flex: 1 }}>
      <div style={{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "#666", marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

function TokenBarChart({ entries }: { entries: TokenUsageEntry[] }) {
  const maxTokens = Math.max(...entries.map(e => e.total_tokens), 1)
  const colors: Record<string, string> = { cache: "#4ade80", web: "#c084fc", llm: "#38bdf8" }
  return (
    <div style={{ overflowX: "auto", paddingBottom: 4 }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 6, minWidth: entries.length * 40, height: 100 }}>
        {entries.map((e, i) => {
          const color = colors[e.source] || "#38bdf8"
          const h = Math.max(4, (e.total_tokens / maxTokens) * 90)
          return (
            <div key={i} title={e.step_label + "\n" + fmtTokens(e.total_tokens) + " tokens\n" + fmtCost(e.cost_usd)}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, minWidth: 32 }}>
              <div style={{ width: "100%", height: h, background: color, borderRadius: "4px 4px 0 0", opacity: 0.85 }} />
              <div style={{ fontSize: 9, color: "#555", marginTop: 2, textAlign: "center" }}>{i + 1}</div>
            </div>
          )
        })}
      </div>
      <div style={{ fontSize: 10, color: "#555", marginTop: 6, textAlign: "center" }}>Each bar = one LLM call (hover for details)</div>
    </div>
  )
}

function StepTable({ entries }: { entries: TokenUsageEntry[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ background: "rgba(255,255,255,0.04)", color: "#888" }}>
            {["#", "Step", "Model", "Source", "Prompt", "Completion", "Total", "Cost", "Latency"].map(h => (
              <th key={h} style={{ padding: "8px 10px", textAlign: "left", borderBottom: "1px solid #222", whiteSpace: "nowrap" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => {
            const src = srcLabel(e.source)
            return (
              <tr key={i} style={{ borderBottom: "1px solid #1a1a2e" }}>
                <td style={{ padding: "7px 10px", color: "#555" }}>{i + 1}</td>
                <td style={{ padding: "7px 10px", color: "#ccc", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.step_label}</td>
                <td style={{ padding: "7px 10px", color: "#38bdf8", fontSize: 11 }}>{e.model}</td>
                <td style={{ padding: "7px 10px" }}>
                  <span style={{ background: src.bg, color: src.color, padding: "2px 8px", borderRadius: 20, fontSize: 11, fontWeight: 600 }}>{src.label}</span>
                </td>
                <td style={{ padding: "7px 10px", color: "#fbbf24", fontVariantNumeric: "tabular-nums" }}>{fmtTokens(e.prompt_tokens)}</td>
                <td style={{ padding: "7px 10px", color: "#fbbf24", fontVariantNumeric: "tabular-nums" }}>{fmtTokens(e.completion_tokens)}</td>
                <td style={{ padding: "7px 10px", color: "#fff", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{fmtTokens(e.total_tokens)}</td>
                <td style={{ padding: "7px 10px", color: "#4ade80", fontVariantNumeric: "tabular-nums" }}>{fmtCost(e.cost_usd)}</td>
                <td style={{ padding: "7px 10px", color: "#60a5fa" }}>{e.latency_ms}ms</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function WebSearchPanel({ results }: { results: WebSearchResult[] }) {
  if (results.length === 0) {
    return <div style={{ color: "#555", padding: "20px", textAlign: "center", fontSize: 13 }}>No web searches performed for this task.</div>
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {results.map((r, i) => (
        <div key={i} style={{ background: "rgba(192,132,252,0.06)", border: "1px solid rgba(192,132,252,0.2)", borderRadius: 12, padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 3 }}>{r.step_label}</div>
              <div style={{ color: "#e2e8f0", fontWeight: 600, fontSize: 13 }}>"{r.query}"</div>
            </div>
            <span style={{ background: r.is_sufficient ? "rgba(74,222,128,0.15)" : "rgba(251,191,36,0.15)", color: r.is_sufficient ? "#4ade80" : "#fbbf24", padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600 }}>
              {r.is_sufficient ? "Sufficient" : "Partial"}
            </span>
          </div>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginBottom: 10 }}>
            {([["Tier", tierLabel(r.tier_used), "#c084fc"], ["Sites Checked", String(r.sites_checked), "#38bdf8"], ["Sites Used", String(r.sites_used), "#4ade80"], ["Tokens Saved", "~" + fmtTokens(r.estimated_tokens_saved), "#fbbf24"], ["Latency", r.latency_ms + "ms", "#60a5fa"]] as [string, string, string][]).map(([label, val, clr]) => (
              <div key={label}>
                <div style={{ fontSize: 10, color: "#666", textTransform: "uppercase", marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 13, color: clr, fontWeight: 600 }}>{val}</div>
              </div>
            ))}
          </div>
          {r.sources.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 6 }}>Sources checked:</div>
              {r.sources.slice(0, 5).map((s, j) => (
                <div key={j} style={{ fontSize: 11, color: "#888", background: "rgba(255,255,255,0.03)", padding: "4px 8px", borderRadius: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginBottom: 3 }}>
                  <span style={{ color: "#c084fc", marginRight: 6 }}>{j + 1}.</span>
                  <a href={s.url} target="_blank" rel="noreferrer" style={{ color: "#888", textDecoration: "none" }} title={s.snippet}>{s.title || s.url}</a>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: "#888", textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 14, paddingBottom: 8, borderBottom: "1px solid #1f1f2e" }}>{title}</div>
      {children}
    </div>
  )
}

export function TokenAnalytics() {
  const { tokenUsage, webSearchResults, tokenSummary } = useTaskStore()

  const summary = useMemo(() => {
    if (tokenSummary) return tokenSummary
    let prompt = 0, completion = 0, cost = 0, latency = 0, llm = 0, cache = 0
    for (const e of tokenUsage) {
      prompt += e.prompt_tokens; completion += e.completion_tokens
      cost += e.cost_usd; latency += e.latency_ms
      if (e.source === "cache") cache++; else llm++
    }
    return {
      total_prompt_tokens: prompt, total_completion_tokens: completion, total_tokens: prompt + completion,
      total_cost_usd: cost, avg_latency_ms: llm > 0 ? Math.round(latency / llm) : 0,
      cache_hits: cache, llm_calls: llm,
      web_searches: webSearchResults.length,
      web_sites_checked: webSearchResults.reduce((s, r) => s + r.sites_checked, 0),
      tokens_saved_by_web: webSearchResults.reduce((s, r) => s + r.estimated_tokens_saved, 0),
    }
  }, [tokenUsage, webSearchResults, tokenSummary])

  if (tokenUsage.length === 0 && webSearchResults.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#555", gap: 12 }}>
        <div style={{ fontSize: 40 }}>📊</div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>No analytics yet</div>
        <div style={{ fontSize: 13 }}>Run a task to see token usage data here.</div>
      </div>
    )
  }

  return (
    <div style={{ height: "100%", overflowY: "auto", padding: "28px 32px", fontFamily: "Inter, system-ui, sans-serif", color: "#e2e8f0" }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#fff", marginBottom: 4 }}>Token Analytics</div>
        <div style={{ fontSize: 13, color: "#666" }}>Per-step breakdown of AI token usage, costs, and web search activity</div>
      </div>

      <Section title="Task Summary">
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          <SummaryCard label="Total Tokens" value={fmtTokens(summary.total_tokens)} sub={fmtTokens(summary.total_prompt_tokens) + " in · " + fmtTokens(summary.total_completion_tokens) + " out"} color="#fbbf24" />
          <SummaryCard label="Total Cost" value={fmtCost(summary.total_cost_usd)} sub="USD (estimated)" color="#4ade80" />
          <SummaryCard label="LLM Calls" value={String(summary.llm_calls)} sub={summary.cache_hits + " cache hits"} color="#38bdf8" />
          <SummaryCard label="Avg Latency" value={summary.avg_latency_ms + "ms"} sub="per LLM call" color="#60a5fa" />
          <SummaryCard label="Web Searches" value={String(summary.web_searches)} sub={summary.web_sites_checked + " sites checked"} color="#c084fc" />
          <SummaryCard label="Tokens Saved" value={"~" + fmtTokens(summary.tokens_saved_by_web)} sub="via web search" color="#f472b6" />
        </div>
      </Section>

      {tokenUsage.length > 0 && (
        <Section title="Token Usage Per Call">
          <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid #1f1f2e", borderRadius: 12, padding: 18 }}>
            <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 11 }}>
              {[{ label: "LLM Call", color: "#38bdf8" }, { label: "Cache Hit", color: "#4ade80" }, { label: "Web", color: "#c084fc" }].map(({ label, color }) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
                  <span style={{ color: "#888" }}>{label}</span>
                </div>
              ))}
            </div>
            <TokenBarChart entries={tokenUsage} />
          </div>
        </Section>
      )}

      {tokenUsage.length > 0 && (
        <Section title="Per-Call Breakdown">
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid #1f1f2e", borderRadius: 12, overflow: "hidden" }}>
            <StepTable entries={tokenUsage} />
          </div>
          <div style={{ marginTop: 10, display: "flex", gap: 24, flexWrap: "wrap", padding: "12px 16px", background: "rgba(251,191,36,0.05)", border: "1px solid rgba(251,191,36,0.15)", borderRadius: 10, fontSize: 12 }}>
            <div><span style={{ color: "#666" }}>Prompt total: </span><span style={{ color: "#fbbf24", fontWeight: 600 }}>{fmtTokens(summary.total_prompt_tokens)}</span></div>
            <div><span style={{ color: "#666" }}>Completion total: </span><span style={{ color: "#fbbf24", fontWeight: 600 }}>{fmtTokens(summary.total_completion_tokens)}</span></div>
            <div><span style={{ color: "#666" }}>Grand total: </span><span style={{ color: "#fff", fontWeight: 700 }}>{fmtTokens(summary.total_tokens)}</span></div>
            <div><span style={{ color: "#666" }}>Grand cost: </span><span style={{ color: "#4ade80", fontWeight: 700 }}>{fmtCost(summary.total_cost_usd)}</span></div>
          </div>
        </Section>
      )}

      <Section title={"Web Search Activity (" + webSearchResults.length + " searches)"}>
        <WebSearchPanel results={webSearchResults} />
      </Section>
    </div>
  )
}
