# 一键部署引擎设计方案

> 日期：2026-06-09 | 状态：设计阶段

## 一、问题定义

当前 `deploy_service.py` 是 P1 骨架——构建过程纯模拟，没有真实的 Docker 构建/运行/编排。需要设计一套完整的部署引擎，支持：

1. 自动探测项目栈（Python/Node/Go/多服务）
2. 按探测结果动态生成构建流程
3. 真实 Docker 构建 + docker-compose 编排
4. 返回真实 preview_url

## 二、核心洞察

**「动态」不是每次部署做判断，而是初始化时探测一次，之后按 config 重复执行。**

```
┌─ 项目初始化（一次）──────────────────┐    ┌─ 每次部署（纯程序）──────────┐
│                                      │    │                              │
│  1. 扫描源码目录                       │    │  1. 读 deploy_config          │
│  2. 探测语言/框架/依赖                 │    │  2. 按 config 执行 pipeline   │
│  3. 生成 deploy_config                │    │     package → build → deploy  │
│  4. 持久化到 DB                        │    │  3. 健康检查 + 分配 URL       │
│                                      │    │                              │
└──────────────────────────────────────┘    └──────────────────────────────┘
```

参考：Vercel/Railway/Render 的部署 UI 零 AI 参与，全部内容来自数据库字段 + 模板填充 + 系统命令输出。

## 三、总体架构

```
StackDetector ──→ DeployConfig ──→ Pipeline Engine ──→ Docker ──→ preview_url
（初始化一次）     （持久化DB）     （每次部署执行）     （真实容器）   （真实域名）
```

## 四、模块一：StackDetector（Agent 探测）

### 核心决策：不用代码探测，用 Agent

**手动维护 SIGNATURES 表 → Agent 一次性推断。**

理由：
- 全量支持需要 ~25 个签名文件 × ~5 个框架变体 = ~50 个 detector 函数，~1500 行代码，且永远有盲区
- 新框架/语言出现需要持续维护，成本线性增长
- 最终仍然要 AI 兜底处理非标准项目——等于维护两套系统
- Agent 一次性调用覆盖所有语言、所有框架、非标准项目，维护成本为零（模型升级自然获得新框架知识）
- 初始化阶段 2-5 秒延迟完全可接受（项目创建时一次调用，不是每次部署）

### 输入/输出

- 输入：workspace 目录路径
- 输出：`DeployConfig`（持久化到 deployment 表的 JSONB 列）

### Agent 探测实现

```python
from pydantic import BaseModel

class DetectResult(BaseModel):
    """Agent 输出的结构化探测结果"""
    services: list[ServiceConfig]
    dependencies: list[DependencyConfig]
    raw_summary: str  # Agent 的解释说明（审计/调试用）

async def detect(self, workspace: Path) -> DeployConfig:
    """Agent 读目录结构 + 关键配置文件，一次性输出标准化 DeployConfig。"""
    result: DetectResult = await llm.structured_output(
        system="""你是项目栈探测专家。分析目录结构，读取关键配置文件
        （package.json, requirements.txt, go.mod, Cargo.toml, 
         pom.xml, composer.json, Gemfile, CMakeLists.txt 等），
        识别每个可部署服务的语言、框架、构建命令、启动命令、端口、
        环境变量，以及所需的依赖服务（数据库、缓存等）。

        对已知框架用标准命令（如 npm install && npm run build），
        对非标准项目从文件结构推断合理的构建/启动方式。""",
        tools=[listdir, read_file],
        schema=DetectResult,
        prompt=f"分析 {workspace} 目录，输出所有可部署的服务和依赖。",
    )

    return DeployConfig(
        project_id=workspace.name,
        services=result.services,
        dependencies=result.dependencies,
        detected_at=datetime.now(timezone.utc),
    )
```

~50 行。无需维护 SIGNATURES 表。

### sanity check

Agent 输出后做确定性校验（不通过的字段驳回重试）：

- 端口范围 1024–65535
- `dir` 路径在 workspace 下真实存在
- 依赖镜像名合法（`postgresql` / `mysql` / `redis` / `mongodb`）
- `build_command` 和 `start_command` 非空

### 数据结构（Agent 输出格式）

