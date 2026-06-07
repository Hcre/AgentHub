# 2026-06-08 CLI Runtime 全线打通 + Agent 数据模型 + 创建流程重构

## 完成事项

### CLI Runtime 4/4 全部 E2E 通过
- `claude_code`: ✅ 走 DeepSeek Anthropic 兼容端点，读取 `~/.claude/settings.json` 认证
- `pi_agent`: ✅ 直连 DeepSeek，原生 multi-provider 支持
- `opencode`: ✅ 修复 stderr 管道阻塞 + `step_finish` DONE 事件缺失
- `codex`: ✅ 新建 `codex_runtime.py`，`codex exec --json -` 子进程调用

### 关键 bug 修复
- `factory.py`: `provider != "anthropic"` 拦截误伤 Claude Code CLI 路径（改回仅检查 CLI 安装状态）
- `factory.py`: 新增 `_resolve_api_key()` 三层降级（Agent 存储→环境变量→`~/.claude/settings.json`）
- `opencode_runtime.py`: `stderr=DEVNULL` 避免管道满死锁 + `step_finish` 生成 DONE 事件
- `chat.py`: `reply_to_id` vs `reply_to` 字段名不匹配
- `chat_service.py`: `SKILLS_DIR` 硬编码 `/skills` 改为动态读取 `settings.skills_dir_path`
- `vite.config.ts`: 代理目标从 Docker 容器名 `backend:8000` 改为本地 `localhost:8000`
- `CreateAgentModal.tsx`: 修复 `setTplDetailLoadingId`/`setCustomName` 未定义导致弹窗无法关闭

### Agent 数据模型
- 全链路新增 `template_name` 字段（domain entity → DB → schema → API → frontend）
- 激活 `created_from_template_id` 列（之前是 dead column）
- 名字唯一性：`exists_by_name` 应用层检查（同模板不同名允许，同名不可）
- Alembic migration 0018: `agents.template_name VARCHAR(128)`

### 创建流程重构
- Step 1: 名字输入置顶 + 分隔线 + "选择身份模板"
- 8 个真实身份模板：从 `wshobson-agents` 精选（产品经理/后端工程师/代码评审/测试工程师/技术负责人/运维工程师/数据工程师/安全审计），完整 system prompt 注入
- 自定义模式：新增"身份（模板名）"输入框
- Agent 卡片：大字名字 + 小字模板名

### 删除确认弹窗 + 图标居中
- `AgentsListPage`: 单个删除 + 批量删除 → Dialog 弹窗
- `GroupsListPage`: 批量删除 → Dialog 弹窗
- 空态图标：`grid place-items-center` → `flex items-center justify-center mx-auto`

### 其他
- `docker-compose.yml`: backend/celery 注入 `SKILLS_DIR=/skills`
- `WorkspaceBrowser.tsx`: fetch 加 `API_BASE` 前缀
- `src/frontend/.env`: 新建，本地开发用 `VITE_API_BASE_URL=http://localhost:8000`

## 给下一位的交接

- 后端改动在 `feature/template/template-system-v4` 分支
- 前端改动未提交（4 个文件 modified），本次 push 一并提交
- 4 个 CLI runtime 全部 E2E 验证通过（测试脚本 `test_4cli.py` 已删除）
- `template_name` 字段需运行 `alembic upgrade head` 应用 migration 0018
- Codex CLI 需要本机有 `OPENAI_API_KEY` 或 DeepSeek Key 通过 Anthropic 兼容端点

## 耗时
~8h（多轮迭代调试，主要在 CLI runtime 集成和模板系统重构）
