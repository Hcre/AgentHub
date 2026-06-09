# 部署功能端到端审查报告

> 2026-06-09，全链路代码审查 + 日志分析。给接手的人看，5 分钟了解当前进度和缺口。

---

## 一、功能概述

AgentHub 的「部署」功能允许用户在聊天中触发部署，将 Agent 生成的代码（HTML/JS/项目文件）部署为可预览的静态站点、容器化应用或源码包下载。

## 二、当前真实状态

**部署引擎 = 带状态机的入参校验器 + 日志模拟器。不执行真实构建，不生成可用链接。**

- 后端基础设施完整（状态机 + 校验 + 持久化 + API + 测试）
- 前端展示层部分实施（DeployPanel 列表页可读可删，DeployCard 聊天卡片仅有类型定义）
- **整个功能缺少触发入口**，无人调用 `POST /api/deployments`
- **构建过程是假的**——不写磁盘、不装依赖、不启进程、不生成可访问的 URL
- **DeployCard 聊天卡片从未被填充**——类型定义了但没有后端代码往消息里写这个字段

STATUS.md 标注为「✅ 完整」，实际是：端点已落 + 前端 UI 已画，但串联不起来。

---

## 三、文件清单

### 后端（8 文件）

| 文件 | 说明 |
|------|------|
| `domain/enums.py:168-187` | `DeploymentTarget` (static_site/container/package) + `DeploymentStatus` (queued/building/ready/failed/deleted) |
| `domain/deploy/deployment.py` | `Deployment` 聚合根 + `DeploymentPlan` 值对象 + 状态机（transition_deployment 全局把关） + 阶段序列 |
| `domain/deploy/errors.py` | 5 个领域错误类型（Validation / Transition / Stage / Build / NotFound） |
| `domain/repositories/deployment_repository.py` | 抽象 Repository 接口（save / get_by_id / list_by_session） |
| `infrastructure/db/models.py:361-389` | `DeploymentModel` SQLAlchemy ORM（deployments 表） |
| `infrastructure/repositories/deployment_repository.py` | `PostgresDeploymentRepository` 实现（_to_domain / _to_model 映射） |
| `application/services/deploy_service.py` | `DeployService`（start / get / list / delete + _advance_synchronous 模拟构建） |
| `api/routers/deploy.py` | REST 路由：POST / GET / DELETE /api/deployments |

### 前端（4 文件）

| 文件 | 说明 |
|------|------|
| `types/index.ts:178-209` | `DeployCard` 接口（聊天消息内嵌卡片，字段 `deploy_url`） |
| `api/deploy.ts` | `deployApi` HTTP client（list / get / start / remove） |
| `components/deploy/DeployCard.tsx` | `DeployCardView` 组件（4 状态色 + 进度条 + 打开预览按钮） |
| `components/preview/DeployPanel.tsx` | `DeployPanel` 预览 tab（部署历史列表，仅 list + delete，无 start） |

### 测试（1 文件）

| 文件 | 覆盖 |
|------|------|
| `tests/test_deploy.py` | 13 条：domain 校验 (5) + 服务路径 (4) + 状态机 (2) + CRUD (2) |

---

## 四、`POST /api/deployments` 实际做了什么

以一次 `static_site` 请求为例：

```
输入: { target: "static_site", entry_file: "index.html", files: {"index.html": "...", "app.js": "..."} }

1. DeploymentPlan.validate()
   - 检查 files 不为空
   - 检查 static_site 必须有 entry_file
   - 检查 entry_file 在 files 里

2. 创建 Deployment 实体，写入 PostgreSQL（status=queued）

3. _advance_synchronous() 同步模拟构建：
   queued → building (progress=0.1)
     uploading 阶段: build_logs.append("[uploading] xxx")
     building 阶段: 正则扫描 index.html → 提取 src="x.js" → 检查 x.js 在 files 里
   → ready (progress=1.0)
     preview_url = "https://agenthub-deploy.com/d{id_hex}-static_site"

4. 返回 JSON 响应
```

**关键事实：**
- 不进任何构建工具（无 npm / pip / cmake / docker）
- 不写磁盘（files 内容只在内存里，不落 `_assets/` 或 `/tmp`）
- preview_url 的域名 `agenthub-deploy.com` 不存在，只是一个拼字符串
- `container` 和 `package` target 甚至连引用检查都没有，直接走到 ready
- `framework` 字段完全不被解析，传什么都一样

---

## 五、三个断裂点

### 断裂 1：无人触发部署（Critical）

`deployApi.start()` 在 `api/deploy.ts:59` 已定义，但在整个前端零调用。

