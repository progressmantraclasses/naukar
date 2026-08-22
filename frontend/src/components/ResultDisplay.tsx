import React from 'react'
import ReactMarkdown from 'react-markdown'
import { useTaskStore } from '../store/taskStore'

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

export const ResultDisplay: React.FC = () => {
  const {
    phase, finalResult, qualityScore, elapsedMs,
    employees, steps, title, reset,
  } = useTaskStore()

  if (phase !== 'completed' && phase !== 'failed') return null
  if (phase === 'failed') {
    return (
      <div className="result-panel">
        <div className="result-header">
          <div className="result-header-top">
            <div className="result-title">❌ Task Failed</div>
            <button className="btn-new-task" onClick={reset}>
              ↩ New Task
            </button>
          </div>
        </div>
        <div className="result-content">
          <div style={{ color: 'var(--accent-rose)', padding: 16 }}>
            The task encountered an error. Please check the backend logs and try again.
          </div>
        </div>
      </div>
    )
  }

  const completedSteps = steps.filter((s) => s.status === 'completed').length

  return (
    <div className="result-panel">
      <div className="result-header">
        <div className="result-header-top">
          <div className="result-title">
            ✅ {title || 'Task Complete'}
          </div>
          <div className="result-quality">
            {qualityScore !== null && (
              <div className="quality-badge">
                ⭐ {Math.round(qualityScore * 100)}% Quality
              </div>
            )}
            <button className="btn-new-task" onClick={reset}>
              ↩ New Task
            </button>
          </div>
        </div>
        <div className="result-stats">
          <div className="result-stat">
            <strong>{employees.length}</strong> employees
          </div>
          <div className="result-stat">
            <strong>{completedSteps}</strong> steps
          </div>
          <div className="result-stat">
            Completed in <strong>{formatElapsed(elapsedMs)}</strong>
          </div>
        </div>
      </div>

      <div className="result-content">
        <div className="result-markdown">
          <ReactMarkdown>{finalResult || '_No result generated._'}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
