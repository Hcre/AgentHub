import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { EmptyChatState, PROMPTS_DEFAULT } from '../ChatView'

/**
 * B-4-P2-S1-S01 / docs/specs/04-commands §6.4.7
 * S1 私聊 3 建议卡 click 真接 backend 修复（Day 2 gap #6）。
 *
 * 修复口径：
 *   - ChatView.tsx line 138-140 `onPick={(text) => composerRef.current?.setText(text)}`
 *     → `onPick={(text) => onSend({ text })}`
 *   - 跳过 composer input，直接走 onSend (WS 优先 + send 降级) → 后端 POST /api/messages
 *   - 用户体感「点了没反应」→ 修了
 *
 * 测法：把 EmptyChatState + PROMPTS_DEFAULT 提到 top-level export（per T2 收尾模式），
 *       直接在 jsdom 里渲染，onPick 用 vi.fn() 注入 — 不依赖 useWebSocket / store。
 *       4 个 it 锁定：3 卡渲染 + 3 click onPick 调用的 text 文本与 §6.4.7 对齐。
 *
 * 关键点：
 *   - onPick 接收的 text 参数必须 == PROMPTS_DEFAULT[i].onPick（与 BDD spec Then-1/2/3 一致）
 *   - 锁 PROMPTS_DEFAULT 顺序（title 升序：帮我看看代码 → 改个 bug → 起一个新项目）
 *   - 测「auto-collapse」靠 ChatView 父组件的 list.length > 0 卸载（不在本测试范围，父组件
 *     list 状态机由 store 测试覆盖；本测试锁定 presentational contract）
 */
describe('S1 私聊建议卡（EmptyChatState）— B-4-P2-S1-S01', () => {
  it('空态渲染 3 张建议卡（帮我看看代码 / 改个 bug / 起一个新项目）', () => {
    // PROMPTS_DEFAULT 必须恰好 3 条且与 §6.4.7 BDD 数据一致
    expect(PROMPTS_DEFAULT).toHaveLength(3)
    expect(PROMPTS_DEFAULT.map((p) => p.title)).toEqual([
      '帮我看看代码',
      '改个 bug',
      '起一个新项目',
    ])

    const onPick = vi.fn()
    render(<EmptyChatState agentName="Coda" prompts={PROMPTS_DEFAULT} onPick={onPick} />)

    // 3 卡都在 DOM（data-testid 由 ChatView.tsx 注入：prompt-card-<title>）
    expect(screen.getByTestId('prompt-card-帮我看看代码')).toBeInTheDocument()
    expect(screen.getByTestId('prompt-card-改个 bug')).toBeInTheDocument()
    expect(screen.getByTestId('prompt-card-起一个新项目')).toBeInTheDocument()

    // agentName 出现在标题
    expect(screen.getByText(/和 Coda 开始对话/)).toBeInTheDocument()

    // 渲染阶段 onPick 不会被调用
    expect(onPick).not.toHaveBeenCalled()
  })

  it('click「帮我看看代码」→ onPick 被以 text="帮我看看当前项目的代码结构" 调用 1 次', () => {
    const onPick = vi.fn()
    render(<EmptyChatState agentName="Coda" prompts={PROMPTS_DEFAULT} onPick={onPick} />)

    fireEvent.click(screen.getByTestId('prompt-card-帮我看看代码'))

    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith('帮我看看当前项目的代码结构')
  })

  it('click「改个 bug」→ onPick 被以 text="我遇到一个 bug，需要你帮我定位和修复" 调用 1 次', () => {
    const onPick = vi.fn()
    render(<EmptyChatState agentName="Coda" prompts={PROMPTS_DEFAULT} onPick={onPick} />)

    fireEvent.click(screen.getByTestId('prompt-card-改个 bug'))

    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith('我遇到一个 bug，需要你帮我定位和修复')
  })

  it('click「起一个新项目」→ onPick 被以 text="帮我从零开始一个新项目，先聊聊需求" 调用 1 次', () => {
    const onPick = vi.fn()
    render(<EmptyChatState agentName="Coda" prompts={PROMPTS_DEFAULT} onPick={onPick} />)

    fireEvent.click(screen.getByTestId('prompt-card-起一个新项目'))

    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith('帮我从零开始一个新项目，先聊聊需求')
  })
})
