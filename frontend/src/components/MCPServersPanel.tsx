import { useEffect, useState } from 'react'
import type { FC } from 'react'
import { useMCPStore } from '../store/mcpStore'
import type { MCPPreset } from '../store/mcpStore'

const STATUS_COLORS: Record<string, string> = {
  connected: '#22c55e',
  connecting: '#eab308',
  error: '#ef4444',
  disconnected: '#6b7280',
}

interface FormState {
  name: string
  transport: 'stdio' | 'sse' | 'http'
  command: string
  args: string
  url: string
  envPairs: { key: string; value: string }[]
}

const EMPTY_FORM: FormState = {
  name: '',
  transport: 'stdio',
  command: '',
  args: '',
  url: '',
  envPairs: [],
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid var(--border-subtle)',
  background: 'var(--bg-surface)',
  color: 'var(--text-primary)',
  fontSize: 12,
  outline: 'none',
  boxSizing: 'border-box',
}

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--text-secondary)',
  marginBottom: 4,
  display: 'block',
  fontWeight: 600,
}

export const MCPServersPanel: FC<{ onClose: () => void }> = ({ onClose }) => {
  const { servers, presets, isLoading, error, fetchServers, fetchPresets, addServer, removeServer, reconnectServer } = useMCPStore()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    fetchServers()
    fetchPresets()
  }, [fetchServers, fetchPresets])

  const applyPreset = (p: MCPPreset) => {
    setForm({
      name: p.name,
      transport: 'stdio',
      command: p.command,
      args: p.args.join(' '),
      url: '',
      envPairs: p.env_keys.map((k) => ({ key: k, value: '' })),
    })
    setShowForm(true)
  }

  const submit = async () => {
    const env: Record<string, string> = {}
    form.envPairs.forEach(({ key, value }) => {
      if (key.trim() && value.trim()) env[key.trim()] = value.trim()
    })
    const ok = await addServer({
      name: form.name.trim() || 'MCP Server',
      transport: form.transport,
      command: form.command.trim(),
      args: form.args.trim().split(/\s+/).filter(Boolean),
      url: form.url.trim(),
      env,
    })
    if (ok) {
      setForm(EMPTY_FORM)
      setShowForm(false)
    }
  }

  const totalTools = servers.reduce((n, s) => n + s.tools.length, 0)

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 640, maxHeight: '82vh', overflowY: 'auto',
          background: 'var(--bg-base)', border: '1px solid var(--border-subtle)',
          borderRadius: 14, padding: 24, boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
              🔌 MCP Servers
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
              Connect external tools — your employees use them automatically during tasks.
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', color: 'var(--text-secondary)',
            fontSize: 18, cursor: 'pointer',
          }}>✕</button>
        </div>

        <div style={{
          fontSize: 11, color: 'var(--accent-cyan, #22d3ee)', margin: '10px 0 14px',
          padding: '8px 12px', borderRadius: 8, background: 'rgba(34,211,238,0.06)',
          border: '1px solid rgba(34,211,238,0.15)',
        }}>
          {servers.filter((s) => s.status === 'connected').length} server(s) connected · {totalTools} tools available to the workforce
        </div>

        {error && (
          <div style={{ fontSize: 12, color: '#f87171', marginBottom: 10 }}>{error}</div>
        )}

        {/* Presets */}
        {presets.length > 0 && !showForm && (
          <div style={{ marginBottom: 18 }}>
            <div style={labelStyle}>QUICK CONNECT</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {presets.map((p) => (
                <button
                  key={p.key}
                  onClick={() => applyPreset(p)}
                  style={{
                    textAlign: 'left', padding: '10px 12px', borderRadius: 10,
                    border: '1px solid var(--border-subtle)', background: 'var(--bg-surface)',
                    cursor: 'pointer', transition: 'border-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-cyan, #22d3ee)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
                >
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.4 }}>
                    {p.description}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Add form */}
        {showForm ? (
          <div style={{
            border: '1px solid var(--border-subtle)', borderRadius: 10,
            padding: 14, marginBottom: 18, background: 'var(--bg-surface)',
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 140px', gap: 10, marginBottom: 10 }}>
              <div>
                <label style={labelStyle}>NAME</label>
                <input style={inputStyle} value={form.name} placeholder="e.g. Meta Ads"
                  onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label style={labelStyle}>TRANSPORT</label>
                <select style={inputStyle} value={form.transport}
                  onChange={(e) => setForm({ ...form, transport: e.target.value as FormState['transport'] })}>
                  <option value="stdio">stdio</option>
                  <option value="sse">sse</option>
                  <option value="http">http</option>
                </select>
              </div>
            </div>

            {form.transport === 'stdio' ? (
              <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: 10, marginBottom: 10 }}>
                <div>
                  <label style={labelStyle}>COMMAND</label>
                  <input style={inputStyle} value={form.command} placeholder="npx"
                    onChange={(e) => setForm({ ...form, command: e.target.value })} />
                </div>
                <div>
                  <label style={labelStyle}>ARGUMENTS (space separated)</label>
                  <input style={inputStyle} value={form.args} placeholder="-y @some/mcp-server"
                    onChange={(e) => setForm({ ...form, args: e.target.value })} />
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: 10 }}>
                <label style={labelStyle}>SERVER URL</label>
                <input style={inputStyle} value={form.url} placeholder="https://mcp.example.com/sse"
                  onChange={(e) => setForm({ ...form, url: e.target.value })} />
              </div>
            )}

            {/* Env vars */}
            <label style={labelStyle}>ENVIRONMENT VARIABLES (API keys etc.)</label>
            {form.envPairs.map((pair, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 30px', gap: 8, marginBottom: 6 }}>
                <input style={inputStyle} value={pair.key} placeholder="KEY"
                  onChange={(e) => {
                    const envPairs = [...form.envPairs]
                    envPairs[i] = { ...pair, key: e.target.value }
                    setForm({ ...form, envPairs })
                  }} />
                <input style={inputStyle} type="password" value={pair.value} placeholder="value"
                  onChange={(e) => {
                    const envPairs = [...form.envPairs]
                    envPairs[i] = { ...pair, value: e.target.value }
                    setForm({ ...form, envPairs })
                  }} />
                <button onClick={() => setForm({ ...form, envPairs: form.envPairs.filter((_, j) => j !== i) })}
                  style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer' }}>✕</button>
              </div>
            ))}
            <button
              onClick={() => setForm({ ...form, envPairs: [...form.envPairs, { key: '', value: '' }] })}
              style={{
                background: 'transparent', border: '1px dashed var(--border-subtle)',
                color: 'var(--text-secondary)', borderRadius: 8, padding: '5px 10px',
                fontSize: 11, cursor: 'pointer', marginBottom: 12,
              }}
            >+ Add variable</button>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowForm(false)} style={{
                padding: '7px 14px', borderRadius: 8, border: '1px solid var(--border-subtle)',
                background: 'transparent', color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer',
              }}>Cancel</button>
              <button onClick={submit} disabled={isLoading} style={{
                padding: '7px 14px', borderRadius: 8, border: 'none',
                background: 'var(--accent-primary, #6366f1)', color: '#fff',
                fontSize: 12, fontWeight: 600, cursor: isLoading ? 'wait' : 'pointer',
              }}>{isLoading ? 'Connecting…' : 'Connect Server'}</button>
            </div>
          </div>
        ) : (
          <button onClick={() => setShowForm(true)} style={{
            width: '100%', padding: '9px 0', borderRadius: 10, marginBottom: 18,
            border: '1px dashed var(--border-subtle)', background: 'transparent',
            color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer',
          }}>+ Add custom MCP server</button>
        )}

        {/* Connected servers */}
        <div style={labelStyle}>CONFIGURED SERVERS</div>
        {servers.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '12px 0' }}>
            No servers connected yet. Pick a preset above or add a custom one.
          </div>
        ) : (
          servers.map((s) => (
            <div key={s.id} style={{
              border: '1px solid var(--border-subtle)', borderRadius: 10,
              padding: '10px 12px', marginBottom: 8, background: 'var(--bg-surface)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: STATUS_COLORS[s.status] || '#6b7280',
                  boxShadow: s.status === 'connected' ? '0 0 6px #22c55e' : 'none',
                }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{s.name}</span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 5 }}>
                  {s.transport}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                  {s.status === 'connected' ? `${s.tools.length} tools` : s.status}
                </span>
                <button title="Reconnect" onClick={() => reconnectServer(s.id)} style={{
                  background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 13,
                }}>↻</button>
                <button title="Remove" onClick={() => removeServer(s.id)} style={{
                  background: 'transparent', border: 'none', cursor: 'pointer', color: '#f87171', fontSize: 13,
                }}>🗑</button>
              </div>

              {s.error && (
                <div style={{ fontSize: 11, color: '#f87171', marginTop: 6 }}>{s.error}</div>
              )}

              {s.tools.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  <button
                    onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--accent-cyan, #22d3ee)', fontSize: 11, cursor: 'pointer', padding: 0 }}
                  >
                    {expanded === s.id ? '▾ hide tools' : '▸ show tools'}
                  </button>
                  {expanded === s.id && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 6 }}>
                      {s.tools.map((t) => (
                        <span key={t} style={{
                          fontSize: 10, padding: '2px 8px', borderRadius: 999,
                          background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.2)',
                          color: 'var(--accent-cyan, #22d3ee)',
                        }}>{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
