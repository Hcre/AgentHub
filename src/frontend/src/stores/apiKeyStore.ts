import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { uid } from '../lib/id'

export interface ApiKeyEntry {
  id: string
  name: string
  provider: string
  keyPrefix: string
  apiKey: string
  baseUrl: string
  model: string
  createdAt: number
}

interface ApiKeyState {
  keys: ApiKeyEntry[]
  coordinatorCredentialId: string | null
  addKey: (data: { name: string; provider: string; apiKey: string; baseUrl?: string; model?: string }) => void
  removeKey: (id: string) => void
  setCoordinatorCredential: (id: string | null) => void
}

export const PROVIDER_LABELS: Record<string, string> = {
  deepseek: 'DeepSeek',
  xiaomi: 'Xiaomi MiMo',
  minimax: 'MiniMax',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  siliconflow: '硅基流动',
  other: '其他',
}

export const useApiKeyStore = create<ApiKeyState>()(
  persist(
    (set, get) => ({
      keys: [],
      coordinatorCredentialId: null,

      addKey: (data) => {
        const entry: ApiKeyEntry = {
          id: uid('ak'),
          name: data.name.trim(),
          provider: data.provider,
          keyPrefix: data.apiKey.slice(0, 4),
          apiKey: data.apiKey,
          baseUrl: (data.baseUrl || '').trim(),
          model: (data.model || '').trim(),
          createdAt: Date.now(),
        }
        set({ keys: [...get().keys, entry] })
      },

      removeKey: (id) => {
        set((s) => {
          const next = s.keys.filter((k) => k.id !== id)
          return { keys: next, coordinatorCredentialId: s.coordinatorCredentialId === id ? null : s.coordinatorCredentialId }
        })
      },

      setCoordinatorCredential: (id) => set({ coordinatorCredentialId: id }),
    }),
    { name: 'agenthub-apikeys' },
  ),
)
