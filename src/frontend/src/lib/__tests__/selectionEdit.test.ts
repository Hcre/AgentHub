import { describe, it, expect } from 'vitest'
import { computeLineRange, relativePath, buildEditPrompt } from '../selectionEdit'

const content = 'line1\nline2\nline3\nline4\n'

describe('computeLineRange', () => {
  it('单行选区 → start===end', () => {
    expect(computeLineRange(content, 'line2')).toEqual({ startLine: 2, endLine: 2 })
  })
  it('多行选区 → 起止行', () => {
    expect(computeLineRange(content, 'line2\nline3')).toEqual({ startLine: 2, endLine: 3 })
  })
  it('首行选区 → 第 1 行', () => {
    expect(computeLineRange(content, 'line1')).toEqual({ startLine: 1, endLine: 1 })
  })
  it('找不到 → null', () => {
    expect(computeLineRange(content, 'nope')).toBeNull()
  })
  it('空选区 → null', () => {
    expect(computeLineRange(content, '')).toBeNull()
  })
})

describe('relativePath', () => {
  it('在 workdir 下 → 相对路径（POSIX）', () => {
    expect(relativePath('C:\\proj\\src\\a.ts', 'C:\\proj')).toBe('src/a.ts')
  })
  it('大小写不敏感（Windows 盘符）', () => {
    expect(relativePath('c:\\Proj\\x.ts', 'C:\\proj')).toBe('x.ts')
  })
  it('无 workdir → 原样', () => {
    expect(relativePath('/a/b.ts')).toBe('/a/b.ts')
  })
  it('不在 workdir 下 → 原样', () => {
    expect(relativePath('/other/b.ts', '/a')).toBe('/other/b.ts')
  })
})

describe('buildEditPrompt', () => {
  it('组装出含 相对路径/行范围/原文/需求 的 prompt', () => {
    const p = buildEditPrompt({
      relPath: 'src/a.ts',
      startLine: 2,
      endLine: 3,
      selectedText: 'foo\nbar',
      request: '改成 map',
    })
    expect(p).toContain('`src/a.ts`')
    expect(p).toContain('第 2–3 行')
    expect(p).toContain('foo\nbar')
    expect(p).toContain('改成 map')
  })
  it('单行用"第 N 行"措辞', () => {
    const p = buildEditPrompt({ relPath: 'a', startLine: 5, endLine: 5, selectedText: 'x', request: 'y' })
    expect(p).toContain('第 5 行')
    expect(p).not.toContain('–')
  })
})
