import React from 'react'
import { useTaskStore } from './store/taskStore'
import { TaskInput } from './components/TaskInput'
import { ExecutionView } from './components/ExecutionView'
import { ResultDisplay } from './components/ResultDisplay'
import { EmployeeCard } from './components/EmployeeCard'

function App() {
  const { phase, employees } = useTaskStore()

  const isExecuting = ['analyzing', 'planning', 'creating_workforce', 'executing', 'reviewing'].includes(phase)
  const isDone = phase === 'completed' || phase === 'failed'

  return (
    <div className="app-shell">
      {/* Custom titlebar */}
      <div className="titlebar">
        <div className="titlebar-logo">
          <div className="titlebar-logo-icon">N</div>
          <div className="titlebar-name">NAUKAR</div>
          <div className="titlebar-tag">Autonomous AI Workforce</div>
        </div>
      </div>

      {/* Main content */}
      <div className="main-layout">
        {phase === 'idle' && <TaskInput />}

        {isExecuting && !isDone && <ExecutionView />}

        {isDone && (
          <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
            {/* Workforce panel stays visible */}
            <div
              style={{
                width: 360,
                borderRight: '1px solid var(--border-subtle)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                background: 'rgba(10, 10, 18, 0.6)',
              }}
            >
              <div className="panel-header">
                <div className="panel-title">AI Workforce</div>
                <div className="panel-count">{employees.length} employees</div>
              </div>
              <div className="workforce-list">
                {employees
                  .sort((a, b) => a.hierarchy_level - b.hierarchy_level)
                  .map((emp) => (
                    <EmployeeCard
                      key={emp.id}
                      employee={emp}
                      allEmployees={employees}
                    />
                  ))}
              </div>
            </div>
            {/* Result */}
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <ResultDisplay />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
