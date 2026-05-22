# AgentHub 代码红线

> 版本: v2.1 | 违反任一条 = CR 不通过

## Python 后端

### CR-01：禁止裸 print

```python
# 禁止
print("debug info")
# 必须
logger = logging.getLogger(__name__)
logger.info("AgentHub.Module: message")
```

### CR-02：禁止裸 SQL 拼接

```python
# 禁止
db.execute(f"SELECT * FROM tasks WHERE id = {task_id}")
# 必须
db.execute("SELECT * FROM tasks WHERE id = $1", task_id)
```

### CR-03：数据库变更必须走 Alembic Migration

禁止手动改表结构。

### CR-04：API 端点和外部调用必须有异常处理

每个 API 端点、外部 API 调用、数据库操作必须 try/except，记录日志并返回标准错误响应。纯内部工具函数不强制。

### CR-05：Pydantic v2 校验所有 API 输入

禁止直接使用 `request.json()` 裸字典。所有 API 输入通过 Pydantic model。

### CR-06：外部 API 调用必须有超时+重试+熔断

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(url, json=data)
```

## TypeScript 前端

### CR-07：TypeScript strict mode 零错误

`tsc --noEmit` 零错误。禁止 `any` 除非明确注释原因。

### CR-08：禁止在 render 中调用异步函数

副作用放在 useEffect 或 event handler。

### CR-09：React 组件超过 200 行建议拆分

超过 200 行优先考虑拆分。Hooks 逻辑抽离。不强制，但 Code Review 时会提示。

## 通用

### CR-10：禁止硬编码密钥/Token/密码

全部通过环境变量注入。`.env` 不入 Git。加密密钥必须从环境变量读取，禁止写死在代码中。

### CR-11：禁止遗留调试代码

禁止 `print()`、`console.log()` 生产路径。禁止被注释掉的代码块。

### CR-12：禁止同步阻塞在 async 上下文

FastAPI async 端点禁止 `time.sleep()`、同步文件 I/O、同步 HTTP。
