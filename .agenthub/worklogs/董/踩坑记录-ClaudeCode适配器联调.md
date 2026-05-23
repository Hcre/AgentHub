# ClaudeCode 适配器联调踩坑记录

> 日期：2026-05-23 | 版本：v1.0

---

## 坑 1：agents 表缺少 agent_system 和 base_url 列

**现象：** `POST /api/agents` 返回 `Internal Server Error`

**原因：** Migration `0002_add_agent_system_base_url.py` 未执行。初始 migration `0001_initial.py` 使用 `Base.metadata.create_all()` 创建全表，但表已存在时不会增量添加新列。0002 是手写的增量 migration，需要单独执行或手动 ALTER TABLE。

当前项目的 migration 机制未自动化，`0001` 用 `create_all`（幂等建表），`0002` 无人执行。

**根因：** 没有统一的 migration 执行流程。每次新增字段需要手动跑 SQL。

**解决：**
```sql
ALTER TABLE agents ADD COLUMN agent_system VARCHAR(32) DEFAULT 'mock' NOT NULL;
ALTER TABLE agents ADD COLUMN base_url VARCHAR(512);
```

**后续建议：** 在启动脚本或 CI 中自动执行 `alembic upgrade head`。

---

## 坑 2：Session 创建路由 404

**现象：** `POST http://127.0.0.1:8000/sessions` 返回 `404 Not Found`

**原因：** sessions router 的 prefix 是 `/api`（`APIRouter(prefix="/api")`），完整路径应是 `/api/sessions`。

测试脚本 `manual_test_claude.py` 写错了路径。

**解决：** 修正脚本中的 URL 为 `POST /api/sessions`。

---

## 坑 3：decrypt_secret("") 抛出 Nonce 错误

**现象：** 发送 WS 消息后，后端日志报错：
```
ValueError: Nonce must be between 8 and 128 bytes
  at decrypt_secret → AESGCM(key).decrypt(nonce, ct, None)
```

**原因：** Agent 创建时 `api_key` 未传（CLI 模式用本机 Claude Code 认证，不需要 API key），`api_key_encrypted` 为空字符串 `""`。`build_adapter_for_agent` 对空字符串调 `decrypt_secret("")`，base64 解码空字符串得到长度不足的 bytes，传给 AESGCM.decrypt 时 nonce 长度检查失败。

**根因：** Factory 对 CLI 模式无条件解密 api_key，但 CLI 模式 API key 应为可选。

**解决：** `factory.py` 中增加非空判断：
```python
api_key = decrypt_secret(agent.api_key_encrypted) if agent.api_key_encrypted else ""
```

**设计教训：** API 模式需要 API key 是合理的，但 CLI 模式的认证完全依赖用户本机的 Claude Code 配置（`~/.claude/credentials.json` 或环境变量）。两种模式的认证机制根本不同，Factory 需要区分处理。

---

## 坑 4：测试脚本端口不一致

**现象：** 前端 `.env` 配置 `VITE_API_BASE_URL=http://localhost:8000`，但测试脚本用了 `PORT = 8765`

**原因：** 8765 是为了避免和已有的 8000 端口后端冲突。但实际 8000 端口空闲，且前端已固定配置 8000。

**解决：** 测试脚本统一用 8000。

---

## 总结

| # | 类别 | 根本原因 | 修复方式 |
|---|------|---------|---------|
| 1 | DB Schema | migration 未执行 | 手动 ALTER TABLE |
| 2 | API 路径 | 测试脚本 URL 缺 /api 前缀 | 修正 URL |
| 3 | 空值处理 | CLI 模式 api_key 为空时解密崩溃 | 非空判断 |
| 4 | 配置 | 测试端口与前端不一致 | 统一为 8000 |

**核心教训：** API 模式和 CLI 模式的认证机制不同。API 模式必须有 API key，CLI 模式依赖本机用户认证。这个差异体现在 Agent 实体的 `api_key_encrypted` 可能是空字符串，Factory 层必须容忍。
