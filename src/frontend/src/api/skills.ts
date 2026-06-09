// Skill library 客户端封装：把散落在组件里的裸 fetch('/api/skills/library/...')
// 收拢到一处。仅覆盖 library 系列 5 端点（list/create/generate/delete/batch-delete）；
// marketplace 系列是另一关注点，保持各组件自管。

const BASE = import.meta.env.VITE_API_BASE_URL || ''

/** 后端 GET /api/skills/library 单条返回。 */
export interface SkillLibraryItem {
  name: string
  path: string
  rel_path: string
  source: string
  description: string
  author: string
  version: string
  installed_at: number
}

/** create 端点接受两种 body 形态（手写表单字段 / SKILL.md 草稿），统一为宽松 record。 */
export type CreateSkillBody = Record<string, unknown>

/** generate 端点返回的 skill 字段草稿。 */
export interface GenerateSkillResult {
  name?: string
  description?: string
  triggers?: string[]
  instructions?: string
  [k: string]: unknown
}

/** 从非 2xx 响应提取后端 {detail} 文案，回退到状态码——保持各组件原有错误 UX。 */
async function detailError(r: Response): Promise<never> {
  const d = (await r.json().catch(() => ({}))) as { detail?: string }
  throw new Error(d.detail ?? `请求失败 (${r.status})`)
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) return detailError(r)
  return (await r.json().catch(() => ({}))) as T
}

export const skillsApi = {
  /** 已安装 skill 列表（带 cache-busting，确保拿到刚装的）。 */
  listLibrary: async (): Promise<SkillLibraryItem[]> => {
    const r = await fetch(`${BASE}/api/skills/library?_=${Date.now()}`)
    if (!r.ok) return detailError(r)
    return (await r.json().catch(() => [])) as SkillLibraryItem[]
  },
  /** 手写表单 / SKILL.md 草稿创建 skill。 */
  createLibrary: <T = unknown>(body: CreateSkillBody): Promise<T> =>
    postJson<T>('/api/skills/library/create', body),
  /** AI 根据描述生成 skill 字段草稿。 */
  generateLibrary: (description: string): Promise<GenerateSkillResult> =>
    postJson<GenerateSkillResult>('/api/skills/library/generate', { description }),
  /** 删除单个 skill（force=true 即使有 Agent 引用也删）。 */
  removeLibrary: async (name: string, force = false): Promise<void> => {
    const qs = force ? '?force=true' : ''
    const r = await fetch(`${BASE}/api/skills/library/${encodeURIComponent(name)}${qs}`, {
      method: 'DELETE',
    })
    if (!r.ok) return detailError(r)
  },
  /** 批量删除 skill。 */
  batchDeleteLibrary: (names: string[]): Promise<{ deleted?: string[] }> =>
    postJson('/api/skills/library/batch-delete', { names }),
}
