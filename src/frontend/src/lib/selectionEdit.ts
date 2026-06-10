/** 对话式局部修改：从选区文本算行号 + 组装发给 Agent 的结构化 prompt。 */

/** 在 content 里定位 selectedText 的起止行（1-based，含端点）。找不到/不唯一仍尽力返回首个匹配。 */
export function computeLineRange(
  content: string,
  selectedText: string,
): { startLine: number; endLine: number } | null {
  if (!selectedText) return null
  const idx = content.indexOf(selectedText)
  if (idx < 0) return null
  const before = content.slice(0, idx)
  const startLine = before.split('\n').length // 1-based
  const endLine = startLine + selectedText.split('\n').length - 1
  return { startLine, endLine }
}

/** 计算文件相对 workdir 的路径（POSIX 分隔符）；无 workdir 或不在其下则返回原 path。 */
export function relativePath(path: string, workdir?: string): string {
  if (!workdir) return path
  const norm = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '')
  const np = norm(path)
  const nw = norm(workdir)
  if (np.toLowerCase().startsWith(nw.toLowerCase() + '/')) {
    return np.slice(nw.length + 1)
  }
  return path
}

/** 组装"仅改选中行"的结构化 prompt——经现有会话 WS 通道发给当前 Agent。 */
export function buildEditPrompt(args: {
  relPath: string
  startLine: number
  endLine: number
  selectedText: string
  request: string
}): string {
  const { relPath, startLine, endLine, selectedText, request } = args
  const range = startLine === endLine ? `第 ${startLine} 行` : `第 ${startLine}–${endLine} 行`
  return (
    `请仅修改文件 \`${relPath}\` 的${range}，不要改动其他部分。\n\n` +
    '选中的原文：\n```\n' +
    selectedText +
    '\n```\n\n' +
    `修改需求：${request}`
  )
}
