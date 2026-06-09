/**
 * Unified-diff → {oldValue, newValue} 解析器。
 *
 * 目的：react-diff-viewer-continued 接受的是「变更前/变更后」两份纯文本字符串，
 * 而 Agent 在 ```diff ... ``` 围栏里给我们的是 git 风格的 unified diff。
 * 这里把 unified diff 拆成 old/new，再交给库内部 Myers 算法重新对齐 + 染色。
 *
 * 拆出去的原因：跟 webPreviewUrl.ts 一样 —— .tsx 文件只导出 React 组件
 * （react-refresh/only-export-components），把纯函数解析逻辑放在 .ts 里。
 *
 * 解析规则（精简版，覆盖 99% 实际场景）：
 *   - 跳过 header：`diff --git`、`index ...`、`--- a/...`、`+++ b/...`、`@@ ... @@`
 *   - 跳过 `\ No newline at end of file`（git 提示，库内不识别）
 *   - `+xxx` → 仅加到 new（首字符是 `+` 但不是 `+++`）
 *   - `-xxx` → 仅加到 old（首字符是 `-` 但不是 `---`）
 *   - ` xxx` → 同时加到 old + new（context 行）
 *   - 末尾空行：trim 掉，避免多出一行 padding
 *
 * 设计取舍：解析后再让库重新 diff，比「按 unified diff 一行行手画」更简单、
 * 正确（自动 word-diff / 折叠 / 行号都对齐），代价是 O(n*m) 一次额外 diff —— 对聊天
 * 消息里出现的几十行 diff 完全可以忽略。
 */
export interface ParsedDiff {
  oldValue: string
  newValue: string
  /** 是否识别出任何 add/remove 改动（否则视为空 diff / 纯 context） */
  hasChanges: boolean
}

/** 多文件 diff：每个文件一条 */
export interface FileDiff {
  /** 文件名（从 +++ b/path 提取） */
  filename: string
  oldValue: string
  newValue: string
  hasChanges: boolean
}

const HUNK_HEADER = /^@@/
const FILE_HEADER_OLD = /^--- /
const FILE_HEADER_NEW = /^\+\+\+ /
const NO_NEWLINE_MARKER = /^\\ No newline at end of file$/
const DIFF_GIT_HEADER = /^diff --git /

/** 从 +++ b/path 行提取文件名 */
function extractFilename(line: string): string {
  const m = line.match(/^\+\+\+ b\/(.+)$/)
  return m ? m[1] : ''
}

export function parseUnifiedDiff(diff: string): ParsedDiff {
  const oldLines: string[] = []
  const newLines: string[] = []
  let hasChanges = false

  if (!diff) return { oldValue: '', newValue: '', hasChanges: false }

  const lines = diff.split('\n')
  for (const raw of lines) {
    if (HUNK_HEADER.test(raw)) continue
    if (FILE_HEADER_OLD.test(raw)) continue
    if (FILE_HEADER_NEW.test(raw)) continue
    if (NO_NEWLINE_MARKER.test(raw)) continue

    if (raw.startsWith('+')) {
      newLines.push(raw.slice(1))
      hasChanges = true
    } else if (raw.startsWith('-')) {
      oldLines.push(raw.slice(1))
      hasChanges = true
    } else if (raw.startsWith(' ')) {
      // context 行：old + new 都要保留（保留缩进/语法）
      const ctx = raw.slice(1)
      oldLines.push(ctx)
      newLines.push(ctx)
    }
    // 其他（首字符不是 +- 空格的，比如裸内容或空行）默认忽略 —— 避免误判
  }

  // 去尾空行，但保留中间空行作为代码语义的一部分
  const trimTrailing = (arr: string[]): string[] => {
    let end = arr.length
    while (end > 0 && arr[end - 1] === '') end--
    return arr.slice(0, end)
  }

  return {
    oldValue: trimTrailing(oldLines).join('\n'),
    newValue: trimTrailing(newLines).join('\n'),
    hasChanges,
  }
}

/**
 * 把多文件 unified diff 按 diff --git 切分，每文件独立解析。
 * 无 diff --git 头时回退到单文件解析（兼容 ```diff 围栏）。
 */
export function parseMultiFileDiff(diff: string): FileDiff[] {
  if (!diff) return []

  // 按 diff --git 切分
  const chunks: { filename: string; body: string }[] = []
  const lines = diff.split('\n')
  let currentFilename = ''
  let currentLines: string[] = []
  let started = false

  for (const raw of lines) {
    if (DIFF_GIT_HEADER.test(raw)) {
      // 保存上一个 chunk
      if (started && currentLines.length > 0) {
        chunks.push({ filename: currentFilename, body: currentLines.join('\n') })
      }
      started = true
      currentFilename = ''
      currentLines = [raw]
    } else if (started) {
      currentLines.push(raw)
      if (FILE_HEADER_NEW.test(raw) && !currentFilename) {
        currentFilename = extractFilename(raw)
      }
    }
  }
  // 最后一个 chunk
  if (started && currentLines.length > 0) {
    chunks.push({ filename: currentFilename, body: currentLines.join('\n') })
  }

  // 无 diff --git 头 → 单文件回退
  if (chunks.length === 0) {
    const parsed = parseUnifiedDiff(diff)
    return [{ filename: '', oldValue: parsed.oldValue, newValue: parsed.newValue, hasChanges: parsed.hasChanges }]
  }

  return chunks.map((c) => {
    const parsed = parseUnifiedDiff(c.body)
    return { filename: c.filename, ...parsed }
  })
}

/**
 * 从 markdown 文本里抠出 ```diff ... ``` 围栏，返回 {diffBody, before, after}。
 * - diffBody: 围栏内的纯 diff（不含 ```diff 标记和围栏关闭符）
 * - before/after: 围栏前/后剩余的 markdown 文本
 *
 * 只识别 ```diff（含 `diff` 语言提示），其他 ```ts/```js 围栏原样保留给 ReactMarkdown。
 * 多个 ```diff 围栏会被合并到一个字符串里（用换行符拼接），逐个渲染。
 */
export function extractDiffFences(text: string): {
  diffBody: string
  before: string
  after: string
  hasDiffFence: boolean
} {
  // 匹配 ```diff\n ... \n``` （非贪婪 + dotAll）
  const fenceRe = /```diff\s*\n([\s\S]*?)```/g
  const matches = Array.from(text.matchAll(fenceRe))
  if (matches.length === 0) {
    return { diffBody: '', before: text, after: '', hasDiffFence: false }
  }

  const first = matches[0]!
  const last = matches[matches.length - 1]!
  const before = text.slice(0, first.index ?? 0)
  const after = text.slice((last.index ?? 0) + last[0].length)
  const diffBody = matches.map((m) => m[1] ?? '').join('\n')

  return { diffBody, before, after, hasDiffFence: true }
}
