# 工作日志：移除 CLI 路径 L1 Redis 记忆

- **谁**: 黎
- **日期**: 2026-05-25
- **分支**: `feature/domain2/remove-l1-from-cli`

## 目标

CLI 通过 `--resume` 自己管理对话历史，AgentHub 的 L1 Redis 滑动窗口对 CLI 模式多余。移除。

## 产出

- [x] ChatService 移除 `l1_memory` 参数
- [x] ws/chat.py 移除 RedisL1Store 构造
- [x] deps.py 删除 `get_l1_memory()` 函数
- [x] config.py 移除 `l1_window_size`
- [x] protocol.py `l1_working` 标记已废弃
- [x] adapter-cli-flow.md 更新至 v1.5

## 影响范围

CLI 路径无影响（本来就不依赖 L1）。API 适配器 L1 代码保留未删。

## 决策记录

> 单聊 Agent 不需要 AgentHub 层记忆系统，CLI 自带的 `--resume` 和本地 sqlite 已经完整覆盖对话历史、上下文记忆、文件操作。L2/L3 记忆留给群聊场景。
