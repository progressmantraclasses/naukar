import { create } from 'zustand'

const API_BASE = 'http://localhost:8000'
const TOKEN_KEY = 'naukar_token'

export interface AuthUser {
  user_id: string
  email: string
  workspace_id: string
  role: string
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

interface AuthActions {
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  clearError: () => void
  restoreSession: () => void
  getAuthHeaders: () => Record<string, string>
}

export const useAuthStore = create<AuthState & AuthActions>((set, get) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  restoreSession: () => {
    try {
      const token = localStorage.getItem(TOKEN_KEY)
      if (!token) return
      // Decode JWT payload (no verification needed client-side)
      const payloadB64 = token.split('.')[1]
      if (!payloadB64) return
      const payload = JSON.parse(atob(payloadB64))
      // Check expiry
      if (payload.exp && payload.exp * 1000 < Date.now()) {
        localStorage.removeItem(TOKEN_KEY)
        return
      }
      set({
        token,
        isAuthenticated: true,
        user: {
          user_id: payload.sub,
          email: payload.email,
          workspace_id: payload.workspace_id,
          role: payload.role,
        },
      })
    } catch {
      localStorage.removeItem(TOKEN_KEY)
    }
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json().catch(() => ({ detail: `HTTP ${res.status} response from server` }))
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      localStorage.setItem(TOKEN_KEY, data.access_token)
      set({
        token: data.access_token,
        isAuthenticated: true,
        isLoading: false,
        user: { user_id: data.user_id, email: data.email, workspace_id: data.workspace_id, role: data.role },
      })
    } catch (err: unknown) {
      const msg = err instanceof TypeError && err.message.includes('fetch')
        ? 'Cannot reach backend at http://localhost:8000. Is the backend server running?'
        : err instanceof Error ? err.message : 'Login failed'
      console.error('Auth login error:', err)
      set({ isLoading: false, error: msg })
      throw err
    }
  },

  register: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json().catch(() => ({ detail: `HTTP ${res.status} response from server` }))
      if (!res.ok) throw new Error(data.detail || 'Registration failed')
      localStorage.setItem(TOKEN_KEY, data.access_token)
      set({
        token: data.access_token,
        isAuthenticated: true,
        isLoading: false,
        user: { user_id: data.user_id, email: data.email, workspace_id: data.workspace_id, role: data.role },
      })
    } catch (err: unknown) {
      const msg = err instanceof TypeError && err.message.includes('fetch')
        ? 'Cannot reach backend at http://localhost:8000. Is the backend server running?'
        : err instanceof Error ? err.message : 'Registration failed'
      console.error('Auth register error:', err)
      set({ isLoading: false, error: msg })
      throw err
    }
  },


  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    set({ token: null, user: null, isAuthenticated: false, error: null })
  },

  clearError: () => set({ error: null }),

  getAuthHeaders: () => {
    const token = get().token
    return token ? { Authorization: `Bearer ${token}` } : {}
  },
}))

