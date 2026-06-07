import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { AppShell } from '../AppShell'

// 直接 mock useMediaQuery 控制 isMobile，避免 matchMedia 在 jsdom 中的边缘行为
let mockIsMobile = false
vi.mock('../../../hooks/useMediaQuery', () => ({
  useMediaQuery: () => mockIsMobile,
}))

// 简化 AppShell 子依赖
vi.mock('../CenterPanel', () => ({
  CenterPanel: () => <div data-testid="center-panel-stub">center</div>,
}))
vi.mock('../LeftPanel', () => ({
  LeftPanel: () => <div data-testid="left-panel-stub">left</div>,
}))
vi.mock('../NavRail', () => ({
  NavRail: () => <div data-testid="nav-rail-stub">rail</div>,
}))
vi.mock('../RightPanel', () => ({
  RightPanel: () => <div data-testid="right-panel-stub">right</div>,
}))
vi.mock('../../agent/AgentDetailDrawer', () => ({
  AgentDetailDrawer: () => null,
}))
vi.mock('../../tweaks/TweaksPanel', () => ({
  TweaksPanel: () => null,
}))

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  mockIsMobile = false
})

describe('AppShell responsive (mobile H5)', () => {
  beforeEach(() => {
    mockIsMobile = false
  })

  it('renders mobile shell when viewport < 768px (hamburger + center full width)', () => {
    mockIsMobile = true
    render(<AppShell />)
    expect(screen.getByTestId('app-shell-mobile')).toBeInTheDocument()
    expect(screen.getByTestId('mobile-hamburger')).toBeInTheDocument()
    expect(screen.queryByTestId('app-shell-desktop')).not.toBeInTheDocument()
    expect(screen.queryByTestId('mobile-left-drawer')).not.toBeInTheDocument()
    expect(screen.queryByTestId('mobile-right-drawer')).not.toBeInTheDocument()
  })

  it('renders desktop shell (4-column) when viewport >= 768px (no hamburger)', () => {
    mockIsMobile = false
    render(<AppShell />)
    expect(screen.getByTestId('app-shell-desktop')).toBeInTheDocument()
    expect(screen.queryByTestId('app-shell-mobile')).not.toBeInTheDocument()
    expect(screen.queryByTestId('mobile-hamburger')).not.toBeInTheDocument()
  })

  it('mobile: clicking hamburger opens the left drawer (NavRail + LeftPanel inside)', () => {
    mockIsMobile = true
    render(<AppShell />)
    expect(screen.queryByTestId('mobile-left-drawer')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('mobile-hamburger'))
    const drawer = screen.getByTestId('mobile-left-drawer')
    expect(drawer).toBeInTheDocument()
    expect(drawer.querySelector('[data-testid="nav-rail-stub"]')).toBeInTheDocument()
    expect(drawer.querySelector('[data-testid="left-panel-stub"]')).toBeInTheDocument()
  })

  it('mobile: clicking the scrim closes the left drawer', () => {
    mockIsMobile = true
    render(<AppShell />)
    fireEvent.click(screen.getByTestId('mobile-hamburger'))
    expect(screen.getByTestId('mobile-left-drawer')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('mobile-left-drawer-scrim'))
    expect(screen.queryByTestId('mobile-left-drawer')).not.toBeInTheDocument()
  })

  it('mobile: pressing Escape closes the left drawer', () => {
    mockIsMobile = true
    render(<AppShell />)
    fireEvent.click(screen.getByTestId('mobile-hamburger'))
    expect(screen.getByTestId('mobile-left-drawer')).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByTestId('mobile-left-drawer')).not.toBeInTheDocument()
  })

  it('mobile: section=chat shows the right-toggle button', () => {
    mockIsMobile = true
    render(<AppShell />)
    expect(screen.getByTestId('mobile-right-toggle')).toBeInTheDocument()
  })
})
