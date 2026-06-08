import { useEffect, useState } from 'react'
import { Dialog, DialogContent, Button, Icon } from '../ui'

interface UsageResp {
  window: string
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  since: string
  by_agent: { agent_id: string; total_tokens: number }[]
}

const WINDOWS = ['1h', '24h', '7d'] as const

export function TokenMonitorPanel({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [data, setData] = useState<Record<string, UsageResp | null>>({})
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setErr(null)
    Promise.all(
      WINDOWS.map(async (w) => {
        const r = await fetch(`/api/usage/global?window=${w}`)
        if (!r.ok) throw new Error(`HTTP ${r.status} for window=${w}`)
        return [w, (await r.json()) as UsageResp] as const
      })
    )
      .then((entries) => {
        setData(Object.fromEntries(entries))
        setLoading(false)
      })
      .catch((e) => {
        setErr(String(e))
        setLoading(false)
      })
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[680px]">
        <header className="border-b p-4">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <Icon name="activity" className="h-4 w-4" />
            Token 消耗监控
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            实时显示全平台 1h / 24h / 7d 窗口消耗
          </p>
        </header>
        <div className="grid grid-cols-3 gap-3 p-4">
          {WINDOWS.map((w) => (
            <div
              key={w}
              className="rounded-lg border p-3"
              data-testid={`usage-card-${w}`}
            >
              <div className="text-xs text-muted-foreground">{w} 消耗</div>
              <div className="mt-1 font-mono text-2xl font-semibold">
                {data[w]?.total_tokens ?? '—'}
              </div>
              <div className="mt-1 text-[10px] text-muted-foreground">
                prompt {data[w]?.prompt_tokens ?? 0} · completion{' '}
                {data[w]?.completion_tokens ?? 0}
              </div>
            </div>
          ))}
        </div>
        {err && (
          <div className="px-4 text-xs text-destructive" data-testid="usage-error">
            {err}
          </div>
        )}
        {loading && (
          <div className="px-4 text-xs text-muted-foreground" data-testid="usage-loading">
            加载中...
          </div>
        )}
        <footer className="flex justify-between border-t p-3 text-xs text-muted-foreground">
          <span>Top agent: {data['24h']?.by_agent?.[0]?.agent_id?.slice(0, 8) ?? '—'}</span>
          <Button onClick={() => onOpenChange(false)}>关闭</Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
