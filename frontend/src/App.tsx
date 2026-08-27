import { useEffect, useState } from 'react'
import { useTaskStore } from './store/taskStore'
import { useAuthStore } from './store/authStore'
import { useHistoryStore } from './store/historyStore'
import { TaskInput } from './components/TaskInput'
import { ExecutionView } from './components/ExecutionView'
import { ResultDisplay } from './components/ResultDisplay'
import { EmployeeCard } from './components/EmployeeCard'
import { TokenAnalytics } from './components/TokenAnalytics'
import { AuthScreen } from './components/AuthScreen'
import { MCPServersPanel } from './components/MCPServersPanel'
import { useMCPStore } from './store/mcpStore'
import { History, Plug } from 'lucide-react'

function App() {
  const { phase, employees, tokenUsage, webSearchResults, activeView, setActiveView } = useTaskStore()
  const { isAuthenticated, user, logout, restoreSession } = useAuthStore()
  const { history } = useHistoryStore()
  const mcpServers = useMCPStore((s) => s.servers)
  const [showHistory, setShowHistory] = useState(false)
  const [showMCP, setShowMCP] = useState(false)

  // Restore JWT from localStorage on first render
  useEffect(() => {
    restoreSession()
    useMCPStore.getState().fetchServers()
  }, [restoreSession])

  const isExecuting = ['analyzing', 'planning', 'creating_workforce', 'executing', 'reviewing'].includes(phase)
  const isDone = phase === 'completed' || phase === 'failed'
  const hasAnalytics = tokenUsage.length > 0 || webSearchResults.length > 0

  // Show auth screen if not logged in
  if (!isAuthenticated) {
    return <AuthScreen />
  }

  return (
    <div className="app-shell">
      {/* Titlebar */}
      <div className="titlebar">
        <div className="titlebar-logo">
          <div className="titlebar-logo-icon">N</div>
          <div className="titlebar-name">NAUKAR</div>
          <div className="titlebar-tag">Autonomous AI Workforce</div>
        </div>

        {/* Analytics tab — shown during execution and after completion */}
        {(isExecuting || isDone) && (
          <div style={{ display: 'flex', gap: 6, marginLeft: 'auto', marginRight: 16 }}>
            <button
              onClick={() => setActiveView('result')}
              style={{
                padding: '4px 12px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 600,
                background: activeView === 'result' ? 'var(--bg-elevated)' : 'transparent',
                color: activeView === 'result' ? 'var(--text-primary)' : 'var(--text-secondary)',
                transition: 'all 0.15s ease',
              }}
            >
              {isDone ? '📄 Result' : '⚙️ Execution'}
            </button>
            <button
              onClick={() => setActiveView('analytics')}
              style={{
                padding: '4px 12px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 600,
                background: activeView === 'analytics' ? 'var(--bg-elevated)' : 'transparent',
                color: activeView === 'analytics' ? 'var(--text-primary)' : 'var(--text-secondary)',
                transition: 'all 0.15s ease',
                position: 'relative',
              }}
            >
              📊 Analytics
              {hasAnalytics && (
                <span style={{
                  position: 'absolute', top: 2, right: 2,
                  width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--accent-primary)',
                }} />
              )}
            </button>
          </div>
        )}

        {/* User Info & Sign Out */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginLeft: !(isExecuting || isDone) ? 'auto' : 0, marginRight: 16 }}>
          <button
            onClick={() => setShowMCP(true)}
            title="MCP Servers — connect external tools"
            style={{
              padding: '4px 8px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: showMCP ? 'var(--bg-elevated)' : 'transparent',
              color: mcpServers.some((s) => s.status === 'connected') ? '#22c55e' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              transition: 'all 0.15s ease'
            }}
          >
            <Plug size={14} />
            {mcpServers.filter((s) => s.status === 'connected').length > 0 && (
              <span style={{ fontSize: 10, fontWeight: 700 }}>
                {mcpServers.filter((s) => s.status === 'connected').length}
              </span>
            )}
          </button>

          <button
            onClick={() => setShowHistory(!showHistory)}
            title="Task History"
            style={{
              padding: '4px 8px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: showHistory ? 'var(--bg-elevated)' : 'transparent',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              transition: 'all 0.15s ease'
            }}
          >
            <History size={14} />
          </button>

          {user?.email && (
            <span style={{ fontSize: 11, color: '#888', background: 'rgba(255,255,255,0.04)', padding: '3px 8px', borderRadius: 6 }}>
              {user.email}
            </span>
          )}
          <button
            onClick={logout}
            style={{
              padding: '4px 10px',
              borderRadius: 6,
              border: '1px solid rgba(239,68,68,0.3)',
              background: 'rgba(239,68,68,0.1)',
              color: '#f87171',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Logout
          </button>
        </div>
      </div>

      {/* MCP servers modal */}
      {showMCP && <MCPServersPanel onClose={() => setShowMCP(false)} />}


      {/* Main content */}
      <div className="main-layout">
        {showHistory && (
          <div style={{ width: 280, borderRight: '1px solid var(--border-subtle)', background: 'var(--bg-base)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
              Task History
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {history.length === 0 ? (
                <div style={{ padding: '32px 20px', color: 'var(--text-muted)', fontSize: 13, textAlign: 'center' }}>No tasks found.</div>
              ) : (
                history.map((item) => (
                  <div
                    key={item.taskId}
                    onClick={() => {
                      useTaskStore.setState({
                        taskId: item.taskId,
                        title: item.title,
                        phase: 'completed',
                        finalResult: item.finalResult,
                        qualityScore: item.qualityScore,
                        employees: item.employees,
                        steps: item.steps,
                        elapsedMs: item.elapsedMs,
                        activeView: 'result'
                      });
                      setShowHistory(false);
                    }}
                    style={{
                      padding: '16px 20px',
                      borderBottom: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-elevated)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.title}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {new Date(item.date).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {phase === 'idle' && <TaskInput />}

          {isExecuting && !isDone && (
            activeView === 'analytics' ? (
              <div style={{ flex: 1, overflow: 'hidden', height: '100%' }}>
                <TokenAnalytics />
              </div>
            ) : (
              <ExecutionView />
            )
          )}

          {isDone && (
            activeView === 'analytics' ? (
              <div style={{ flex: 1, overflow: 'hidden', height: '100%' }}>
                <TokenAnalytics />
              </div>
            ) : (
              <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
                {/* Workforce panel */}
              <div style={{
                width: 360,
                borderRight: '1px solid var(--border-subtle)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                background: 'rgba(10, 10, 18, 0.6)',
              }}>
                <div className="panel-header">
                  <div className="panel-title">AI Workforce</div>
                  <div className="panel-count">{employees.length} employees</div>
                </div>
                <div className="workforce-list">
                  {employees
                    .sort((a, b) => a.hierarchy_level - b.hierarchy_level)
                    .map((emp) => (
                      <EmployeeCard key={emp.id} employee={emp} allEmployees={employees} />
                    ))}
                </div>
              </div>
              {/* Result */}
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <ResultDisplay />
              </div>
            </div>
          )
        )}
        </div>
      </div>
    </div>
  )
}

export default App
