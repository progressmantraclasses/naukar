import { useEffect, useRef, type FC } from 'react'
import { useTaskStore } from '../store/taskStore'
import { EmployeeCard } from './EmployeeCard'
import { CompetitionPanel } from './CompetitionPanel'


const PHASE_LABELS: Record<string, string> = {
  analyzing: '🔍 Analyzing',
  planning: '📐 Planning',
  creating_workforce: '👥 Creating Team',
  executing: '⚡ Executing',
  reviewing: '🔎 Reviewing',
  completed: '✅ Completed',
  failed: '❌ Failed',
}

const STEP_ICONS: Record<string, string> = {
  pending: '○',
  running: '⟳',
  completed: '✓',
  failed: '✗',
}

const EVENT_ICONS: Record<string, string> = {
  TASK_ANALYZED: '🔍',
  WORKFORCE_CREATED: '👥',
  EMPLOYEE_CREATED: '🤖',
  EMPLOYEE_STATUS_CHANGED: '⚡',
  TASK_ASSIGNED: '📋',
  STEP_STARTED: '▶️',
  STEP_COMPLETED: '✅',
  LLM_CALLED: '🧠',
  QUALITY_CHECKED: '🔎',
  TASK_REPLANNED: '🔄',
  TASK_FAILED: '❌',
  COMPETITOR_SCAN_PROGRESS: '🕵️',
  COMPETITOR_MATRIX_READY: '📊',
  MCP_TOOL_CALLED: '🔌',
}

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

