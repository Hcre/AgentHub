import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { DocumentRenderer } from '../DocumentRenderer'

afterEach(cleanup)

describe('DocumentRenderer — markdown path (P1-2)', () => {
  it('renders markdown text with react-markdown (headings, code, lists)', () => {
    const md = '# 标题\n\n- 项目 1\n- 项目 2\n\n```ts\nconst x = 1\n```\n'
    render(<DocumentRenderer kind="markdown" content={md} />)
    // 标题存在
    expect(screen.getByRole('heading', { name: '标题' })).toBeInTheDocument()
    // 列表项存在
    expect(screen.getByText('项目 1')).toBeInTheDocument()
    expect(screen.getByText('项目 2')).toBeInTheDocument()
    // code 块存在（textContent 里能找到）
    const root = screen.getByTestId('doc-renderer')
    expect(root.textContent).toContain('const x = 1')
  })

  it('uses a top-corner header with the file name + markdown label', () => {
    render(
      <DocumentRenderer
        kind="markdown"
        content="hello"
        fileName="README.md"
      />,
    )
    expect(screen.getByTestId('doc-header')).toBeInTheDocument()
    expect(screen.getByTestId('doc-header').textContent).toContain('README.md')
    expect(screen.getByTestId('doc-header').textContent).toContain('markdown')
  })
})

describe('DocumentRenderer — pdf path (P1-2)', () => {
  it('renders an iframe with the PDF URL when kind=pdf and url is provided', () => {
    render(
      <DocumentRenderer
        kind="pdf"
        url="/api/attachments/abc/file.pdf"
        fileName="paper.pdf"
      />,
    )
    const iframe = screen.getByTitle('paper.pdf') as HTMLIFrameElement
    expect(iframe).toBeInTheDocument()
    expect(iframe.getAttribute('src')).toBe('/api/attachments/abc/file.pdf')
  })

  it('pdf header shows the file name + pdf label', () => {
    render(
      <DocumentRenderer kind="pdf" url="https://example.com/x.pdf" fileName="x.pdf" />,
    )
    const header = screen.getByTestId('doc-header')
    expect(header.textContent).toContain('x.pdf')
    expect(header.textContent).toContain('pdf')
  })
})

describe('DocumentRenderer — richtext path (P1-2)', () => {
  it('renders rich text by treating content as markdown (subset: bold + links)', () => {
    // 简化富文本：粗体 + 链接 — 复用 markdown 引擎（前端 demo 范围）
    const rich = '这是 **粗体** 部分 [链接](https://example.com)'
    render(<DocumentRenderer kind="richtext" content={rich} />)
    const root = screen.getByTestId('doc-renderer')
    expect(root.textContent).toContain('粗体')
    const link = screen.getByRole('link', { name: '链接' })
    expect(link.getAttribute('href')).toBe('https://example.com')
  })

  it('richtext header shows richtext label', () => {
    render(<DocumentRenderer kind="richtext" content="x" fileName="note" />)
    const header = screen.getByTestId('doc-header')
    expect(header.textContent).toContain('note')
    expect(header.textContent).toContain('richtext')
  })
})
