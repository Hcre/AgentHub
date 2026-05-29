# 工作日志：Phase 0 验收 + Phase 1 设计落地

- **谁**: 董
- **日期**: 2026-05-29
- **分支**: worktree-group-chat-design
- **关联 Spec**: ADR-01, ADR-02, group-chat-pipeline-proposal v3.1

## 目标

完成群聊身份错乱问题的 Phase 0 验证 + Phase 1 实施方案设计。

## 产出

- [x] Phase 0 措辞修复（4 处，已于工作树实现）：
  - P0-1 `context_builder.py:98` persona 强化模板（含否定式约束）
  - P0-2 `prompt_templates.py:17` GROUP_CHAT_CONTRACT 第 1 条身份确认
  - P0-3 `context_builder.py:215` `_load_members` 排除 coordinator_id
  - P0-4 `prompt_templates.py:55` `format_delta` 发言人前缀说明
- [x] Phase 0.5 V5 验证：`--resume` + `--input-format stream-json` 兼容性 ✅
- [x] Phase 0 量化基线（N=20）：身份互串 0/60、自己@自己 0/60
- [x] Proposal v3.1 修正：fan-out 废弃、8 处问题补入、V5 补充
- [x] ADR-02：Phase 1 长驻 CLI + stream-json 实施计划（Accepted）
- [x] 合并 origin/main → 工作树

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| Phase 1 推迟 | 量化基线身份互串 0/60（<5%），Phase 0 措辞修复已够用 | 暂不改 ClaudeCodeRuntime 架构 |
| ADR-02 仍写入 | Phase 0 修 prompt 不修结构，system_prompt 膨胀问题仍存在；后续需做时不用重新设计 | ADR 归档备查 |
| fan-out 广播废弃 | stream-json 协议不支持只读推送，每条 user message 触发回复 | 群聊改为纯 pull 模式 |
| --resume + stream-json 兼容 | V5 验证通过 | crash recovery 路径明确 |

## 未完成 / 阻塞

- [ ] Spec 文档同步（S1-S4）：architecture 双轨→CLI 主、CLAUDE.md、roadmap 同步
- [ ] 口吻传染独立工单（Q9）
- [ ] EVOLUTION.md 写入今日决策

## 给下一位的交接

> Phase 0 已验收通过。Phase 1 设计文档齐全（ADR-02），`claude_code_runtime.py` 改造按 ADR-02 四步走。
> 验证脚本集中在 `scripts/feasibility/`：V1-V5 全部通过，phase0_baseline.py 可复跑。
> 合并 main 后无冲突，可随时切工作树继续。
