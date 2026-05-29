# 工作日志：Agent 消息 Markdown 渲染

- **谁**: 黎
- **日期**: 2026-05-25
- **分支**: `feature/frontend/markdown-render`

## 目标

Agent 回复支持 Markdown 渲染（代码块高亮、粗体、列表、链接），用户消息保持纯文本。

## 产出

- [x] 引入 react-markdown + remark-gfm + rehype-highlight
- [x] MessageBubble.tsx 中 agent 消息用 ReactMarkdown 渲染
- [x] 代码块使用 github-dark 主题高亮
- [x] 内联代码、链接、表格等 Markdown 语法均支持

## 给下一位的交接

> `MessageBubble.tsx` 中 `isAgent` 分支使用 `<ReactMarkdown>` 组件，用户消息保持纯文本。高亮主题在 `index.css` 第一行 import。
