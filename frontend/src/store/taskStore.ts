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
  name: string
  avatar?: string
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

export interface TokenUsageEntry {
  step_label: string
  model: string
  source: 'llm' | 'cache' | 'web' | string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  latency_ms: number
  web_sites_checked?: number
  web_sites_used?: number
  tokens_saved_by_web?: number
  timestamp?: number
  // cumulative at this point
  cumulative_tokens?: number
  cumulative_cost_usd?: number
}

export interface WebSearchResult {
  query: string
  step_label: string
  tier_used: 'ddg' | 'tavily' | 'none' | string
  sites_checked: number
  sites_used: number
  is_sufficient: boolean
  estimated_tokens_saved: number
  latency_ms: number
  sources: { url: string; title: string; snippet: string }[]
}

export interface CompetitorProfile {
  name: string
  website: string
  pricing: string[]
  features: string[]
  strengths: string[]
  weaknesses: string[]
  sources: { url: string; title: string }[]
  sites_checked: number
}

export interface CompetitionScan {
  status: 'scanning' | 'done'
  own_product: string | null
  current_target: string | null
  profiles: CompetitorProfile[]
  matrix_md: string
  sites_browsed: number
  llm_calls: number
  tokens_saved: number
}

export interface TokenSummary {
  task_id: string
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  total_cost_usd: number
  avg_latency_ms: number
  cache_hits: number
  llm_calls: number
  web_searches: number
  web_sites_checked: number
  tokens_saved_by_web: number
  entries: TokenUsageEntry[]
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
  // Token analytics
  tokenUsage: TokenUsageEntry[]
  webSearchResults: WebSearchResult[]
  tokenSummary: TokenSummary | null
  activeView: 'result' | 'analytics'
  // Competition scout super-worker
  competitionScan: CompetitionScan | null
}

interface TaskActions {
  setUserInput: (input: string) => void
  startTask: (taskId: string, userInput: string) => void
  handleEvent: (event: Record<string, unknown>) => void
  reset: () => void
  setWsConnected: (connected: boolean) => void
  setActiveView: (view: 'result' | 'analytics') => void
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
  tokenUsage: [],
  webSearchResults: [],
  tokenSummary: null,
  activeView: 'result',
  competitionScan: null,
}

let startTime = 0

export const useTaskStore = create<TaskState & TaskActions>((set) => ({
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

  setActiveView: (view) => set({ activeView: view }),

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
            name: (payload.name as string) || 'Employee',
            avatar: (payload.avatar as string) || '👨‍💼',
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

        case 'TOKEN_USAGE': {
          const entry: TokenUsageEntry = {
            step_label: payload.step_label as string,
            model: payload.model as string,
            source: payload.source as string,
            prompt_tokens: payload.prompt_tokens as number,
            completion_tokens: payload.completion_tokens as number,
            total_tokens: payload.total_tokens as number,
            cost_usd: payload.cost_usd as number,
            latency_ms: payload.latency_ms as number,
            cumulative_tokens: payload.cumulative_tokens as number,
            cumulative_cost_usd: payload.cumulative_cost_usd as number,
          }
          return {
            events: [...state.events.slice(-100), newEvent],
            tokenUsage: [...state.tokenUsage, entry],
          }
        }

        case 'WEB_SEARCH_RESULT': {
          const wsr: WebSearchResult = {
            query: payload.query as string,
            step_label: payload.step_label as string,
            tier_used: payload.tier_used as string,
            sites_checked: payload.sites_checked as number,
            sites_used: payload.sites_used as number,
            is_sufficient: payload.is_sufficient as boolean,
            estimated_tokens_saved: payload.estimated_tokens_saved as number,
            latency_ms: payload.latency_ms as number,
            sources: (payload.sources as { url: string; title: string; snippet: string }[]) || [],
          }
          return {
            events: [...state.events.slice(-100), newEvent],
            webSearchResults: [...state.webSearchResults, wsr],
          }
        }

        case 'TASK_TOKEN_SUMMARY':
          return {
            events: [...state.events.slice(-100), newEvent],
            tokenSummary: payload as unknown as TokenSummary,
          }

        case 'COMPETITOR_SCAN_PROGRESS': {
          const name = payload.name as string
          const status = payload.status as string
          const prev = state.competitionScan
          const scan: CompetitionScan = prev || {
            status: 'scanning',
            own_product: null,
            current_target: null,
            profiles: [],
            matrix_md: '',
            sites_browsed: 0,
            llm_calls: 0,
            tokens_saved: 0,
          }
          if (status === 'browsing') {
            return {
              events: [...state.events.slice(-100), newEvent],
              competitionScan: { ...scan, current_target: name },
            }
          }
          // status === 'done' — upsert the extracted profile
          const profile = payload.profile as unknown as CompetitorProfile
          const others = scan.profiles.filter((p) => p.name !== name)
          return {
            events: [...state.events.slice(-100), newEvent],
            competitionScan: {
              ...scan,
              current_target: null,
              profiles: [...others, profile],
              sites_browsed: scan.sites_browsed + (profile?.sites_checked || 0),
            },
          }
        }

        case 'COMPETITOR_MATRIX_READY': {
          const scan: CompetitionScan = {
            status: 'done',
            own_product: (payload.own_product as string) || null,
            current_target: null,
            profiles: (payload.profiles as unknown as CompetitorProfile[]) || [],
            matrix_md: (payload.matrix_md as string) || '',
            sites_browsed: (payload.sites_browsed as number) || 0,
            llm_calls: (payload.llm_calls_used as number) || 0,
            tokens_saved: (payload.estimated_tokens_saved as number) || 0,
          }
          return {
            events: [...state.events.slice(-100), newEvent],
            competitionScan: scan,
          }
        }

        case 'MCP_TOOL_CALLED':
          return {
            events: [...state.events.slice(-100), newEvent],
          }

        case 'FINAL_RESULT_READY': {
          const finalResultStr = payload.result as string;
          const qualityScoreNum = payload.quality_score as number;
          
          // Save to local history
          if (state.taskId && finalResultStr) {
            import('./historyStore').then(({ useHistoryStore }) => {
              useHistoryStore.getState().addToHistory({
                taskId: state.taskId!,
                title: state.title || 'Untitled Task',
                date: new Date().toISOString(),
                finalResult: finalResultStr,
                qualityScore: qualityScoreNum,
                employees: state.employees,
                steps: state.steps,
                elapsedMs: elapsed,
              })
            })
          }

          return {
            events: [...state.events.slice(-100), newEvent],
            phase: 'completed',
            finalResult: finalResultStr,
            qualityScore: qualityScoreNum,
            elapsedMs: elapsed,
          }
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
