import { CheckCircle2, ExternalLink, Loader2, Rocket, TriangleAlert, Clock } from 'lucide-react'
import type { DeployCard as DeployCardData, DeployStatus } from '../../types'

/**
 * DeployCard — Agent 消息下挂的部署状态卡（与 backend `DeploymentStatus` 对齐）。
 *
 * 4 状态色 + 4 图标 + 4 行为：
 *   - queued: 灰底 + Clock + 不可交互（显示「排队中」）
 *   - building: 蓝底 + Loader2 旋转 + 进度条（progress 0~1）
 *   - ready: 绿底 + CheckCircle2 + 「打开预览」按钮（点 window.open(deploy_url)）
 *   - failed: 红底 + TriangleAlert + 错误码 + 错误信息
 *
 * 视觉：
 *   - 状态色走 Tailwind semantic classes（emerald/blue/rose/zinc），不引额外色板
 *   - 进度条用纯 CSS transition（width）+ step 标签（stage）
 *   - deploy_url 域截断到 60 字符（移动端友好）
 *
 * 测试覆盖（MessageBubble.deploy.test.tsx 间接覆盖）：
 *   - 4 状态色 + 4 状态文案 + deploy_url 显示
 *   - ready 状态「打开预览」按钮可点 + window.open 调用
 *   - failed 状态显示 error_code + error_message
 */
const STATUS_STYLES: Record<DeployStatus, { wrap: string; icon: string; label: string }> = {
  queued: {
    wrap: 'border-zinc-300 bg-zinc-100/60 dark:bg-zinc-900/40 dark:border-zinc-700',
    icon: 'text-zinc-500',
    label: '排队中',
  },
  building: {
    wrap: 'border-blue-300 bg-blue-50/60 dark:bg-blue-950/30 dark:border-blue-800',
    icon: 'text-blue-500',
    label: '构建中',
  },
  ready: {
    wrap: 'border-emerald-300 bg-emerald-50/60 dark:bg-emerald-950/30 dark:border-emerald-800',
    icon: 'text-emerald-600 dark:text-emerald-400',
    label: '已就绪',
  },
  failed: {
    wrap: 'border-rose-300 bg-rose-50/60 dark:bg-rose-950/30 dark:border-rose-800',
    icon: 'text-rose-500',
    label: '部署失败',
  },
}

const STATUS_ICON: Record<DeployStatus, typeof Clock> = {
  queued: Clock,
  building: Loader2,
  ready: CheckCircle2,
  failed: TriangleAlert,
}

const TARGET_LABEL: Record<DeployCardData['target'], string> = {
  static_site: '静态站点',
  container: '容器',
  package: '源码包',
}

export function DeployCardView({ card }: { card: DeployCardData }) {
  const styles = STATUS_STYLES[card.status]
  const IconCmp = STATUS_ICON[card.status]
  const progressPct = Math.round((card.progress ?? (card.status === 'ready' ? 1 : 0)) * 100)

  return (
    <div
      data-testid="deploy-card"
      data-status={card.status}
      className={`mt-2 w-full max-w-[480px] rounded-lg border p-3 transition-colors ${styles.wrap}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <IconCmp
            className={`h-4 w-4 flex-shrink-0 ${styles.icon} ${card.status === 'building' ? 'animate-spin' : ''}`}
            strokeWidth={1.75}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[12px] font-semibold tracking-tight">
                {styles.label}
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {TARGET_LABEL[card.target]}
                {card.framework ? ` · ${card.framework}` : ''}
                {card.entry_file ? ` · ${card.entry_file}` : ''}
              </span>
            </div>
            <div className="font-mono text-[10.5px] text-muted-foreground">
              部署 ID: {card.id.slice(0, 8)} · TTL {card.ttl ?? 3600}s
            </div>
          </div>
        </div>
        {/* ready 状态：右上「打开预览」按钮 */}
        {card.status === 'ready' && card.deploy_url && (
          <button
            type="button"
            data-testid="deploy-open-btn"
            onClick={() => window.open(card.deploy_url ?? '', '_blank', 'noopener,noreferrer')}
            className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-100/60 px-2.5 py-1 font-mono text-[11px] font-medium text-emerald-700 transition-colors hover:bg-emerald-200/60 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 dark:hover:bg-emerald-900/60"
            title={card.deploy_url}
          >
            <Rocket className="h-3 w-3" strokeWidth={1.75} />
            <span>打开预览</span>
            <ExternalLink className="h-2.5 w-2.5" strokeWidth={1.75} />
          </button>
        )}
      </div>

      {/* building 状态：进度条 + 阶段标签 */}
      {(card.status === 'building' || card.status === 'queued') && (
        <div className="mt-2.5 space-y-1.5">
          <div className="flex items-center justify-between font-mono text-[10.5px] text-muted-foreground">
            <span>{card.stage ?? (card.status === 'queued' ? '等待 worker' : '准备中')}</span>
            <span data-testid="deploy-progress">{progressPct}%</span>
          </div>
          <div className="h-1 w-full overflow-hidden rounded-full bg-foreground/10">
            <div
              className={`h-full transition-all duration-300 ease-out ${
                card.status === 'queued' ? 'bg-zinc-400' : 'bg-blue-500'
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* ready 状态：deploy_url 单行展示 */}
      {card.status === 'ready' && card.deploy_url && (
        <a
          href={card.deploy_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 block truncate rounded border border-emerald-200/60 bg-background/60 px-2 py-1 font-mono text-[11px] text-emerald-700 underline-offset-2 hover:underline dark:border-emerald-800/60 dark:text-emerald-300"
          data-testid="deploy-url"
        >
          {card.deploy_url}
        </a>
      )}

      {/* failed 状态：错误码 + 错误信息 */}
      {card.status === 'failed' && (
        <div className="mt-2 space-y-1 rounded border border-rose-200/60 bg-background/60 p-2 font-mono text-[11px] dark:border-rose-800/60">
          {card.error_code && (
            <div className="font-semibold text-rose-700 dark:text-rose-300" data-testid="deploy-error-code">
              {card.error_code}
            </div>
          )}
          {card.error_message && (
            <div className="text-rose-600/90 dark:text-rose-300/80" data-testid="deploy-error-msg">
              {card.error_message}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