export const ExecutionView: FC = () => {
  const {
    phase, title, complexityScore, employees, steps,
    thinkingMessages, events, elapsedMs, wsConnected, topology,
    workforce_rationale,
  } = useTaskStore()

  const feedRef = useRef<HTMLDivElement>(null)

  // Auto-scroll activity feed
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [events, thinkingMessages])

  const completedSteps = steps.filter((s) => s.status === 'completed').length
  const workingEmployees = employees.filter((e) => e.status === 'working').length

  // Separate events from thinking messages for the feed
  const filteredEvents = events.filter(
    (e) => !['THINKING', 'HEARTBEAT', 'CONNECTED', 'LLM_RESPONSE'].includes(e.event_type)
  )

  return (
    <div className="execution-screen">
      {/* ── LEFT PANEL: Workforce ──────────────────────────────── */}
      <div className="panel-left">
        <div className="panel-header">
          <div className="panel-title">AI Workforce</div>
          <div className="panel-count">
            {employees.length > 0 && (
              <span>
                {employees.length} employee{employees.length !== 1 ? 's' : ''}
                {topology && ` · ${topology}`}
              </span>
            )}
          </div>
        </div>

        <div className="workforce-list">
          {employees.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">👥</div>
              <span>Team assembling…</span>
            </div>
          ) : (
            employees
              .sort((a, b) => a.hierarchy_level - b.hierarchy_level)
              .map((emp) => (
                <EmployeeCard
                  key={emp.id}
                  employee={emp}
                  allEmployees={employees}
                />
              ))
          )}
        </div>

        {/* Topology info */}
        {workforce_rationale && (
          <div
            style={{
              padding: '10px 14px',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: 11,
              color: 'var(--text-disabled)',
              lineHeight: 1.5,
              flexShrink: 0,
            }}
          >
            {workforce_rationale.slice(0, 120)}…
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL: Activity + Steps ──────────────────────── */}
      <div className="panel-right">
        {/* Status bar */}
        <div className="status-header">
          <div className="status-phase">
            <div className={`phase-indicator ${phase}`}>
              {phase === 'executing' || phase === 'analyzing' || phase === 'planning' ? (
                <div className="spinner" />
              ) : null}
              {PHASE_LABELS[phase] || phase}
            </div>
          </div>

          {title && (
            <div className="status-stat">
              <span>{title}</span>
            </div>
          )}

          {complexityScore !== null && (
            <div className="status-stat">
              <strong>Complexity</strong>
              <span>{Math.round(complexityScore * 100)}%</span>
            </div>
          )}

          {employees.length > 0 && (
            <div className="status-stat">
              <strong>{workingEmployees}</strong>
              <span>working</span>
            </div>
          )}

          <div className="status-stat" style={{ marginLeft: 'auto' }}>
            <span
              style={{
                color: wsConnected ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                fontSize: 10,
              }}
            >
              {wsConnected ? '● Live' : '○ Offline'}
            </span>
            <strong style={{ fontFamily: 'JetBrains Mono' }}>
              {formatElapsed(elapsedMs)}
            </strong>
          </div>
        </div>

        {/* Activity feed */}
        <div className="activity-feed" ref={feedRef}>
          {thinkingMessages.map((msg) => (
            <div key={msg.id} className="thinking-message">
              <span className="thinking-icon">💭</span>
              <div className="thinking-text">{msg.message}</div>
            </div>
          ))}

          {filteredEvents.map((ev) => (
            <div key={ev.id} className="event-row">
              <span className="event-icon">{EVENT_ICONS[ev.event_type] || '•'}</span>
              <div className="event-content">
                <div className="event-type">{ev.event_type.replace(/_/g, ' ')}</div>
                <div className="event-detail">
                  {ev.event_type === 'EMPLOYEE_CREATED' &&
                    `${ev.payload.role as string} — ${ev.payload.objective as string}`}
                  {ev.event_type === 'TASK_ASSIGNED' &&
                    `Step ${ev.payload.step_index as number}: ${ev.payload.objective as string}`}
                  {ev.event_type === 'STEP_STARTED' &&
                    `${ev.payload.role as string}: ${ev.payload.objective as string}`}
                  {ev.event_type === 'STEP_COMPLETED' &&
                    `Quality ${Math.round((ev.payload.quality_score as number) * 100)}% · Confidence ${Math.round((ev.payload.confidence as number) * 100)}%`}
                  {ev.event_type === 'QUALITY_CHECKED' &&
                    `Score: ${Math.round((ev.payload.score as number) * 100)}% · ${ev.payload.passed ? 'PASSED' : 'FAILED'}`}
                  {ev.event_type === 'LLM_CALLED' &&
                    `${ev.payload.role as string} → ${(ev.payload.model as string)?.split('/').pop()}`}
                  {ev.event_type === 'WORKFORCE_CREATED' &&
                    `${(ev.payload.roles as unknown[])?.length} roles · ${ev.payload.topology as string}`}
                  {ev.event_type === 'TASK_REPLANNED' &&
                    (ev.payload.reason as string)}
                  {ev.event_type === 'COMPETITOR_SCAN_PROGRESS' &&
                    `${ev.payload.status === 'browsing' ? 'Browsing' : 'Scanned'}: ${ev.payload.name as string}`}
                  {ev.event_type === 'COMPETITOR_MATRIX_READY' &&
                    `Competitor matrix ready · ${(ev.payload.profiles as unknown[])?.length || 0} competitors · ${ev.payload.sites_browsed as number} sites browsed`}
                  {ev.event_type === 'MCP_TOOL_CALLED' &&
                    `${ev.payload.status === 'calling' ? 'Calling' : ev.payload.status === 'done' ? 'Returned' : 'Failed'} MCP tool: ${ev.payload.tool as string}${ev.payload.server ? ` (${ev.payload.server as string})` : ''}`}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Competition Scout live panel (only for competition tasks) */}
        <CompetitionPanel />

        {/* Steps tracker */}
        {steps.length > 0 && (
          <div className="steps-section">
            <div className="steps-title">
              Execution Plan · {completedSteps}/{steps.length} steps complete
            </div>
            <div className="steps-list">
              {steps.map((step) => (
                <div key={step.id} className="step-row">
                  <div className="step-index">{step.step_index + 1}</div>
                  <div
                    className="step-status-icon"
                    style={{
                      color:
                        step.status === 'completed'
                          ? 'var(--accent-emerald)'
                          : step.status === 'running'
                          ? 'var(--accent-cyan)'
                          : step.status === 'failed'
                          ? 'var(--accent-rose)'
                          : 'var(--text-disabled)',
                    }}
                  >
                    {step.status === 'running' ? (
                      <div className="spinner" style={{ width: 10, height: 10 }} />
                    ) : (
                      STEP_ICONS[step.status]
                    )}
                  </div>
                  <div className="step-objective">{step.objective}</div>
                  <div className="step-role">{step.assigned_role?.split(' ')[0]}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
