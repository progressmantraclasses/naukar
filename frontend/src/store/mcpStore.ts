import { create } from 'zustand'

const API_BASE = 'http://localhost:8000'

export interface MCPServer {
  id: string
  name: string
  transport: 'stdio' | 'sse' | 'http'
  command: string
  args: string[]
  env: Record<string, string>
  url: string
  enabled: boolean
  status: 'disconnected' | 'connecting' | 'connected' | 'error'
  error: string
  tools: string[]
}

export interface MCPPreset {
  key: string
  name: string
  description: string
  transport: string
  command: string
  args: string[]
  env_keys: string[]
}

interface AddServerInput {
  name: string
  transport: 'stdio' | 'sse' | 'http'
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
}

interface MCPState {
  servers: MCPServer[]
  presets: MCPPreset[]
  isLoading: boolean
  error: string | null
  fetchServers: () => Promise<void>
  fetchPresets: () => Promise<void>
  addServer: (input: AddServerInput) => Promise<boolean>
  removeServer: (id: string) => Promise<void>
  reconnectServer: (id: string) => Promise<void>
}

export const useMCPStore = create<MCPState>((set, get) => ({
  servers: [],
  presets: [],
  isLoading: false,
  error: null,

  fetchServers: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/mcp/servers`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const servers = await res.json()
      set({ servers, error: null })
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to load MCP servers' })
    }
  },

  fetchPresets: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/mcp/presets`)
      if (!res.ok) return
      const data = await res.json()
      set({ presets: data.presets || [] })
    } catch {
      /* presets are optional */
    }
  },

  addServer: async (input) => {
    set({ isLoading: true, error: null })
    try {
      const res = await fetch(`${API_BASE}/api/mcp/servers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...input, connect_now: true }),
      })
      const data = await res.json()
      if (!res.ok) {
        set({ isLoading: false, error: data.detail || 'Failed to add server' })
        return false
      }
      set({ isLoading: false })
      await get().fetchServers()
      return true
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to add server',
      })
      return false
    }
  },

  removeServer: async (id) => {
    try {
      await fetch(`${API_BASE}/api/mcp/servers/${id}`, { method: 'DELETE' })
      set({ servers: get().servers.filter((s) => s.id !== id) })
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to remove server' })
    }
  },

  reconnectServer: async (id) => {
    try {
      await fetch(`${API_BASE}/api/mcp/servers/${id}/reconnect`, { method: 'POST' })
      await get().fetchServers()
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Reconnect failed' })
    }
  },
}))
