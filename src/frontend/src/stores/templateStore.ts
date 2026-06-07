import { create } from 'zustand'

export interface TemplateData {
  id: string
  source: string
  source_path: string
  name: string
  description: string
  model_tier: string
  tools: string[]
  color: string | null
  display_name_zh: string | null
  description_zh: string | null
  recommended_skills: string[]
  compatible_agent_systems: string[]
  compatible_providers: string[]
  is_enabled: boolean
  is_favorite: boolean
  favorite_name: string | null
  favorite_description: string | null
  favorite_order: number
  created_at: string
  updated_at: string
}

export interface TemplateDetail extends TemplateData {
  system_prompt: string
}

export interface SourceStatus {
  id: string
  url: string
  branch: string
  description_zh: string | null
  enabled: boolean
  template_count: number
  last_synced: string | null
  created_at: string
}

export interface SyncResult {
  source_id: string
  added: number
  updated: number
  deleted: number
  total: number
  error: string | null
}

export interface TemplateCreateInput {
  name: string
  description: string
  system_prompt: string
  model_tier: string
  recommended_skills: string[]
  display_name_zh?: string | null
  description_zh?: string | null
  compatible_agent_systems: string[]
  compatible_providers: string[]
}

async function safeJson(r: Response) {
  const text = await r.text()
  try {
    return JSON.parse(text)
  } catch {
    const preview = text.trim().slice(0, 80)
    throw new Error(preview || `HTTP ${r.status}`)
  }
}

interface TemplateState {
  templates: TemplateData[]
  total: number
  loading: boolean
  error: string
  sourceStatus: SourceStatus | null
  sourceLoading: boolean
  syncing: boolean
  /** Cache of loaded template details keyed by template id */
  detailCache: Record<string, TemplateDetail>
  /** Set of template ids currently loading detail */
  detailLoadingIds: Set<string>

  /** Favorited templates list */
  favorites: TemplateData[]
  /** Loading state for favorites */
  favoritesLoading: boolean

  // Primary actions (Agent 1 naming convention, matching agentStore pattern)
  loadTemplates: (q?: string) => Promise<void>
  syncSource: () => Promise<SyncResult>
  createTemplate: (data: TemplateCreateInput) => Promise<TemplateData>
  updateTemplate: (id: string, data: Partial<TemplateCreateInput>) => Promise<TemplateData>
  deleteTemplate: (id: string) => Promise<void>
  /** Fetch full template detail, with client-side cache. */
  loadTemplateDetail: (id: string) => Promise<TemplateDetail | null>
  /** Synchronous cache lookup; returns undefined if not yet loaded. */
  getCachedDetail: (id: string) => TemplateDetail | undefined
  /** Download template as .md file. */
  exportMarkdown: (id: string) => Promise<void>
  /** Load list of favorited templates */
  loadFavorites: () => Promise<void>
  /** Set or unset a template as favorite */
  setFavorite: (id: string, data: { is_favorite: boolean; favorite_name?: string | null; favorite_description?: string | null }) => Promise<void>

  // Compatibility aliases for components using legacy names
  fetchTemplates: (q?: string) => Promise<void>
  fetchSourceStatus: () => Promise<void>
  getTemplateDetail: (id: string) => Promise<TemplateDetail>
  /** Alias for fetchSourceStatus — matches api/templates naming. */
  getSourceStatus: () => Promise<void>
}