```python
@dataclass
class DeployConfig:
    project_id: str
    services: list[ServiceConfig]
    dependencies: list[DependencyConfig]
    detected_at: datetime

@dataclass
class ServiceConfig:
    name: str              # "backend"
    dir: str               # "./backend"
    language: str          # "python"
    framework: str | None  # "fastapi"
    build_command: str     # "pip install -r requirements.txt"
    start_command: str     # "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    port: int              # 8000
    env_vars: dict[str, str]

@dataclass
class DependencyConfig:
    type: str              # "postgresql" / "mysql" / "redis" / "mongodb"
    version: str           # "16"
    port: int              # 5432
    need_data_seed: bool   # 是否同步种子数据
```

### 探测时机

- **主触发**：用户首次进入部署面板（或点「开始部署」时），workspace 尚未有有效 DeployConfig
- **手动触发**：用户点「重新探测」按钮（结构变了、Agent 上次误判、加了新服务）
- **探测结果持久化到 DB**（deployment 表 JSONB 列），后续部署直接读取，不重复调用 Agent

---

## 五、模块二：Pipeline Engine（部署执行）

### 输入/输出

- 输入：`DeployConfig`（从 DB 读取）+ 最新源码（workspace 目录）
- 输出：运行中的容器 + `preview_url`

### 部署阶段

```
[launch]  (0.5s)  创建部署记录（status=queued）
                    - 分配 deploy_id
                    - 记录 git commit hash + message
                    - 读 deploy_config

[package] (2-5s)  代码打包
                    - 复制源码到构建目录
                    - 产出标准化 tar 包

[build]   (30-120s)并行构建所有 runtime service
                    - for each service in config.services:
                        docker build -t agenthub/{project}-{name}:latest {dir}
                        （有 Dockerfile 直接用，没有则从 Nixpacks 生成）
                    - 或直接用 Nixpacks: nixpacks build --name {name} {dir}

[deploy]  (5-20s)  编排 + 启动
                    - generate_docker_compose(config)  ← 动态拼 YAML
                    - docker compose up -d
                    - 等待健康检查通过
                    - 端口分配 + Nginx/Caddy 反向代理 route
                    - 子阶段并行:
                      [deploy][postgres] ──┐
                      [deploy][redis]    ──┤ 并行
                      [deploy][backend]  ──┤
                      [deploy][frontend] ──┘
                             │
                             ▼
                      [deploy][health]    ← 全部就绪后验证
                      [deploy][nginx]     ← 注册 route
```

### 动态 docker-compose 生成

```python
def generate_docker_compose(config: DeployConfig) -> str:
    """根据 DeployConfig 动态拼接 docker-compose.yml"""
    services = {}

    # 运行时服务（Nixpacks 或自定义 Dockerfile 构建的镜像）
    for svc in config.services:
        env = {}
        # 自动注入数据库/缓存连接地址
        for dep in config.dependencies:
            if dep.type in ("postgresql", "mysql"):
                env["DATABASE_URL"] = f"{dep.type}://agenthub:password@{dep.type}:{dep.port}/app"
            elif dep.type == "redis":
                env["REDIS_URL"] = f"redis://redis:{dep.port}/0"

        env.update(svc.env_vars)

        services[svc.name] = {
            "image": f"agenthub/{config.project_id}-{svc.name}:latest",
            "environment": env,
            "depends_on": _depends_on_list(config.dependencies),
            "networks": [f"{config.project_id}-net"],
            "mem_limit": "512m",
            "cpus": "1.0",
        }

    # 依赖服务（官方镜像）
    for dep in config.dependencies:
        services[dep.type] = {
            "image": f"{dep.type}:{dep.version}-alpine",
            "environment": DEFAULT_ENV.get(dep.type, {}),
            "volumes": [f"{dep.type}_data:/var/lib/{dep.type}/data"],
            "networks": [f"{config.project_id}-net"],
            "mem_limit": "256m",
        }

    compose = {
        "services": services,
        "networks": {
            f"{config.project_id}-net": {"driver": "bridge"}
        },
        "volumes": {f"{dep.type}_data": None for dep in config.dependencies},
    }
    return yaml.dump(compose)
```

---

## 六、模块三：前端部署面板

