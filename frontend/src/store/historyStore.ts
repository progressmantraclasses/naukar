import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Employee, TaskStep } from './taskStore'

export interface HistoryItem {
  taskId: string
  title: string
  date: string
  finalResult: string
  qualityScore: number | null
  employees: Employee[]
  steps: TaskStep[]
  elapsedMs: number
}

interface HistoryState {
  history: HistoryItem[]
  addToHistory: (item: HistoryItem) => void
  removeFromHistory: (taskId: string) => void
  clearHistory: () => void
}

export const useHistoryStore = create<HistoryState>()(
  persist(
    (set) => ({
      history: [],
      addToHistory: (item) =>
        set((state) => {
          // Prevent duplicates
          if (state.history.some((h) => h.taskId === item.taskId)) return state
          return { history: [item, ...state.history] }
        }),
      removeFromHistory: (taskId) =>
        set((state) => ({
          history: state.history.filter((h) => h.taskId !== taskId),
        })),
      clearHistory: () => set({ history: [] }),
    }),
    {
      name: 'naukar-task-history', // key in localStorage
    }
  )
)
