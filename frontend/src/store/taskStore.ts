import { create } from 'zustand'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
export type EmployeeStatus =
  | 'idle' | 'planning' | 'working' | 'waiting'
  | 'reviewing' | 'blocked' | 'retrying' | 'completed' | 'failed'

export interface Employee {
  id: string
  role: string
  objective: string
  skills: string[]
  tools: string[]
  status: EmployeeStatus
  current_task?: string
  current_model?: string
  confidence?: number
  last_action?: string
  hierarchy_level: number
  manager_id?: string
}

export interface TaskStep {
  id: string
  step_index: number
  objective: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  assigned_role?: string
  quality_score?: number
  confidence?: number
  model?: string
}

export interface ThinkingMessage {
  id: string
  message: string
  timestamp: number
}

export interface LiveEvent {
  id: string
  event_type: string
  payload: Record<string, unknown>
  timestamp: string
}

export type TaskPhase =
  | 'idle'
  | 'analyzing'
  | 'planning'
  | 'creating_workforce'
  | 'executing'
  | 'reviewing'
  | 'completed'
  | 'failed'

export interface TaskState {
  taskId: string | null
  userInput: string
  phase: TaskPhase
  title: string
  taskType: string
  complexityScore: number | null
  employees: Employee[]
  steps: TaskStep[]
  thinkingMessages: ThinkingMessage[]
  events: LiveEvent[]
  finalResult: string | null
  qualityScore: number | null
  elapsedMs: number
  wsConnected: boolean
  error: string | null
  workforce_rationale: string
  topology: string
}

interface TaskActions {
  setUserInput: (input: string) => void
  startTask: (taskId: string, userInput: string) => void
  handleEvent: (event: Record<string, unknown>) => void
  reset: () => void
  setWsConnected: (connected: boolean) => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────
const initialState: TaskState = {
  taskId: null,
  userInput: '',
  phase: 'idle',
  title: '',
  taskType: '',
  complexityScore: null,
  employees: [],
  steps: [],
  thinkingMessages: [],
  events: [],
  finalResult: null,
  qualityScore: null,
  elapsedMs: 0,
  wsConnected: false,
  error: null,
  workforce_rationale: '',
  topology: '',
}

let startTime = 0

export const useTaskStore = create<TaskState & TaskActions>((set, get) => ({
  ...initialState,

  setUserInput: (input) => set({ userInput: input }),

  startTask: (taskId, userInput) => {
    startTime = Date.now()
    set({
      ...initialState,
      taskId,
      userInput,
      phase: 'analyzing',
    })
  },

  reset: () => set({ ...initialState }),

  setWsConnected: (connected) => set({ wsConnected: connected }),

  handleEvent: (event) => {
    const type = event.event_type as string
    const payload = (event.payload || {}) as Record<string, unknown>
    const elapsed = Date.now() - startTime

    set((state) => {
      const newEvent: LiveEvent = {
        id: Math.random().toString(36).slice(2),
        event_type: type,
        payload,
        timestamp: (event.timestamp as string) || new Date().toISOString(),
      }

      switch (type) {
        case 'THINKING':
          return {
            events: [...state.events.slice(-100), newEvent],
            thinkingMessages: [
              ...state.thinkingMessages,
              {
                id: newEvent.id,
                message: payload.message as string,
                timestamp: elapsed,
              },
            ],
          }

        case 'TASK_ANALYZED':
          return {
            events: [...state.events.slice(-100), newEvent],
            phase: 'planning',
            title: payload.title as string,
            taskType: payload.task_type as string,
            complexityScore: payload.complexity as number,
          }

        case 'WORKFORCE_CREATED':
          return {
            events: [...state.events.slice(-100), newEvent],
            phase: 'creating_workforce',
            workforce_rationale: payload.rationale as string,
            topology: payload.topology as string,
          }

        case 'EMPLOYEE_CREATED':
        case 'EMPLOYEE_CREATED_DURING_EXECUTION': {
          const emp: Employee = {
            id: payload.employee_id as string,
            role: payload.role as string,
            objective: payload.objective as string,
            skills: (payload.skills as string[]) || [],
            tools: (payload.tools as string[]) || [],
            status: 'idle',
            hierarchy_level: (payload.hierarchy_level as number) || 0,
            manager_id: payload.manager_id as string | undefined,
          }
          const existing = state.employees.find((e) => e.id === emp.id)
          if (existing) return { events: [...state.events.slice(-100), newEvent] }
          return {
            events: [...state.events.slice(-100), newEvent],
            employees: [...state.employees, emp],
          }
        }

        case 'EMPLOYEE_STATUS_CHANGED': {
          const updatedEmployees = state.employees.map((e) =>
            e.id === payload.employee_id
              ? {
                  ...e,
                  status: (payload.status as EmployeeStatus) || e.status,
                  current_task: (payload.current_task as string) || e.current_task,
                  current_model: (payload.current_model as string) || e.current_model,
                  confidence: (payload.confidence as number) ?? e.confidence,
                  last_action: (payload.last_action as string) || e.last_action,
                }
              : e
          )
          return {
            events: [...state.events.slice(-100), newEvent],
            employees: updatedEmployees,
          }
        }

        case 'TASK_ASSIGNED': {
          const step: TaskStep = {
            id: payload.step_id as string,
            step_index: payload.step_index as number,
            objective: payload.objective as string,
            status: 'pending',
            assigned_role: payload.assigned_role as string,
          }
          const exists = state.steps.find((s) => s.id === step.id)
          if (exists) return { events: [...state.events.slice(-100), newEvent] }
          return {
            events: [...state.events.slice(-100), newEvent],
            steps: [...state.steps, step].sort((a, b) => a.step_index - b.step_index),
            phase: 'executing',
          }
        }

        case 'STEP_STARTED': {
          const updatedSteps = state.steps.map((s) =>
            s.id === payload.step_id ? { ...s, status: 'running' as const } : s
          )
          return { events: [...state.events.slice(-100), newEvent], steps: updatedSteps }
        }

        case 'STEP_COMPLETED': {
          const updatedSteps = state.steps.map((s) =>
            s.id === payload.step_id
              ? {
                  ...s,
                  status: 'completed' as const,
                  quality_score: payload.quality_score as number,
                  confidence: payload.confidence as number,
                  model: payload.model as string,
                }
              : s
          )
          return {
            events: [...state.events.slice(-100), newEvent],
            steps: updatedSteps,
            elapsedMs: elapsed,
          }
        }

        case 'QUALITY_CHECKED':
          return { events: [...state.events.slice(-100), newEvent], elapsedMs: elapsed }

        case 'FINAL_RESULT_READY':
          return {
            events: [...state.events.slice(-100), newEvent],
            phase: 'completed',
            finalResult: payload.result as string,
            qualityScore: payload.quality_score as number,
            elapsedMs: elapsed,
          }

        case 'TASK_FAILED':
          return {
            events: [...state.events.slice(-100), newEvent],
            phase: 'failed',
            error: payload.error as string,
            elapsedMs: elapsed,
          }

        default:
          return { events: [...state.events.slice(-100), newEvent], elapsedMs: elapsed }
      }
    })
  },
}))
