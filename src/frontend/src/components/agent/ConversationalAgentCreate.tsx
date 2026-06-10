import { useState } from 'react'
import { agentsApi, type AgentDraft } from '../../api/agents'
import { useAgentStore } from '../../stores/agentStore'

/**
 * 对话式创建 Agent：用一句话描述想要的队友 → LLM 抽取结构化草稿（name/role/avatar/
 * system_prompt/能力标签）→ 预览可改 → 确认落库（POST /api/agents，agent_system=mock，
 * 用户随后可在详情里改运行时）。
 */
export function ConversationalAgentCreate({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [desc, setDesc] = useState('')
  const [draft, setDraft] = useState<AgentDraft | null>(null)
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loadAgents = useAgentStore((s) => s.loadAgents)

  if (!open) return null

  const reset = () => {
    setDesc('')
    setDraft(null)
    setError(null)
  }

  const generate = async () => {
    if (!desc.trim()) return
    setLoading(true)
    setError(null)
    try {
      setDraft(await agentsApi.draftFromChat(desc.trim()))
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成草稿失败')
    } finally {
      setLoading(false)
    }
  }

  const confirm = async () => {
    if (!draft) return
    setCreating(true)
    setError(null)
    try {
      await agentsApi.create({
        name: draft.name,
        avatar: draft.avatar,
        role: draft.role,
        agent_system: 'mock',
        system_prompt: draft.system_prompt,
        capability_tags: draft.capability_tags,
      })
      await loadAgents()
      reset()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      data-testid="conv-agent-create"
    >
      <div
        className="w-full max-w-lg rounded-xl border bg-background p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">✨ 对话式创建队友</h2>
          <button type="button" onClick={onClose} aria-label="关闭" className="text-muted-foreground hover:text-foreground">
            ✕
          </button>
        </div>

        <label className="mb-1 block text-[12px] text-muted-foreground">用一句话描述你想要的队友</label>
        <textarea
          autoFocus
          rows={3}
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          placeholder="例如：一个擅长 React 性能优化、说话简洁、会主动指出反模式的前端专家"
          className="w-full resize-none rounded-md border bg-background px-3 py-2 text-[13px] outline-none focus:border-brand/40"
        />
        <div className="mt-2 flex justify-end">
          <button
            type="button"
            data-testid="conv-generate-btn"
            disabled={!desc.trim() || loading}
            onClick={generate}
            className="rounded-md bg-brand px-3 py-1.5 text-[13px] font-medium text-brand-foreground disabled:opacity-50"
          >
            {loading ? '生成中…' : 'AI 生成草稿'}
          </button>
        </div>

        {error && <div className="mt-2 text-[12px] text-destructive" data-testid="conv-error">{error}</div>}

        {draft && (
          <div className="mt-4 space-y-2 rounded-lg border bg-muted/20 p-3" data-testid="conv-draft-preview">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{draft.avatar}</span>
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="flex-1 rounded border bg-background px-2 py-1 text-[14px] font-medium"
              />
            </div>
            <input
              value={draft.role}
              onChange={(e) => setDraft({ ...draft, role: e.target.value })}
              placeholder="角色定位"
              className="w-full rounded border bg-background px-2 py-1 text-[12.5px] text-muted-foreground"
            />
            <textarea
              rows={4}
              value={draft.system_prompt}
              onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })}
              className="w-full resize-none rounded border bg-background px-2 py-1 font-mono text-[12px]"
            />
            <div className="flex flex-wrap gap-1">
              {draft.capability_tags.map((t) => (
                <span key={t} className="rounded-full border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
                  {t}
                </span>
              ))}
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={generate} disabled={loading} className="rounded border px-3 py-1.5 text-[12.5px] text-muted-foreground hover:bg-accent">
                重新生成
              </button>
              <button
                type="button"
                data-testid="conv-create-btn"
                onClick={confirm}
                disabled={creating || !draft.name.trim()}
                className="rounded-md bg-brand px-3 py-1.5 text-[12.5px] font-medium text-brand-foreground disabled:opacity-50"
              >
                {creating ? '创建中…' : '创建队友'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
