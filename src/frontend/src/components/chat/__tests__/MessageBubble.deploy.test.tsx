import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MessageBubble } from '../MessageBubble'
import type { Agent, ChatMessage, UserInfo, DeployCard } from '../../../types'

afterEach(cleanup)

const agent: Agent = {
  id: 'deploy-bot',
  name: '部署 Bot',
  role: 'Deploy assistant',
  color: 'brand',
  online: true,
}

const user: UserInfo = { handle: 't', name: 't', initial: 'T' }

const baseMsg: ChatMessage = {
  id: 'msg-d1',
  from: 'agent',
  time: '12:00',
  text: '已收到，开始部署',
}

const SESSION_ID = 'sess-deploy-1'

/**
 * P2-2 部署卡 3 路径（与 components/deploy/DeployCard.tsx 的 DeployCardView 对齐）：
 *   1. ready — 显示「已就绪」+ deploy_url + 「打开预览」按钮 + a 链接（data-testid="deploy-url"）
 *   2. building — 显示「构建中」+ 进度条（data-testid="deploy-progress"）+ 没有「打开预览」按钮
 *   3. failed — 显示「部署失败」+ error_code + error_message（data-testid="deploy-error-code"/"-msg"）
 *
 * 顺带覆盖 queued 作为 baseline（4 态机色存在性）。
 *
 * data-attr schema 钉死在测试里（data-status / data-testid）—— 后续 DeployCardView 重构
 * 改了渲染名测试立刻挂。
 */

describe('MessageBubble deploy card (P2-2)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders deploy card in ready state with deploy_url and open button', () => {
    const deploy: DeployCard = {
      id: 'd-001-full-uuid-string',
      status: 'ready',
      target: 'static_site',
      framework: 'vite',
      entry_file: 'index.html',
      deploy_url: 'https://preview.agenthub.dev/run/d-001',
      ttl: 3600,
      updated_at: Date.now(),
    }
    const msg: ChatMessage = { ...baseMsg, deploy }
    render(<MessageBubble msg={msg} agent={agent} user={user} sessionId={SESSION_ID} />)

    const card = screen.getByTestId('deploy-card')
    expect(card).toBeInTheDocument()
    expect(card.getAttribute('data-status')).toBe('ready')

    // 状态文案
    expect(card.textContent).toContain('已就绪')

    // URL 链接 + 打开预览按钮都存在
    const urlLink = screen.getByTestId('deploy-url')
    expect(urlLink).toBeInTheDocument()
    expect(urlLink.getAttribute('href')).toBe('https://preview.agenthub.dev/run/d-001')
    expect(urlLink).toHaveTextContent('https://preview.agenthub.dev/run/d-001')

    const openBtn = screen.getByTestId('deploy-open-btn')
    expect(openBtn).toBeInTheDocument()
    expect(openBtn).toHaveTextContent('打开预览')
    expect(openBtn.getAttribute('title')).toBe('https://preview.agenthub.dev/run/d-001')

    // ready 态不展示 error
    expect(screen.queryByTestId('deploy-error-code')).toBeNull()
    expect(screen.queryByTestId('deploy-error-msg')).toBeNull()
  })

  it('renders building state with progress bar and NO open button', () => {
    const deploy: DeployCard = {
      id: 'd-003',
      status: 'building',
      target: 'static_site',
      framework: 'vite',
      progress: 0.42,
      stage: '正在 npm install…',
      ttl: 3600,
      updated_at: Date.now(),
    }
    const msg: ChatMessage = { ...baseMsg, id: 'msg-d3', deploy }
    render(<MessageBubble msg={msg} agent={agent} user={user} sessionId={SESSION_ID} />)

    const card = screen.getByTestId('deploy-card')
    expect(card.getAttribute('data-status')).toBe('building')
    expect(card.textContent).toContain('构建中')

    // 进度条百分比（42% = "42%"）
    const progress = screen.getByTestId('deploy-progress')
    expect(progress).toBeInTheDocument()
    expect(progress.textContent).toBe('42%')

    // building 态不展示「打开预览」
    expect(screen.queryByTestId('deploy-open-btn')).toBeNull()
    expect(screen.queryByTestId('deploy-url')).toBeNull()
    // 不展示 error
    expect(screen.queryByTestId('deploy-error-code')).toBeNull()
    expect(screen.queryByTestId('deploy-error-msg')).toBeNull()
  })

  it('renders failed state with error_code + error_message and NO open button', () => {
    const deploy: DeployCard = {
      id: 'd-004',
      status: 'failed',
      target: 'static_site',
      framework: 'vite',
      error_code: 'BUILD_OOM',
      error_message: 'Build failed at step "vite build": out of memory',
      ttl: 3600,
      updated_at: Date.now(),
    }
    const msg: ChatMessage = { ...baseMsg, id: 'msg-d4', deploy }
    render(<MessageBubble msg={msg} agent={agent} user={user} sessionId={SESSION_ID} />)

    const card = screen.getByTestId('deploy-card')
    expect(card.getAttribute('data-status')).toBe('failed')
    expect(card.textContent).toContain('部署失败')

    // error_code + error_message 都展示
    const errCode = screen.getByTestId('deploy-error-code')
    expect(errCode).toBeInTheDocument()
    expect(errCode).toHaveTextContent('BUILD_OOM')

    const errMsg = screen.getByTestId('deploy-error-msg')
    expect(errMsg).toBeInTheDocument()
    expect(errMsg.textContent).toContain('out of memory')

    // failed 态不展示「打开预览」
    expect(screen.queryByTestId('deploy-open-btn')).toBeNull()
    expect(screen.queryByTestId('deploy-url')).toBeNull()
  })
})
