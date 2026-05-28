# 代码编写规范 — AgentHub

> **本规范是 [ai-workflow 第二步·迭代开发](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) 的细化**：
> - 细化 **§2.1 实现** —— 写代码时必须满足的硬约束（命名 / 错误处理 / 安全 / 日志）
> - 细化 **§2.3 审查** —— 审 `git diff` 时逐条核对的清单
>
> AgentHub 栈：Python（FastAPI async + Pydantic v2 + SQLAlchemy ORM + ruff）+ TypeScript（strict + Zustand + ESLint）。同步阻塞代码、`any` 类型、裸 SQL 在生产路径**任一条**违反即 CR 不通过。

---

## 一、红线（必守 · CR 命中任一条即打回）

每条都有自动检测方式——规则要能被工具拦下。

### Python 后端

| # | 红线 | 怎么自动抓 |
|---|------|-----------|
| **CR-01** | 禁裸 `print()`，统一用 `logging` | ruff `T20` |
| **CR-02** | 禁裸 SQL 字符串拼接，必须参数化（`db.execute(sql, params)`） | ruff `S608` (bandit) + CR |
| **CR-03** | 数据库变更必须走 Alembic Migration，禁手动改表 | grep `ALTER TABLE` 出现在 .py 即打回 + 审查 |
| **CR-04** | API 端点 + 外部 API 调用 + DB 操作必须 try/except，记录日志并返回标准错误响应 | CR |
| **CR-05** | 所有 API 输入必须经 Pydantic v2 model 校验，禁 `request.json()` 裸字典 | CR + 类型检查 |
| **CR-06** | 外部 API 必须 timeout + retry + 熔断（默认 `httpx` `timeout=30.0`） | CR + 运行时监控 |
| **CR-12** | 禁同步阻塞在 async 上下文：禁 `time.sleep()` / 同步文件 I/O / 同步 HTTP | ruff `ASYNC` 系列 + CR |

### TypeScript 前端

| # | 红线 | 怎么自动抓 |
|---|------|-----------|
| **CR-07** | TypeScript strict mode 零错误；禁 `any`（除非明确注释原因） | `tsc --noEmit` + eslint `@typescript-eslint/no-explicit-any` |
| **CR-08** | 禁在 React render 中调用异步函数；副作用放 `useEffect` 或 event handler | eslint `react-hooks/rules-of-hooks` + CR |
| **CR-09** | 组件建议 < 200 行；超出优先拆分 + Hooks 抽离（warning 级） | eslint `max-lines` warning |

### 通用

| # | 红线 | 怎么自动抓 |
|---|------|-----------|
| **CR-10** | 禁硬编码密钥/Token/密码；全部环境变量注入，`.env` 不入 Git | ruff `S105/S106/S107` + `gitleaks` + `.gitignore` 校 `.env` |
| **CR-11** | 禁遗留调试代码：`print()` / `console.log` 生产路径、被注释掉的代码块 | ruff `T20` `ERA001` + eslint `no-console` |

---

## 二、落地：把规则装进工具（复制即用）

可操作的关键在于——规则不靠自觉，靠 pre-commit 和 CI 拦截。AgentHub 已在 `.pre-commit-config.yaml` 配置；下表是规则源头。

**Python — `backend/pyproject.toml`：**

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
# T20=print  S=安全(bandit)  E722=裸except  T100=调试断点
# ASYNC=async-aware  ERA001=注释代码块  N=命名
select = ["E", "F", "N", "T20", "T100", "S", "ASYNC", "ERA001", "PLR0915"]
ignore = ["S101"]  # 测试中允许 assert

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S", "T20"]   # 测试可用 print
"alembic/versions/**" = ["E501"]
```

**`.pre-commit-config.yaml`（AgentHub 已挂载，新增钩子追加即可）：**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: ["--fix"]
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
  - repo: local
    hooks:
      - id: check-worklog
        name: 校 worklog + STATUS 更新
        entry: python scripts/check_worklog.py
        language: system
        stages: [pre-push]
      - id: check-docs
        name: 校文档命名 + CLAUDE 引用 + hooks 装机
        entry: python scripts/check_docs.py
        language: system
        stages: [pre-push]
      - id: check-branch
        name: 校分支命名 feature/<domain>/<desc>
        entry: python scripts/check_branch.py
        language: system
        stages: [pre-push]
```

**TypeScript — `frontend/eslint.config.js`：**

```js
export default [
  {
    rules: {
      "no-console": ["error", { allow: ["warn", "error"] }],
      "@typescript-eslint/no-explicit-any": "error",
      "max-lines": ["warn", { max: 200, skipBlankLines: true }],
      "react-hooks/rules-of-hooks": "error",
    },
  },
];
```

装好后，CR-01/CR-10/CR-11/CR-07/CR-08 在 `git commit` 时自动挡下，CR 只需聚焦工具盲区（CR-02/04/05/06/09/12）与业务逻辑。

---

## 三、写代码时的决策表

数值阈值一律是 **linter 警告级、可按项目调**，不是铁律——触发时要么拆分，要么写一行注释说明为何例外。

### 命名

| 元素 | 风格 | 示例 |
|------|------|------|
| Python 变量 / 函数 | `snake_case` | `agent_id` / `dispatch_task` |
| Python 类 / Pydantic Model | `PascalCase` | `AgentService` / `ChatMessageIn` |
| 常量 | `UPPER_SNAKE` | `MAX_RETRY_COUNT` |
| TS 变量 / 函数 | `camelCase` | `agentId` / `dispatchTask` |
| TS 类型 / 接口 / 组件 | `PascalCase` | `AgentCard` / `ChatStore` |
| 布尔 | `is/has/can` 前缀 | `isStreaming` `hasPermission` |
| 文件名 | `kebab-case` (TS) / `snake_case` (Python) | `agent-card.tsx` / `task_engine.py` |

