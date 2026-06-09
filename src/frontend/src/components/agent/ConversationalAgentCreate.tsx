/**
 * ConversationalAgentCreate — M1#4 对话式创建 Agent（owner override）
 *
 * 用户自然语言描述需求 → 调 draft-from-chat 端点 → 展示草稿卡
 * → 用户可编辑 → 确认调 createAgent → 跳转详情页
 *
 * 注意：当前为降级实现（启发式抽取），真实 LLM 接入后无需改 UI。
 */
import { useState } from 'react'
import { agentsApi, type AgentDraft } from '../../api/agents'
import { Button, Icon } from '../ui'

interface Props {
  onCreated: (agentId: string) => void
  onCancel: () => void
}

export function ConversationalAgentCreate({ onCreated, onCancel }: Props) {
  const [step, setStep] = useState<'input' | 'preview'>('input')
  const [description, setDescription] = useState('')
  const [draft, setDraft] = useState<AgentDraft | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleGenerate = async () => {
    if (!description.trim()) return
    setLoading(true)
    setError(null)
    try {
      const d = await agentsApi.draftFromChat(description.trim())
      setDraft(d)
      setStep('preview')
    } catch (err) {
      setError((err as Error).message ?? '草稿生成失败')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async () => {
    if (!draft) return
    setSubmitting(true)
    setError(null)
    try {
      const created = await agentsApi.create({
        name: draft.name,
        avatar: '🤖',
        role: draft.role,
        agent_system: 'mock',
        skills: draft.skills,
        system_prompt: draft.system_prompt,
      })
      onCreated(created.id)
    } catch (err) {
      setError((err as Error).message ?? '创建失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-full flex-col p-4">
      {step === 'input' ? (
        <>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-[14px] font-semibold">对话式创建 Agent</h2>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                描述你想让这个 Agent 做什么，系统会自动抽取配置
              </p>
            </div>
            <button
              onClick={onCancel}
              className="rounded p-1 text-muted-foreground hover:bg-accent"
              title="取消"
            >
              <Icon name="x" className="h-3.5 w-3.5" />
            </button>
          </div>

          <textarea
            data-testid="conv-agent-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="例：帮我建一个前端代码审查 Agent，关注 React 性能和安全"
            className="min-h-[120px] flex-1 resize-none rounded border bg-background p-3 text-[13px] outline-none placeholder:text-muted-foreground/60 focus:border-brand"
            disabled={loading}
          />

          {error && (
            <div className="mt-2 rounded border border-destructive/30 bg-destructive/10 p-2 text-[11px] text-destructive">
              ⚠️ {error}
            </div>
          )}

          <div className="mt-3 flex justify-end gap-2">
            <Button variant="ghost" onClick={onCancel}>
              取消
            </Button>
            <Button
              onClick={handleGenerate}
              disabled={!description.trim() || loading}
              data-testid="conv-agent-generate"
            >
              {loading ? '生成中…' : '生成草稿'}
            </Button>
          </div>
        </>
      ) : (
        draft && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-[14px] font-semibold">确认 Agent 配置</h2>
              <button
                onClick={() => setStep('input')}
                className="text-[11px] text-muted-foreground hover:text-foreground"
              >
                ← 重新描述
              </button>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto">
              <Field label="名称">
                <input
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  className="w-full rounded border bg-background px-2 py-1.5 text-[13px] outline-none focus:border-brand"
                />
              </Field>
              <Field label="角色">
                <input
                  value={draft.role}
                  onChange={(e) => setDraft({ ...draft, role: e.target.value })}
                  className="w-full rounded border bg-background px-2 py-1.5 text-[13px] outline-none focus:border-brand"
                />
              </Field>
              <Field label="技能（逗号分隔）">
                <input
                  value={draft.skills.join(', ')}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      skills: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                    })
                  }
                  className="w-full rounded border bg-background px-2 py-1.5 text-[13px] outline-none focus:border-brand"
                />
              </Field>
              <Field label="System Prompt">
                <textarea
                  value={draft.system_prompt}
                  onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })}
                  className="min-h-[100px] w-full rounded border bg-background px-2 py-1.5 text-[12px] outline-none focus:border-brand"
                />
              </Field>
            </div>

            {error && (
              <div className="mt-2 rounded border border-destructive/30 bg-destructive/10 p-2 text-[11px] text-destructive">
                ⚠️ {error}
              </div>
            )}

            <div className="mt-3 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setStep('input')}>
                返回
              </Button>
              <Button
                onClick={handleConfirm}
                disabled={!draft.name.trim() || submitting}
                data-testid="conv-agent-confirm"
              >
                {submitting ? '创建中…' : '确认创建'}
              </Button>
            </div>
          </>
        )
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  )
}