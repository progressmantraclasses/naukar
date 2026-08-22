import React from 'react'
import type { Employee } from '../store/taskStore'

const ROLE_EMOJI: Record<string, string> = {
  manager: '🎯',
  lead: '🎯',
  director: '🏛️',
  researcher: '🔍',
  analyst: '📊',
  writer: '✍️',
  engineer: '⚙️',
  reviewer: '🔎',
  qa: '✅',
  designer: '🎨',
  strategist: '🧠',
  specialist: '⚡',
  developer: '💻',
  coordinator: '🔗',
  default: '🤖',
}

function getRoleEmoji(role: string): string {
  const lower = role.toLowerCase()
  for (const [key, emoji] of Object.entries(ROLE_EMOJI)) {
    if (lower.includes(key)) return emoji
  }
  return ROLE_EMOJI.default
}

function getHierarchyIndent(level: number): number {
  return level * 16
}

interface EmployeeCardProps {
  employee: Employee
  allEmployees: Employee[]
}

export const EmployeeCard: React.FC<EmployeeCardProps> = ({
  employee,
  allEmployees,
}) => {
  const manager = employee.manager_id
    ? allEmployees.find((e) => e.id === employee.manager_id)
    : null

  const confidencePct = employee.confidence
    ? Math.round(employee.confidence * 100)
    : null

  return (
    <div
      className="employee-card"
      data-status={employee.status}
      style={{ marginLeft: getHierarchyIndent(employee.hierarchy_level) }}
    >
      <div className="employee-card-header">
        <div className="employee-avatar">{getRoleEmoji(employee.role)}</div>
        <div className="employee-info">
          <div className="employee-role">{employee.role}</div>
          <div className="employee-status-row">
            <div className="status-dot" data-status={employee.status} />
            <div className="status-label">{employee.status}</div>
            {manager && (
              <div style={{ fontSize: 10, color: 'var(--text-disabled)' }}>
                → {manager.role.split(' ')[0]}
              </div>
            )}
          </div>
        </div>
      </div>

      {employee.current_task && employee.status !== 'idle' && employee.status !== 'completed' && (
        <div className="employee-task">{employee.current_task}</div>
      )}

      {employee.status === 'completed' && employee.last_action && (
        <div className="employee-task" style={{ color: 'var(--status-completed)' }}>
          ✓ {employee.last_action.replace('Completed: ', '')}
        </div>
      )}

      <div className="employee-meta">
        {employee.current_model && (
          <div className="meta-chip">
            🧠 {employee.current_model.split('/').pop()}
          </div>
        )}
        {employee.tools.length > 0 && (
          <div className="meta-chip">
            🔧 {employee.tools.slice(0, 2).join(', ')}
            {employee.tools.length > 2 ? ` +${employee.tools.length - 2}` : ''}
          </div>
        )}
        {confidencePct !== null && (
          <div
            className="meta-chip"
            style={{
              color:
                confidencePct >= 85
                  ? 'var(--accent-emerald)'
                  : confidencePct >= 70
                  ? 'var(--accent-amber)'
                  : 'var(--accent-rose)',
            }}
          >
            {confidencePct}%
          </div>
        )}
      </div>

      {employee.confidence !== undefined && (
        <div className="confidence-bar">
          <div
            className="confidence-fill"
            style={{ width: `${(employee.confidence || 0) * 100}%` }}
          />
        </div>
      )}
    </div>
  )
}