### 6.1 顶部 Tab 栏

```
┌──────────────────────────────────────────────────────────────┐
│  [总览]  [日志]  [分析]  [Trace]  [渠道]  [用量管理]           │
└──────────────────────────────────────────────────────────────┘
```

| Tab | 内容 | 数据来源 |
|-----|------|---------|
| **总览** | 部署状态、版本、域名、环境变量、数据库、资源配置 | deployment 表 + DeployConfig |
| **日志** | 实时容器日志流，支持关键词过滤 | `docker logs -f <container>` |
| **分析** | 构建耗时拆解、各阶段耗时趋势 | Pipeline 计时数据 |
| **Trace** | 请求链路追踪（API 服务上线后可用） | OpenTelemetry / 日志关联 |
| **渠道** | API/Webhook/WebSocket 等渠道开关 | 渠道配置表 |
| **用量管理** | CPU/RAM/磁盘/网络历史用量 | `docker stats` 采集 |

### 6.2 总览 Tab 布局

```
┌──────────────────────────────────────────────────────────────┐
│  开始部署你的项目吧                                           │
│                                                              │
│  ┌─ 渠道 ──────────────────────────────────────────────────┐ │
│  │  已开启的渠道                                            │ │
│  │  API 服务会在部署后默认上线。如需上线或下线渠道，          │ │
│  │  请前往「渠道」页签，开启或关闭相应渠道即可，无需重新部署。 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ 部署版本 ──────────────────────────────────────────────┐ │
│  │  d1a9c7175f                                              │ │
│  │  chore(sandbox): refresh pyproject.toml / uv.lock        │ │
│  │  6 小时前                                                │ │
│  │                          数据来源: git log -1 + Docker image tag │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ 部署域名 ──────────────────────────────────────────────┐ │
│  │  ymx2qx3845.agh.dev                                      │ │
│  │                          数据来源: Nginx/Caddy route 分配  │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ 数据库 ────────────────────────────────────────────────┐ │
│  │  以下数据表在部署后除了同步数据表结构，也将自动同步数据    │ │
│  │                                                          │ │
│  │  ☐ users   ☐ posts   ☐ comments   ☐ settings            │ │
│  │                          数据来源: Agent 探测时识别 migration │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ 生产环境变量 ──────────────────────────────────────────┐ │
│  │  查看详情                              [新建变量]         │ │
│  │  ┌──────┬─────────────────┬───────┐                      │ │
│  │  │ KEY  │ VALUE           │ 来源  │                      │ │
│  │  ├──────┼─────────────────┼───────┤                      │ │
│  │  │ 暂无数据                                           │ │
│  │  └──────┴─────────────────┴───────┘                      │ │
│  │                          数据来源: DeployConfig.env_vars   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ 更多配置 ──────────────────────────────────────────────┐ │
│  │                                                          │ │
│  │  部署类型        动态应用                                 │ │
│  │  服务器资源      CPU: 1   RAM: 2 GiB                      │ │
│  │  构建指令        bash scripts/setup.sh            [✎]    │ │
│  │  运行指令        bash scripts/http_run.sh -p 5000 [✎]    │ │
│  │                                                          │ │
│  │  端口配置                                                 │ │
│  │  主机地址        0.0.0.0                                  │ │
│  │  应用监听端口    :80                                      │ │
│  │                          数据来源: DeployConfig (Agent 探测) │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │                    [开始部署]                              ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### 6.3 各 Tab 详细说明

**日志 Tab**：
```
┌──────────────────────────────────────────────────────────────┐
│  [backend] [frontend] [postgres] [redis]    🔍 搜索日志...   │
│                                                              │
│  2026-06-09T15:22:01  backend   | INFO  Starting uvicorn     │
│  2026-06-09T15:22:02  backend   | INFO  Application startup  │
│  2026-06-09T15:22:03  frontend  | ready in 342ms             │
│  2026-06-09T15:22:03  postgres  | LOG  database ready        │
│                                                              │
│  [自动滚动]  [下载]  [清屏]                                    │
└──────────────────────────────────────────────────────────────┘
```
数据来源：`docker logs --tail 500 -f <container>`，多容器日志按时间戳合并，前端按服务名筛选。

**分析 Tab**：
```
┌──────────────────────────────────────────────────────────────┐
│  构建耗时                                      首次  增量缓存  │
│  ┌──────────┬─────────┬──────────┬─────────┐                 │
│  │ backend  │ ████████████████    │ 45s    12s  │                 │
│  │ frontend │ ██████████          │ 28s     8s  │                 │
│  │ postgres │ ██                  │  5s     3s  │                 │
│  │ redis    │ █                   │  3s     2s  │                 │
│  └──────────┴─────────┴──────────┴─────────┘                 │
│                                                              │
│  部署历史                                       状态          │
│  v3  2026-06-09 15:22  总耗时 81s               ✅           │
│  v2  2026-06-09 15:18  总耗时 92s               ❌           │
│  v1  2026-06-09 15:10  总耗时 105s              ✅           │
│                          数据来源: Pipeline 阶段计时           │
└──────────────────────────────────────────────────────────────┘
```

**监控数据采集**：Docker daemon 原生提供，不需要额外基础设施。

| 指标 | 命令 | 采集频率 |
|------|------|---------|
| CPU / RAM | `docker stats --no-stream` | 每 10s |
| 磁盘 | `docker system df` | 每小时 |
| 网络 | `docker inspect` 读网络统计 | 每 10s |



---

## 七、部署状态机（扩展现有）

```
queued ──→ packaging ──→ building ──→ deploying ──→ ready
  │            │             │             │           │
  └────────────┴─────────────┴─────────────┴──→ failed  │
                                                   │    │
                                            deleted ←────┘
