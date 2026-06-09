# ADR-0016: E2E 视觉验证工具从 Computer Use 切换到 Playwright MCP

- **状态**: Accepted
- **日期**: 2026-06-07 12:00 (Asia/Shanghai)
- **决策者**: 袁 (xiangbianpangde, owner, per ADR-0008)
- **关联 worklog**: `worklogs/袁/` 6/7-6/8 期间 Playwright E2E 验证产出（多份）

## 背景

AgentHub M5 范围需要 E2E 视觉验证（"功能都没实现"用户疑虑触发）。两条候选工具：

1. **Computer Use (cu)**：Claude 原生能力，纯 GUI 坐标操作
2. **Playwright MCP**：`@playwright/mcp` 服务 + `getByRole/ref/evaluate` DOM 精准

## 候选对比

| 维度 | Computer Use | Playwright MCP |
|------|-------------|---------------|
| 坐标精度 | 截图 + 像素预测，PS 5.1 后中文 IME 编码被破坏 | DOM ref 精准（id/data-testid/role） |
| 中文输入 | PowerShell + Set-Clipboard JSON 注入，CI 端不可控 | 直接 `browser_type` 走 CDP |
| 错误反馈 | 截图延迟，失败原因模糊 | console + network 实时 + DOM 快照 |
| CI 集成 | 不支持（需 GUI） | 支持（headless chromium） |
| 维护成本 | 每次 PS 版本/编码变化需重测 | 跟随 Playwright 版本稳定 |

## 决策

**采用 Playwright MCP，cu 弃用。** 触发条件与适用范围：

- 范围：所有 E2E 视觉验证（前端页面、Modal、按钮响应、消息流、Pin/Diff 视图）
- 不适用：CLI 工具/算法逻辑（仍用 terminal output + pytest）
- 退出条件：若 Playwright MCP 出现 dev-mode-only 行为（如真实上传/WS）回归 cu

## 收效

- 6/7 12:00-13:00 完成 11 章节实测，0 误判（与"功能都没实现"用户疑虑对照）
- 22:00 Phase 2 重测发现 Pin API 401 bug（cu 截图无法定位 network 401）
- 6/8 overnight t1-t4 4/4 track 100% 绿（CI gate 5.4 含 Playwright）

## 反模式沉淀

- 不要再尝试用 cu 验证中文 CJK 文本输入（PowerShell JSON 注入 + IME 切换代价 > 收益）
- 不要假设 cu 截图能反映"按钮 click 不响应"的根因（DOM 0 事件 / network 401 / 状态机未触发需要 ref 级别证据）