- `DeployPanel.tsx` 只调了 `deployApi.list()` 和 `deployApi.remove()`
- 没有任何按钮、右键菜单、聊天指令触发 `deployApi.start()`
- ChatService / Coordinator / Agent 都没有调 `POST /api/deployments`
- SPEC §6.4.4 写的「U1 选中 M3 代码 → 点『部署』」这个 UI 交互不存在

### 断裂 2：DeployCard 聊天卡片是死的（Critical）

`types/index.ts:143` 定义了 `msg.deploy?: DeployCard`。`MessageBubble.tsx:383` 会检查并渲染 `DeployCardView`。

但**没有任何后端代码向消息填充此字段**：
- 没有 WebSocket 事件 `deployment:progress`（SPEC §6.4.4 Then-1-c 定义了但未实现）
- 没有 domain event 发布
- `StreamEvent.artifact` 字段（protocol.py:75）注释写了 `Diff/Preview/Deploy URL`，但从未被赋值 deploy 相关内容
- DeployPanel 自己写了 3 秒轮询（`setInterval`）来兜底，但只用于列表页，不用于聊天卡片

**DeployCard 和 Deployment 是两套完全独立的数据模型，从未连通过。**

### 断裂 3：构建是假的（By Design）

`_advance_synchronous()` 只是推进状态机 + append 日志行 + 拼假 URL。P1 骨架，真实构建标注「留 P2+」。

---

## 六、数据模型断裂

前端有三套 deploy 数据模型，互不连通：

| 模型 | 定义位置 | 预览 URL 字段 | 如何填充 |
|------|---------|-------------|---------|
| `Deployment` (后端) | `deployment.py` | `preview_url` | `_build_preview_url()` 生成假 URL |
| `Deployment` (前端 API) | `api/deploy.ts` | `preview_url` | HTTP GET `/api/deployments` |
| `DeployCard` (聊天卡片) | `types/index.ts` | `deploy_url` | **从未填充** |

注意 `preview_url` vs `deploy_url` 的命名不一致——即使有人写桥接代码，字段名也会对不上。

---

## 七、离可用还差什么

### 要做到「能跑通」

1. **触发入口**：前端加「部署」按钮（选中代码块 → 点部署），或 ChatService 识别「部署」指令 → 调 `DeployService.start()`
2. **WebSocket 推送**：`DeployService` 状态变更时 publish event → WS 推送给前端更新 DeployCard
3. **DeployCard 填充**：把 `Deployment` 数据映射到 `DeployCard`，通过 WS 或 message metadata 写入消息

### 要做到「真的能部署」

4. **文件落盘**：把 `files` 内容写入 `_assets/deployments/{id}/` 目录
5. **依赖安装 + 构建**：`static_site` 不需要构建（本身就是 HTML/CSS/JS）；`container` 需要 `docker build`；`package` 需要打包 zip
6. **服务启动 + 端口映射**：静态文件挂 nginx / 容器 `docker run -p`
7. **真实 URL 回写**：生成的预览地址要实际可访问（如 `http://localhost:port/d{id}`）
8. **TTL 回收**：到期的 deployment 自动清理（stop 容器 / 删文件）

---

## 八、SPEC vs 现实对照

| SPEC §6.4.4 B-5-P2-DP01 | 实现状态 |
|--------------------------|---------|
| POST /api/deployments | ✅ 端点存在，无人调 |
| GET /api/deployments/{id} | ✅ |
| DELETE /api/deployments/{id} | ✅ |
| 返回 `status="building"` | ✅（但毫秒级走到 ready，看不见 building 态） |
| 流新增消息 M4 content_type="deploy_card" | ❌ 不存在 |
| WS 推送 `deployment:progress` | ❌ 不存在 |
| deploy_card 渲染进度条 + 预览 URL + 打开按钮 | ⚠️ 组件写好但无数据 |
| 构建失败 → build_logs 报错 + status="failed" | ✅ static_site 引用检查失败 → failed |
| 「选 M3 代码 → 点部署」UI | ❌ 不存在 |

---

## 九、STATUS.md 的问题

STATUS.md 第 74 行标注部署功能为「✅ 完整」，第 55 行标注「部署卡 ✅」。

实际上：
- 端点写了 → 对
- 前端 UI 画了 → 对
- 功能能用 → **不对**

STATUS.md 第 75 行补充了「真实部署流水线未跑 E2E」和第 97 行「真实数据待 DB seed」，这在某种程度上承认了 gap，但「完整」的标注会误导接手的人。

---

## 十、建议

如果这是 P1 骨架（有意为之），roadmap 上应该有明确的 P2 排期承接真实构建。当前阶段的价值在于：API 契约、数据模型、状态机、前端 UI 骨架都已就绪，接入真实构建时只需替换 `_advance_synchronous()` 的实现（开放-封闭原则）。

如果团队认为这个功能「已经做完了」，那就是被 AI 糊弄了。
