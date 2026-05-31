# 2026-05-31 OpenCode 修复 + 文档基础设施

## 做了什么

1. **修复 opencode JSON 解析 bug** — opencode v1.15+ 将内容嵌套在 `data.part` 内，`_parse_line()` 只查顶层 `data.text`，导致所有 Agent 回复丢失（根因分析见 `docs/explore/黎/opencode-json-parsing-fix.md`）

2. **文档基础设施改进** — CLAUDE.md 新增「AI 产出文件写入规则」section，渐进式披露到 `06-documentation.md` §三（Git→人名映射 + 产出→位置决策表 + 写文件前自检）

3. **调研报告** — M4 产物预览与编辑调研（open-design / open-codesign / AIO Hub 的实现方式分析）

## 关键决策

- opencode JSON 解析采用 `part` 优先 + 顶层 fallback 策略，兼容新旧版本
- 文档产出规范通过 CLAUDE.md 渐进式披露，避免上下文膨胀

## 文件变更

| 文件 | 动作 |
|------|------|
| `opencode_runtime.py` | 修复 `_parse_line` 数据提取层级 |
| `CLAUDE.md` | 新增 AI 产出文件写入规则引用 |
| `06-documentation_文档规范.md` | 新增 Git→人名映射 + AI 产出→位置速查 |
| `docs/explore/黎/artifact-preview-research.md` | M4 产物预览调研 |
| `docs/explore/黎/opencode-json-parsing-fix.md` | opencode 集成审查报告 |

## 给下一位的交接

- 后端重启后 opencode 对话应该能正常工作
- 需确认 `gitignore` 中的 `backend/` 规则是否正确（当前会忽略 `src/backend/` 下的 tracked 文件）
- pre-push 的 dead-links hook 有 29 个预存死链（非本次变更引入）