```

与现有状态机（`queued → building → ready/failed → deleted`）兼容，仅在 building 和 ready 之间插入 `packaging` + `deploying` 两个子阶段。

---

## 八、实施分阶段

| 阶段 | 范围 | 核心交付 | 预计 |
|------|------|---------|------|
| **P1** | StackDetector 文件签名层 | 扫描 workspace → 识别语言/框架 → DeployConfig → 持久化 DB | 1 天 |
| **P2** | Pipeline 基础 + 单服务 | Docker build + run，真实 preview_url，替换模拟逻辑 | 2 天 |
| **P3** | 多服务 docker-compose | 动态 YAML 生成，数据库/缓存容器编排，环境变量注入 | 1 天 |
| **P4** | AI 兜底探测 | 非标准项目 LLM 推断构建命令 | 0.5 天 |
| **P5** | 部署面板完整 UI | 配置页 + 接入文档右侧面板 | 1 天 |

---

## 九、P1 具体实现清单

### 新增文件

```
src/backend/app/domain/deploy/detector.py    # StackDetector
tests/unit/domain/deploy/test_detector.py    # 探测逻辑测试
```

### 修改文件

```
src/backend/app/domain/deploy/deployment.py
  - Deployment 聚合根加 deploy_config: DeployConfig | None
  - DeploymentPlan 加 files 字段改为可选（多服务场景从磁盘读）

src/backend/app/application/services/deploy_service.py
  - start() 调用 StackDetector.detect()
  - DeployConfig 持久化到 deployment 表 JSONB 列

src/backend/app/domain/deploy/config.py      # DeployConfig / ServiceConfig / DependencyConfig
src/backend/app/schemas/deploy.py            # DeployConfigOut 响应 schema

alembic migration                            # deployment 表加 deploy_config JSONB + git_commit TEXT
```

---

## 十、关键决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 构建引擎 | Docker（宿主机 sock） + 可选 Nixpacks | AgentHub 宿主机模式已有 Docker，Nixpacks 覆盖 20+ 语言免除维护模板 |
| 多服务编排 | 动态生成 docker-compose.yml | 声明式、可复用、docker compose 原生支持网络/卷/健康检查 |
| 探测时机 | 首次部署时一次 | Agent 调用成本低（$0.01-0.05），但每次部署重复探测无意义。配置持久化 DB，手动可重新触发 |
| AI 角色 | 探测（一次）+ 配置修复（按需） | 探测：Agent 读文件输出 DeployConfig（替代维护 50+ detector）。修复失败时仅重新生成部署配置文件（Dockerfile/compose），不碰用户代码 |
| 沙箱安全 | Level 1（独立 network + mem_limit + cpus 限制） | MVP 够用，P3+ 加固 |

---

## 十一、部署失败处理与人工介入

### 11.1 可以接受失败

一键部署的成功率取决于项目复杂度。预期：简单项目（单语言 + 无外部依赖）>95%，中等项目（前后端分离 + 数据库）>80%，复杂项目（多服务 + 消息队列 + 非标准构建）首次常常需要人工介入。

**设计原则：失败不是 Bug，是交互起点。**

### 11.2 失败分层

```
失败类型                  根因                    频率预估
──────────────────────────────────────────────────────────
L1: 探测失败            无已知签名文件               5%
                        AI 推断错误
                        （如把 Rust 项目误判成 C）

