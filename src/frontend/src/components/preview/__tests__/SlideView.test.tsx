import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { SlideView } from '../SlideView'
import type { PptxSlide } from '../../../api/fs'

afterEach(cleanup)

const slides: PptxSlide[] = [
  { index: 0, title: 'AgentHub 演示', texts: ['多 Agent 协作平台'], notes: '' },
  { index: 1, title: '架构', texts: ['5 层洋葱', 'CLI/SDK 双轨'], notes: '强调依赖倒置' },
]

describe('SlideView', () => {
  it('默认渲染第 1 页标题 + 正文 + 缩略图导航', () => {
    render(<SlideView slides={slides} />)
    expect(screen.getByTestId('slide-title').textContent).toBe('AgentHub 演示')
    expect(screen.getByText('多 Agent 协作平台')).toBeInTheDocument()
    expect(screen.getByTestId('slide-thumb-0').getAttribute('data-active')).toBe('true')
    expect(screen.getByTestId('slide-thumb-1').getAttribute('data-active')).toBeNull()
  })

  it('点缩略图切到第 2 页：标题/正文/备注更新', () => {
    render(<SlideView slides={slides} />)
    fireEvent.click(screen.getByTestId('slide-thumb-1'))
    expect(screen.getByTestId('slide-title').textContent).toBe('架构')
    expect(screen.getByText('CLI/SDK 双轨')).toBeInTheDocument()
    expect(screen.getByText(/强调依赖倒置/)).toBeInTheDocument()
    expect(screen.getByTestId('slide-thumb-1').getAttribute('data-active')).toBe('true')
  })

  it('空演示文稿（0 页）显示空态', () => {
    render(<SlideView slides={[]} />)
    expect(screen.getByText(/空演示文稿/)).toBeInTheDocument()
  })
})
