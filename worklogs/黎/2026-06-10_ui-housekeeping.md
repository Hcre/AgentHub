# UI 日常维护 — 2026-06-10

## 做了

### Token 消耗真数据
- 修复 `extract_completion_tokens` 解析 dict `token_usage`（之前只接受 int，所有 CLI runtime 上报被丢弃）
- Claude Code runtime DONE 事件补 `usage` 字段
- chat_service 累加所有事件 metadata（不再仅信任 last_event）
- usage_repository JOIN agents 表返回 `agent_name`
- TokenDashboard / TokenMonitorPanel 移除全部 mock 数据

### Diff 面板
- 从左右双栏改为上下统一视图 (`splitView={false}`)
- 多文件按 `diff --git` 头切分，每文件独立滚动盒子
- 子进程 GBK 解码崩溃修复：5 处 `subprocess.run` 加 `encoding="utf-8", errors="replace"`

### 导航 & 快捷键
- NavRail: Skill ↔ 收件箱图标位置对调
- AppShell: Ctrl+B / Cmd+B 折叠/展开预览侧边栏 (capture phase 拦截浏览器)
- HelpModal: 占位内容 → 真实产品流程 + GitHub Issues 链接

### 搜索框
- LeftPanel 搜索框去掉 viewport 依赖的 `clamp()` → 固定 `h-8`
- `min-w-0 flex-1` 随侧栏宽度自适应缩放

### 新建文件夹白屏修复
- **根因**: 后端 `POST /api/fs/mkdir` 声明 `parent: str, name: str` → FastAPI 读 query params，前端发 JSON body → 422 返回 `detail: [{loc, msg, type}, ...]` 数组对象 → 前端 `setCreateErr(data.detail)` 把对象数组塞进 React children → React 抛出 "Objects are not valid as a React child" → 白屏
- **后端修复**: `FsMkdirRequest` Pydantic 模型（对齐已有 `FsReadRequest` 模式），body 解析
- **前端修复**: 错误提取安全化 — string / array(422) / unknown 三档，始终产出 string
- tsc + Python 语法检查通过

## 给下一位的交接
- 分支 `feature/ui/token-diff-cleanup` 已提 PR #20，未合并已删
- 当前分支 `feature/misc/daily-housekeeping` 包含 UI 维护 + 新建文件夹白屏修复
- 后端需重启（`uvicorn` 不带 `--reload`）使 `FsMkdirRequest` 生效
