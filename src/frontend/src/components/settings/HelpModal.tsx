import { Dialog, DialogContent, Button, Icon } from '../ui'

export interface HelpModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * 帮助与反馈入口：从 NavRail 底部 ? 按钮唤起。
 * 展示产品核心使用流程 + 反馈渠道。
 */
export function HelpModal({ open, onOpenChange }: HelpModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[480px]">
        <header className="flex items-start gap-3 border-b border-border/70 p-4">
          <div className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="info" className="h-4 w-4" strokeWidth={2} />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] font-semibold leading-tight">帮助与反馈</h2>
            <p className="mt-1 text-[12.5px] text-muted-foreground">
              欢迎使用 AgentHub，以下是快速上手指引。
            </p>
          </div>
        </header>

        <div className="space-y-4 p-4 text-[13px] text-foreground/90">
          {/* 核心流程 */}
          <section>
            <div className="mb-2 font-medium">核心流程</div>
            <ol className="space-y-2 text-muted-foreground">
              <li>
                <span className="font-medium text-foreground">1. 创建 AI 队友</span>
                <br />
                在「AI 队友」页面点击 + 号，选择模板或自定义角色，Agent 会接入本机 CLI（Claude Code / Codex / Pi / OpenCode）实时执行任务。
              </li>
              <li>
                <span className="font-medium text-foreground">2. 发起对话</span>
                <br />
                点击 Agent 卡片上的「开始聊天」，可选闲聊模式或指定一个本地项目目录作为工作区——Agent 能直接读写你的代码文件。
              </li>
              <li>
                <span className="font-medium text-foreground">3. 群组协作</span>
                <br />
                在「群组」页面创建多 Agent 协作空间，@ 某个 Agent 分配任务，或让协调者自动拆分并派发。
              </li>
              <li>
                <span className="font-medium text-foreground">4. 技能市场</span>
                <br />
                从 SkillHub 安装社区技能，或自己创建本地 Skill——让你的 Agent 拥有专业领域能力。
              </li>
            </ol>
          </section>

          {/* 反馈与 Issue */}
          <section>
            <div className="mb-2 font-medium">反馈与建议</div>
            <p className="text-muted-foreground leading-relaxed">
              遇到 Bug 或有功能建议，欢迎在{' '}
              <a
                href="https://github.com/Hcre/AgentHub/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand underline underline-offset-2 hover:text-brand/80"
              >
                GitHub Issues
              </a>{' '}
              提交，附上截图和复现步骤。我们会尽快跟进。
            </p>
          </section>

          {/* 快捷键速查 */}
          <section>
            <div className="mb-1.5 font-medium">快捷键</div>
            <ul className="space-y-1 text-muted-foreground text-[12.5px]">
              <li>
                <kbd className="inline-block rounded border bg-muted px-1 py-px font-mono text-[11px]">⌘ B</kbd>{' '}
                折叠 / 展开预览侧边栏
              </li>
              <li>
                <kbd className="inline-block rounded border bg-muted px-1 py-px font-mono text-[11px]">ESC</kbd>{' '}
                中断 Agent 正在生成的回复
              </li>
            </ul>
          </section>
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