L2: 构建失败            依赖版本冲突                  15%
                        缺少系统库（gcc/make/openssl）
                        编译错误
                        构建超时

L3: 启动失败            端口冲突                      10%
                        环境变量缺失
                        启动命令错误
                        数据库连接失败

L4: 运行时失败           健康检查不通过                5%
                        进程 crash
                        内存不足 OOM
```

### 11.3 架构决策：全 Docker 隔离

**结论：每个部署一个完整的 Docker Compose 栈，项目代码 + 运行时 + 依赖服务全部容器化。**

| 方案 | 描述 | 多项目隔离 | 迭代速度 | 环境可靠性 |
|------|------|:----------:|:--------:|:----------:|
| 宿主机裸跑 | 源码在宿主机，依赖全局安装 | ❌ 必然退化 | 秒级 | 低（污染累积） |
| 混合模式 | 仅依赖服务进 Docker，代码宿主机跑 | 部分 | 秒级 | 中（系统库仍冲突） |
| **全 Docker** | 源码 + 运行时 + 依赖服务全容器化 | ✅ 完全隔离 | 分钟级（重建） | **高（确定性）** |

选择理由：

1. **多会话多项目 → 宿主机必然退化**：项目 A 装 Node 18、项目 B 装 Node 22、项目 C 用特定 C++ 编译器版本 → 共享宿主机会逐步污染，没有回滚机制
2. **部署 = 确定性快照**：每个 `docker build` 产出的镜像是一个完整、可复现的运行时闭包。失败可以回滚到上一个成功镜像，不依赖宿主机状态
3. **隔离是不需要维护的**：宿主机沙箱需要持续清理、版本管理脚本、冲突检测。Docker 原生隔离，零维护成本
4. **时间消耗可接受**：`docker build` 首次 2-5 分钟，增量构建利用 Docker layer cache 后 30-60 秒。比宿主机环境退化后的排障时间便宜得多

**代价清单**：
- 首次构建慢（可通过 layer cache 缓解）
- 磁盘占用（每个项目 200-800MB 镜像）
- Docker daemon 资源开销（已有的，AgentHub 自己也在用）

### 11.4 失败处理：两层分流

核心原则：**Agent 只修部署配置，不碰用户代码。配置问题自动修复无提示，代码问题直接返回不自动修。**

```
部署失败 → 错误日志分类
    │
    ├─ 部署配置问题（缺系统库、端口不对、依赖遗漏、build_command 无效）
    │   → Agent 读错误日志 + 当前文件 → 自动生成修正版 → 覆盖 → 重新部署
    │   → 全程无提示，用户感知只是多了一次重试
    │   → 最多 3 次，超出放弃并提示用户
    │
    └─ 用户代码问题（编译错误、逻辑 bug、assert 失败）
        → 直接返回错误，不做任何自动修复
```

### 11.5 交互式诊断面板

**部署配置问题 → 自动修复，无提示：**

```
┌──────────────────────────────────────────────────────────────┐
│  🚧 部署中 — 第 2 次尝试（自动修复配置）                      │
│                                                              │
│  ✅ [build]   [frontend]  成功（layer cache）    (12s)       │
│  ❌ [build]   [backend]   失败（自动修复中…）      (3s)       │
│       ModuleNotFoundError: No module 'redis'                 │
│       → Agent 自动更新 Dockerfile，重试中…                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

配置问题自动修复，最多重试 3 次。用户只看到进度面板多了一行「自动修复中…」，无需任何操作。用户代码问题不做自动修复，直接返回错误供人处理。

