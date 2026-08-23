import React, { useEffect } from 'react'
import { useTaskStore } from './store/taskStore'
import { useAuthStore } from './store/authStore'
import { TaskInput } from './components/TaskInput'
import { ExecutionView } from './components/ExecutionView'
import { ResultDisplay } from './components/ResultDisplay'
import { EmployeeCard } from './components/EmployeeCard'
import { TokenAnalytics } from './components/TokenAnalytics'
import { AuthScreen } from './components/AuthScreen'

function App() {
  const { phase, employees, tokenUsage, webSearchResults, activeView, setActiveView } = useTaskStore()
  const { isAuthenticated, user, logout, restoreSession } = useAuthStore()

  // Restore JWT from localStorage on first render
  useEffect(() => {
    restoreSession()
  }, [])

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
                padding: '5px 14px',
                borderRadius: 8,
                border: 'none',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 600,
                background: activeView === 'result' ? 'rgba(56,189,248,0.2)' : 'rgba(255,255,255,0.05)',
                color: activeView === 'result' ? '#38bdf8' : '#888',
                transition: 'all 0.2s',
              }}
            >
              {isDone ? '📄 Result' : '⚙️ Execution'}
            </button>
            <button
              onClick={() => setActiveView('analytics')}
              style={{
                padding: '5px 14px',
                borderRadius: 8,
                border: 'none',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 600,
                background: activeView === 'analytics' ? 'rgba(192,132,252,0.2)' : 'rgba(255,255,255,0.05)',
                color: activeView === 'analytics' ? '#c084fc' : '#888',
                transition: 'all 0.2s',
                position: 'relative',
              }}
            >
              📊 Analytics
              {hasAnalytics && (
                <span style={{
                  position: 'absolute', top: -4, right: -4,
                  width: 8, height: 8, borderRadius: '50%',
                  background: '#c084fc',
                }} />
              )}
            </button>
          </div>
        )}
      </div>

      {/* Main content */}
      <div className="main-layout">
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
  )
}

export default App
