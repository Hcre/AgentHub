import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { TaskCard } from '../TaskCard'
import type { Task } from '../../../types'

afterEach(cleanup)

const todo: Task = { id: 'T-1', title: '实现登录', status: 'todo', priority: 'normal', due: '—' }

describe('TaskCard 派发按钮', () => {
  it('todo 任务显示「派发执行」按钮', () => {
    render(<TaskCard task={todo} onClick={() => {}} onDispatch={() => {}} />)
    expect(screen.getByTestId('task-dispatch-btn')).toBeInTheDocument()
  })

  it('非 todo 任务不显示派发按钮', () => {
    render(<TaskCard task={{ ...todo, status: 'doing' }} onClick={() => {}} onDispatch={() => {}} />)
    expect(screen.queryByTestId('task-dispatch-btn')).not.toBeInTheDocument()
  })

  it('无 onDispatch 时不显示按钮', () => {
    render(<TaskCard task={todo} onClick={() => {}} />)
    expect(screen.queryByTestId('task-dispatch-btn')).not.toBeInTheDocument()
  })

  it('点派发触发 onDispatch 且不冒泡到卡片 onClick', () => {
    const onDispatch = vi.fn()
    const onClick = vi.fn()
    render(<TaskCard task={todo} onClick={onClick} onDispatch={onDispatch} />)
    fireEvent.click(screen.getByTestId('task-dispatch-btn'))
    expect(onDispatch).toHaveBeenCalledTimes(1)
    expect(onClick).not.toHaveBeenCalled() // stopPropagation 生效
  })
})
