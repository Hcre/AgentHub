/* eslint-disable react-refresh/only-export-components */
import { useState } from 'react'
import { Button, Icon } from '../ui'

// ── 类型 ──────────────────────────────────────────────────────────────

export interface SkillMdData {
  name: string
  description?: string
  triggers?: string
  version?: string
  model?: string
  body: string
}

// ── 检测逻辑 ──────────────────────────────────────────────────────────

/**
 * 从消息文本中检测 SKILL.md 草稿（markdown 围栏内含 YAML frontmatter）。
 * 返回 `{ found: true, data }` 或 `{ found: false }`。
 */
export function detectSkillMd(content: string): { found: false } | { found: true; data: SkillMdData } {
  // 匹配 ```markdown / ```md / ``` 围栏，内部以 --- YAML frontmatter 开头
  const mdBlockRegex = /```(?:markdown|md)?\s*\n(---[\s\S]*?---[\s\S]*?)```/g
  const match = mdBlockRegex.exec(content)
  if (!match || !match[1]) return { found: false }

  const full = match[1]
  const fmMatch = full.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/)
  if (!fmMatch || !fmMatch[1] || !fmMatch[2]) return { found: false }

  const yamlRaw = fmMatch[1]
  const body = fmMatch[2]
  const yaml: Record<string, string> = {}
  yamlRaw.split('\n').forEach((line) => {
    const colonIdx = line.indexOf(':')
    if (colonIdx > 0) {
      const key = line.slice(0, colonIdx).trim()
      const value = line.slice(colonIdx + 1).trim()
      yaml[key] = value
    }
  })

  // 至少要有 name 字段，才算有效的 SKILL.md
  if (!yaml.name) return { found: false }

  return {
    found: true,
    data: {
      name: yaml.name,
      description: yaml.description,
      triggers: yaml.triggers,
      version: yaml.version,
      model: yaml.model,
      body,
    },
  }
}

// ── 预览面板组件 ──────────────────────────────────────────────────────

/**
 * 在消息气泡下方渲染 SKILL.md 草稿预览面板。
 * 显示 YAML frontmatter 解析出的元数据 + body 预览 + 保存/修改按钮。
 */
export function SkillMdPreview({
  data,
  onSaveSuccess,
}: {
  data: SkillMdData
  onSaveSuccess?: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  const bodyLines = data.body.split('\n')
  const previewLines = expanded ? bodyLines : bodyLines.slice(0, 3)
  const hasMore = bodyLines.length > 3

  const handleSave = async () => {
    if (saving || saved) return
    setSaving(true)
    setError('')
    try {
      const resp = await fetch('/api/skills/library/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: data.name,
          description: data.description ?? '',
          triggers: data.triggers ?? '',
          version: data.version ?? '1.0.0',
          body: data.body,
        }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail ?? `保存失败 (${resp.status})`)
      }
      setSaved(true)
      onSaveSuccess?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleModify = () => {
    // 把 body 复制到剪贴板，用户可以粘贴到编辑器修改
    const fullContent = [
      '---',
      `name: ${data.name}`,
      data.description && `description: ${data.description}`,
      data.triggers && `triggers: ${data.triggers}`,
      data.version && `version: ${data.version}`,
      data.model && `model: ${data.model}`,
      '---',
      '',
      data.body,
    ]
      .filter(Boolean)
      .join('\n')

    navigator.clipboard.writeText(fullContent).then(
      () => {
        setError('')
      },
      () => {
        setError('复制到剪贴板失败')
      },
    )
  }

  return (
    <div className="mt-2.5 rounded-lg border border-brand/25 bg-brand/[0.04] p-3">
      {/* 标题栏 */}
      <div className="flex items-center gap-2 mb-2.5">
        <Icon name="sparkle" className="h-4 w-4 text-brand" />
        <span className="text-[12.5px] font-medium text-brand">SKILL.md 预览</span>
      </div>

      {/* YAML 元数据网格 */}
      <div className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-[12px]">
        <span className="text-muted-foreground">名称</span>
        <span className="font-medium text-foreground">{data.name}</span>
        {data.description && (
          <>
            <span className="text-muted-foreground">描述</span>
            <span className="text-foreground/80">{data.description}</span>
          </>
        )}
        {data.triggers && (
          <>
            <span className="text-muted-foreground">触发词</span>
            <span className="font-mono text-[11px] text-foreground/80">{data.triggers}</span>
          </>
        )}
        {data.version && (
          <>
            <span className="text-muted-foreground">版本</span>
            <span className="font-mono text-[11px]">{data.version}</span>
          </>
        )}
      </div>

      {/* Body 预览区 */}
      <div className="mt-2.5 rounded-md border bg-muted/30 p-2.5">
        <div className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap break-words leading-relaxed">
          {previewLines.map((line, i) => (
            <div key={i}>{line || ' '}</div>
          ))}
          {!expanded && hasMore && (
            <div className="text-muted-foreground/50">...</div>
          )}
        </div>
        {hasMore && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="mt-1.5 text-[11px] text-brand hover:underline"
          >
            {expanded ? '收起' : `展开（共 ${bodyLines.length} 行）`}
          </button>
        )}
      </div>

      {/* 错误提示 */}
      {error && (
        <div
          role="alert"
          className="mt-2.5 rounded-md bg-red-50 px-2.5 py-1.5 text-[11px] text-red-600 dark:bg-red-950 dark:text-red-400"
        >
          {error}
        </div>
      )}

      {/* 操作按钮 */}
      <div className="mt-3 flex items-center gap-2">
        <Button
          variant="brand"
          size="sm"
          onClick={handleSave}
          disabled={saving || saved}
          data-testid="skill-md-save-btn"
        >
          <Icon name={saved ? 'check' : 'plus'} className="h-3.5 w-3.5" />
          {saving ? '保存中…' : saved ? '已保存' : '保存到技能库'}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleModify}
          title="复制完整 SKILL.md 到剪贴板"
          data-testid="skill-md-modify-btn"
        >
          <Icon name="pencil" className="h-3.5 w-3.5" />
          修改
        </Button>
      </div>
    </div>
  )
}