export const useTemplateStore = create<TemplateState>((set, get) => ({
  templates: [],
  total: 0,
  loading: false,
  error: '',
  sourceStatus: null,
  sourceLoading: false,
  syncing: false,
  detailCache: {},
  detailLoadingIds: new Set(),
  favorites: [],
  favoritesLoading: false,

  loadTemplates: async (q) => {
    set({ loading: true, error: '' })
    try {
      const params = new URLSearchParams()
      if (q) params.set('q', q)
      params.set('page_size', '100')
      const r = await fetch(`/api/templates/?${params}`)
      const data = await safeJson(r)
      if (!r.ok) throw new Error(data.detail || '加载模板失败')
      set({ templates: data.items ?? [], total: data.total ?? 0, loading: false })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '加载模板失败', loading: false })
    }
  },

  // Compatibility alias
  fetchTemplates: (q) => get().loadTemplates(q),

  syncSource: async () => {
    set({ syncing: true, error: '' })
    try {
      const r = await fetch('/api/templates/sync', { method: 'POST' })
      const data = await safeJson(r)
      if (!r.ok) throw new Error(data.detail || '同步失败')
      set({ syncing: false })
      get().loadTemplates()
      get().fetchSourceStatus()
      return data
    } catch (e) {
      const msg = e instanceof Error ? e.message : '同步失败'
      set({ error: msg, syncing: false })
      throw e
    }
  },

  createTemplate: async (data) => {
    const r = await fetch('/api/templates/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    const result = await safeJson(r)
    if (!r.ok) throw new Error(result.detail || '创建模板失败')
    set((s) => ({ templates: [...s.templates, result] }))
    return result
  },

  updateTemplate: async (id, data) => {
    const r = await fetch(`/api/templates/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    const result = await safeJson(r)
    if (!r.ok) throw new Error(result.detail || '更新模板失败')
    set((s) => ({
      templates: s.templates.map((t) => (t.id === id ? result : t)),
    }))
    return result
  },

  deleteTemplate: async (id) => {
    const r = await fetch(`/api/templates/${id}`, { method: 'DELETE' })
    if (!r.ok && r.status !== 204) {
      const data = await safeJson(r)
      throw new Error(data.detail || '删除模板失败')
    }
    set((s) => ({
      templates: s.templates.filter((t) => t.id !== id),
      detailCache: (({ [id]: _, ...rest }) => rest)(s.detailCache),
    }))
  },

  getTemplateDetail: async (id) => {
    const r = await fetch(`/api/templates/${id}`)
    const data = await safeJson(r)
    if (!r.ok) throw new Error(data.detail || '加载模板详情失败')
    return data
  },

  loadTemplateDetail: async (id) => {
    const cached = get().detailCache[id]
    if (cached) return cached
    set((s) => ({ detailLoadingIds: new Set(s.detailLoadingIds).add(id) }))
    try {
      const r = await fetch(`/api/templates/${id}`)
      const data = await safeJson(r)
      if (!r.ok) throw new Error(data.detail || '加载模板详情失败')
      set((s) => ({
        detailCache: { ...s.detailCache, [id]: data },
        detailLoadingIds: ((s) => { const n = new Set(s); n.delete(id); return n })(s.detailLoadingIds),
      }))
      return data as TemplateDetail
    } catch {
      set((s) => ({
        detailLoadingIds: ((s) => { const n = new Set(s); n.delete(id); return n })(s.detailLoadingIds),
      }))
      return null
    }
  },

  getCachedDetail: (id) => {
    return get().detailCache[id]
  },

  exportMarkdown: async (id) => {
    const r = await fetch(`/api/templates/${id}/export`)
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d.detail || '导出失败')
    }
    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const disposition = r.headers.get('Content-Disposition') || ''
    const m = disposition.match(/filename="?([^"]+)"?/)
    const template = get().templates.find((t) => t.id === id)
    a.download = (m && m[1]) ? m[1] : (template?.name ?? 'template') + '.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  loadFavorites: async () => {
    set({ favoritesLoading: true })
    try {
      const r = await fetch('/api/templates/favorites')
      const data = await safeJson(r)
      if (!r.ok) throw new Error(data.detail || '加载常用模板失败')
      set({ favorites: data ?? [], favoritesLoading: false })
    } catch {
      set({ favoritesLoading: false })
    }
  },

  setFavorite: async (id, data) => {
    const r = await fetch(`/api/templates/${id}/favorite`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    const result = await safeJson(r)
    if (!r.ok) throw new Error(result.detail || '更新常用状态失败')
    // Refresh both templates list and favorites list
    get().loadTemplates()
    get().loadFavorites()
  },

  fetchSourceStatus: async () => {
    set({ sourceLoading: true })
    try {
      const r = await fetch('/api/templates/source/status')
      if (r.status === 404) {
        set({ sourceStatus: null, sourceLoading: false })
        return
      }
      const data = await safeJson(r)
      set({ sourceStatus: data, sourceLoading: false })
    } catch {
      set({ sourceLoading: false })
    }
  },

  getSourceStatus: () => get().fetchSourceStatus(),
}))