> 见名知意是红线级要求：禁止 `data` / `info` / `temp` / `process` 等模糊名——CR 时读名字猜不出用途即打回。

### 结构

| 单元 | 警告阈值 | 超了怎么办 |
|------|---------|-----------|
| 函数行数 | ~50 | 抽子函数；算法密集型加注释 |
| 函数参数 | 4 | 用 dataclass / Pydantic Model |
| 类成员变量 | 7 | 按职责拆类 |
| Python 单文件 | 500 | 拆模块 |
| React 组件 | 200 | 拆子组件 + Hooks 抽离（CR-09） |

### 注释

| 何时必须写 | 何时不要写 |
|-----------|-----------|
| 复杂算法（思路与选型理由） | 复述代码（`i++ // 自增`） |
| 业务规则（"为什么这样处理"） | 与代码已不符的过时注释（直接删） |
| 临时方案标记（`TODO` `FIXME` `HACK`） | |

---

## 四、错误处理与日志（实现阶段必做）

**原则：尽早失败、明确传播、留足上下文。**

```python
import logging
logger = logging.getLogger(__name__)

async def fetch_agent(agent_id: str) -> Agent:
    try:
        return await repo.get(agent_id)
    except AgentNotFoundError:
        raise                                    # 明确传播，让上层决定
    except DatabaseError as e:
        logger.error("查询 Agent 失败 | agent_id=%s | err=%s", agent_id, e)
        raise ServiceUnavailableError("数据库不可用") from e
```

| 规则 | 要点 |
|------|------|
| 用具体异常类型 | 捕 `AgentNotFoundError`，不捕裸 `Exception`（落 CR-04） |
| 最外层统一兜底 | FastAPI 全局 exception_handler → 标准错误响应（见 [04-API](04-api_API设计规范.md)） |
| 资源用上下文管理器 | 文件 / 连接 / 锁用 `with` 自动释放 |
| 日志级别 | DEBUG（生产关）/ INFO（关键节点）/ WARN（可恢复）/ ERROR（需关注） |
| 日志带业务上下文 | `agent_id` `task_id` `group_id` 等；禁高频循环刷屏 |
| 日志脱敏 | 禁输出 `api_key` `password` `phone` 全量——`phone=138****1234` 风格 |

---

## 五、反模式

### ❌ 模糊命名

```python
def process(d):                       # 看完函数体才知道干嘛
    return d[0] + d[1]
```
✅ `def calculate_total_tokens(messages: list[Message]) -> int:` —— 名字即文档。

### ❌ 静默吞异常

```python
async def fetch_agent(agent_id):
    try:
        return await repo.get(agent_id)
    except Exception:
        pass                          # 调用方不知出错，排查时日志空白
```
✅ 见 §四：分类型捕获，明确传播或记日志后转换。

### ❌ async 上下文同步阻塞（违反 CR-12）

```python
@router.post("/notify")
async def notify(req: NotifyIn):
    time.sleep(2)                                              # ← 阻塞 event loop
    requests.get("https://api.example.com")                    # ← 同步 HTTP
```
✅ `await asyncio.sleep(2)` + `await httpx.AsyncClient().get(...)`。

### ❌ React render 中直接 await（违反 CR-08）

```tsx
function AgentList() {
  const data = await fetch("/api/agents");                     // ← 不允许
  return <ul>{data.map(...)}</ul>;
}
```
✅ `useEffect(() => { fetch(...).then(setData); }, [])` 或用 React Query。

---

## 六、检查清单（= CR §2.3 展开版）

审 `git diff` 时逐条核对；CR-01/10/11 等已被 pre-commit 拦截，这里复核工具盲区与业务逻辑。

- [ ] **CR-01** 无 `print()` / `console.log`
- [ ] **CR-02** SQL 全部参数化
- [ ] **CR-03** 表结构变更走 Alembic migration
- [ ] **CR-04** API/外部/DB 调用均 try/except，含上下文日志
- [ ] **CR-05** API 输入用 Pydantic v2
- [ ] **CR-06** 外部 API 有 timeout/retry/熔断
- [ ] **CR-07** `tsc --noEmit` 零错误；无 `any`
- [ ] **CR-08** render 中无 async；副作用在 useEffect
- [ ] **CR-09** 组件 < 200 行（或拆分理由清楚）
- [ ] **CR-10** 无硬编码密钥；`.env` 在 `.gitignore`
- [ ] **CR-11** 无 `print` `console.log` `debugger` 残留
- [ ] **CR-12** async 上下文无 `time.sleep` / 同步 I/O / 同步 HTTP
- [ ] 命名见名知意（无 `data` `temp` `process`）
- [ ] 日志不含密钥 / Token / 完整手机号 / 身份证
- [ ] 函数单一职责，超阈值已拆分或注释例外
- [ ] 无越界变更（只改本功能点该改的）

---

## 七、关联

| 方向 | 链接 |
|------|------|
| 细化自 | [ai-workflow 第二步 §2.1 实现 / §2.3 审查](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) |
| 验收标准 | [docs/specs/03-data-model_数据模型.md](../docs/specs/03-data-model_数据模型.md)（Pydantic Model 定义） |
| 分层 / 循环依赖 | [01-架构设计规范](01-architecture_架构设计规范.md) |
| 错误响应格式 | [04-API 设计规范](04-api_API设计规范.md) |
| 代码可理解性 / 调用图 | [08-代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-28 | v3.0 | 按模板骨架重写；红线替换为 CR-01~12（Python 7 + TS 3 + 通用 2）；落地配置切到 AgentHub 实际 ruff / eslint 配置；新增 CR-12 async 阻塞 |
