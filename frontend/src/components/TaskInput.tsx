import React, { useRef } from 'react'
import { useTaskStore } from '../store/taskStore'

const EXAMPLES = [
  'Create a competitor analysis for my SaaS startup',
  'Research the AI startup market in India',
  'Fix this bug: my API returns 500 on /users endpoint',
  'Build a landing page for my product',
  'Analyze why revenue dropped last quarter',
]

const API_BASE = 'http://localhost:8000'

export const TaskInput: React.FC = () => {
  const { userInput, setUserInput, startTask, phase } = useTaskStore()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = async () => {
    if (!userInput.trim()) return
    try {
      const res = await fetch(`${API_BASE}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: userInput }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const task = await res.json()
      startTask(task.id, userInput)

      // Connect WebSocket for live updates
      const ws = new WebSocket(`ws://localhost:8000/ws/${task.id}`)
      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          useTaskStore.getState().handleEvent(event)
        } catch {}
      }
      ws.onopen = () => useTaskStore.getState().setWsConnected(true)
      ws.onclose = () => useTaskStore.getState().setWsConnected(false)
    } catch (err) {
      console.error('Failed to start task:', err)
      alert(`Failed to connect to backend. Is the server running?\n\n${err}`)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  if (phase !== 'idle') return null

  return (
    <div className="input-screen">
      <div className="input-hero">
        <div className="input-hero-badge">Autonomous AI Workforce</div>
        <h1>Your AI Company,<br />On Demand</h1>
        <p>
          Give us a task. We'll hire the team, assign the work,
          execute it, review it, and deliver results — automatically.
        </p>
      </div>

      <div className="input-card">
        <div className="input-label">What do you want done?</div>
        <textarea
          ref={textareaRef}
          className="input-textarea"
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Create a detailed competitor analysis for my SaaS startup in the project management space..."
          rows={4}
          autoFocus
        />
        <div className="input-footer">
          <div className="input-examples">
            {EXAMPLES.slice(0, 3).map((ex) => (
              <button
                key={ex}
                className="example-chip"
                onClick={() => setUserInput(ex)}
              >
                {ex.length > 40 ? ex.slice(0, 40) + '…' : ex}
              </button>
            ))}
          </div>
          <button
            className="btn-start"
            onClick={handleSubmit}
            disabled={!userInput.trim()}
          >
            <span>Start Task</span>
            <span style={{ fontSize: 10, opacity: 0.7 }}>⌘↵</span>
          </button>
        </div>
      </div>
    </div>
  )
}
