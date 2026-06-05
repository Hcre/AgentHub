import { Dialog, DialogContent, Button, Icon } from '../ui'

export interface HelpModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * 帮助与反馈入口：从 NavRail 底部 ? 按钮唤起。
 * 内容占位（具体文档/反馈渠道后续按 Phase 接入）。
 */
export function HelpModal({ open, onOpenChange }: HelpModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[460px]">
        <header className="flex items-start gap-3 border-b border-border/70 p-4">
          <div className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="info" className="h-4 w-4" strokeWidth={2} />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] font-semibold leading-tight">帮助与反馈</h2>
            <p className="mt-1 text-[12.5px] text-muted-foreground">
              遇到问题或有改进建议？这里汇总了常用入口。
            </p>
          </div>
        </header>

        <div className="space-y-3 p-4 text-[13.5px] text-foreground/90">
          <section>
            <div className="mb-1 font-medium">快捷键</div>
            <ul className="space-y-1 text-muted-foreground">
              <li>
                <span className="font-mono text-[12px]">⌘ K</span> · 快速跳转到会话/Agent/群组
              </li>
              <li>
                <span className="font-mono text-[12px]">⌘ B</span> · 折叠/展开会话列表
              </li>
              <li>
                <span className="font-mono text-[12px]">⌘ /</span> · 切换暗/亮色
              </li>
            </ul>
          </section>

          <section>
            <div className="mb-1 font-medium">反馈渠道</div>
            <ul className="space-y-1 text-muted-foreground">
              <li>· 文档：`docs/` 目录（按域分子目录）</li>
              <li>· Issue：在仓库开 issue，附截图与复现步骤</li>
              <li>· 实时：群组中 @ 协调者 Agent 描述问题</li>
            </ul>
          </section>

          <p className="text-[11.5px] text-muted-foreground/80">
            占位内容，Phase 后续接入完整文档与反馈通道。
          </p>
        </div>

        <footer className="flex justify-end gap-2 border-t border-border/70 p-3">
          <Button variant="default" size="sm" onClick={() => onOpenChange(false)}>
            知道了
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