**版本管理**：每次成功构建自动保留镜像（tag: `deploy-v1`、`deploy-v2`……），失败的不保留。回滚 = 切换到上一个成功镜像，无需重新 build。最近 5 个版本保留，超出自动清理。

```
部署历史面板：

  v3  ✅  2026-06-09 15:22  当前
       Image: agenthub/deploy-blog:v3 (245 MB)

  v2  ❌  2026-06-09 15:18  启动失败
       Image: agenthub/deploy-blog:v2 (242 MB)

  v1  ✅  2026-06-09 15:10
       Image: agenthub/deploy-blog:v1 (240 MB)
       [预览此版本]  [回滚到此版本]
```


---

## 十二、复杂项目边界与能力上限

### 12.1 AgentHub 部署引擎定位

**不是替代 K8s 或专业 CI/CD**，而是覆盖 **80% 中小型项目的开发→预览场景**。

```
✅ 适合部署                          ❌ 不适合部署
─────────────────────────────────    ─────────────────────────────
单语言项目（Python/Node/Go/...）     分布式系统（微服务 20+）
前后端分离（2-5 个服务）              需要 GPU 的模型推理
依赖标准数据库/缓存/消息队列          自建 K8s + Helm + Istio
无特殊硬件需求                       需要持久化大容量存储（>10GB）
单机可承载                          需要多机房/异地/专线
静态站点                            需要合规审计环境（金融/医疗）
Dockerfile 项目                      嵌入式系统/ARM 特定硬件
```

### 12.2 复杂项目降级路径

遇到超出能力范围的项目，不是硬上，而是**优雅降级 + 给用户可操作的方案**。

```
检测到复杂项目特征:
  - 微服务数量 > 10           → 标记为「分布式项目」，不自动编排
  - 存在 k8s/helm 配置        → 标记为「K8s 项目」，建议使用 ArgoCD/Helm
  - 存在 GPU 依赖（CUDA/nvidia）→ 标记为「GPU 项目」，无法提供 GPU 容器
  - 单服务镜像 > 2GB          → 警告「构建/启动可能很慢」
  - 存在 terraform/pulumi     → 标记为「IaC 项目」，基础架构无法自动创建
  - 总服务数 > 20             → 标记为「大规模项目」，超出单机承载
```

**降级动作：**

| 检测到 | 动作 |
|--------|------|
| 分布式/微服务（>10 服务） | 只部署用户选择的 2-3 个核心服务，其余标注「手动管理」 |
| K8s 项目 | 生成 `kubectl apply` 命令，不尝试 docker compose |
| GPU 项目 | 生成 Dockerfile，用户自己想办法 run |
| IaC 项目 | 跳过基础设施创建，只处理应用层容器 |
| 超大规模 | 直接建议用户使用专业 CI/CD，AgentHub 只做代码协作 |

### 12.3 环境复杂度分级

```
Level 0「静态」     纯 HTML/CSS/JS → nginx serve            覆盖率 ~25%
Level 1「单服务」    Python/Node/Go 单体 → docker build+run  覆盖率 ~45%
Level 2「多服务」    前后端 + DB + 缓存 → docker compose     覆盖率 ~20%
Level 3「有状态」    需要数据迁移、定时任务、消息队列         覆盖率 ~7%
Level 4「分布式」    微服务 10+、服务发现、配置中心           覆盖率 ~3%
                     ↑
                AgentHub 定位：Level 0-3
                Level 4 → 降级，建议专业方案
```

### 12.4 不承诺的场景

以下场景**明确不覆盖**，探测到时直接告知用户：

```
- GPU/TPU 工作负载          → "项目需要 GPU，当前环境不支持"
- 需要持久化大容量存储       → "项目需要持久化卷 >10GB，建议使用云存储"
- 需要特殊内核模块           → "项目需要 eBPF/XDP，Docker 容器不支持"
- 需要多节点集群             → "项目需要分布式集群，建议使用 K8s"
- 需要固定公网 IP            → "项目需要固定 IP，当前不支持"
- ARM 架构特定指令           → "项目需要 ARM64，当前环境是 x86_64"
- 需要合规认证环境           → "项目需要 SOC2/HIPAA 合规环境，AgentHub 不提供"
```
