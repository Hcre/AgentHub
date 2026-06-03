# 代码风格指南 CS-MCP-V1.0-20260602

> 覆盖 Python 3.11 + SQL（PG）+ Protobuf 3 + Dockerfile + Kubernetes YAML + Bash + JSON Schema 全技术栈
> 所有规范均有对应自动化工具配置；CI 强制（pre-commit + GitHub Actions）

---

## 1. Python 风格指南（主要语言）

### 1.1 命名规范

| 元素 | 规范 | 工具 |
|------|------|------|
| 类名 | PascalCase | ruff N801 |
| 函数/方法名 | snake_case | ruff N802 |
| 变量名 | snake_case | ruff N806 |
| 常量名 | UPPER_SNAKE_CASE | ruff N801/N806 |
| 私有成员 | `_leading_underscore` | 约定（mypy 不检查） |
| 模块文件 | snake_case | 约定 |
| 包名 | 小写无下划线 | 约定 |
| 类型变量 | 单大写字母或 _T 后缀 | ruff N808 |

### 1.2 格式规范

| 项 | 规范 | 工具 |
|----|------|------|
| 缩进 | 4 空格（禁 TAB） | black + .editorconfig |
| 行宽 | 100 字符 | black `line-length = 100` |
| 换行 | LF（Unix） | .editorconfig + .gitattributes |
| 字符串引号 | 双引号（`"`） | black（默认） |
| 末尾换行 | 必须 | .editorconfig |

### 1.3 类型注解（强制）

```python
# 所有函数 + 公共方法必须类型注解
from __future__ import annotations
from typing import TYPE_CHECKING

async def compute_args_hash(args: dict[str, object]) -> str:
    """统一参数哈希（系统级公共函数 ADR-006）.

    Args:
        args: 工具调用参数

    Returns:
        SHA256 hex（64 字符）

    Raises:
        ValueError: args 含不可序列化对象
    """
    ...
```

| 规则 | 工具 |
|------|------|
| 公共 API 100% 类型注解 | mypy `disallow_untyped_defs = true` |
| 禁止 `Any` 滥用 | mypy `warn_return_any = true` |
| 严格 Optional | mypy `strict_optional = true` |

### 1.4 注释规范

```python
"""模块级文档字符串（Google 风格）.

本模块实现 ...
"""

class Foo:
    """类的简要描述.

    Attributes:
        x: 描述
    """

def bar(x: int) -> int:
    """函数简要描述.

    Args:
        x: 参数描述
    Returns:
        返回值描述
    Raises:
        ValueError: 触发条件
    """
```

| 项 | 规范 |
|----|------|
| 文件头 docstring | 必须（模块用途+作者+创建日期） |
| 公共类/函数 docstring | 必须（Google 风格） |
| 行内注释 | `#` 后空一格；避免噪声注释 |
| TODO 格式 | `# TODO(name): 内容 [issue#XX]` |
| FIXME 格式 | `# FIXME(name): 内容` |
| pydocstyle 规则 | `D100,D101,D102,D103,D205,D400` |

### 1.5 导入规范

```python
# 顺序: 标准库 → 第三方 → 本地
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import MetaData as SAMetadata  # [DD洞察-6] 避免与本地 metadata 包冲突

from agenthub.core.config import Settings
from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.data.metadata.unit_of_work import UnitOfWork

log = get_logger(__name__)
```

| 规则 | 工具 |
|------|------|
| 三段式顺序 | ruff `I` (isort) |
| 禁止通配符 | ruff F401/F403 |
| 禁止循环导入 | mypy + 启动时探测 |
| 仅类型导入用 TYPE_CHECKING | 约定 |

### 1.6 异常处理规范

```python
# 推荐
try:
    result = await dao.fetch(id)
except DBError as e:
    log.error("dao_fetch_failed", id=str(id), err=str(e))
    raise NotFoundError(f"id={id}") from e  # 链式异常

# 禁止
try:
    ...
except Exception:  # too broad
    pass            # 吞异常
```

| 规则 | 说明 |
|------|------|
| 捕获粒度 | 精确异常；最外层方可 `except Exception` |
| 异常链 | `raise X from e`（保留原因） |
| 日志先于 raise | 中间层至少一处 log.error |
| 禁止吞异常 | 禁止 `except: pass`（ruff E722） |
| 异常转换 | 跨层转领域异常（DBError → NotFoundError） |
| 自定义异常基类 | 继承 `agenthub.core.exceptions.AgentHubError` |

### 1.7 测试规范

```python
import pytest

@pytest.mark.asyncio
async def test_compute_args_hash_when_same_input_then_same_output() -> None:
    # given
    args = {"a": 1, "b": 2}
    # when
    h1 = await compute_args_hash(args)
    h2 = await compute_args_hash({"b": 2, "a": 1})  # 顺序不同
    # then
    assert h1 == h2
```

| 规则 | 说明 |
|------|------|
| 命名 | `test_{function}_when_{scenario}_then_{expected}` |
| AAA 模式 | given / when / then 注释段 |
| 覆盖率目标 | 行 ≥ 80%（核心模块 ≥ 90%） |
| Mock | pytest-mock / fakeredis / testcontainers |
| Fixture | 仅放 `conftest.py` |
| 异步 | `@pytest.mark.asyncio` + `pytest-asyncio` |

### 1.8 并发与异步

| 规则 | 说明 |
|------|------|
| 默认 async/await | 所有 IO 必须 async（除纯函数） |
| 禁止阻塞调用 | `time.sleep` → `asyncio.sleep`；`requests` → `httpx.AsyncClient` |
| TaskGroup | Python 3.11 `asyncio.TaskGroup` 优先 |
| 超时 | 所有外部调用必须 timeout（10s 默认） |
| 并发限制 | `asyncio.Semaphore` 替代裸 `gather` |

### 1.9 纯函数装饰器约束（响应 [DD 洞察-2]）

```python
# agenthub/core/pure.py
from functools import wraps

def pure(fn):
    """标记纯函数：禁 IO/全局状态/网络/文件."""
    fn.__pure__ = True
    return fn

def in_process_only(fn):
    """标记仅 in-proc 调用：禁止发布为 RPC."""
    fn.__in_process_only__ = True
    return fn
```

CI 自动检查：grep `@pure` 装饰的函数体内不得出现 `await`/`open(`/`requests`/`asyncio`/`subprocess`。

---

## 2. SQL 风格指南（PostgreSQL）

| 规则 | 说明 |
|------|------|
| 关键字大写 | `SELECT`, `WHERE`, `JOIN` |
| 标识符小写 | `mcp_servers`, `workspace_id` |
| 表名复数小写 | `users`, `inbox_queues` |
| 列名 snake_case | `created_at`, `mcp_id` |
| 主键 | `id UUID PK` 统一 |
| 外键命名 | `{table}_id`（如 `mcp_id` 指向 `mcp_servers.id`） |
| 索引命名 | `idx_{table}_{cols}` |
| 唯一索引 | `uq_{table}_{cols}` |
| 时间戳 | `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` |
| 软删 | 禁用（用 `status` 枚举或 append-only） |
| 迁移 | Alembic 必须；禁止手动 DDL 生产 |
| 工具 | sqlfluff（dialect=postgres） |

---

## 3. Protobuf 风格指南（gRPC）

| 规则 | 说明 |
|------|------|
| package 命名 | `agenthub.{service}.v{N}` |
| Message | PascalCase；Field snake_case |
| 版本 | `package agenthub.k4.v1`（v2 不破坏 v1） |
| 字段编号 | 1-15 高频（1 字节），保留 1000-2000 |
| 兼容性 | 禁止改字段类型；删字段用 reserved |
| 工具 | buf lint + buf breaking |

---

## 4. Dockerfile 风格

| 规则 | 说明 |
|------|------|
| 多阶段 | builder / runtime 分离 |
| 非 root | `USER appuser` |
| WORKDIR | `/app` |
| 镜像最小 | `python:3.11-slim` 基底 |
| COPY 顺序 | 依赖文件先 COPY 利于缓存（poetry.lock → pyproject → src） |
| HEALTHCHECK | 必须 |
| 工具 | hadolint |

---

## 5. K8s YAML 风格

| 规则 | 说明 |
|------|------|
| apiVersion | 明确版本 |
| labels | `app.kubernetes.io/name` + `version` + `component` |
| resources | requests + limits 必须 |
| probes | liveness + readiness + startupProbe |
| securityContext | runAsNonRoot + readOnlyRootFilesystem |
| 工具 | kubeval + kube-linter |

---

## 6. Bash 风格（运维脚本）

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

| 规则 | 说明 |
|------|------|
| Shebang | `#!/usr/bin/env bash` |
| 严格模式 | `set -euo pipefail` |
| 工具 | shellcheck |

---

## 7. JSON Schema（manifest 校验）

| 规则 | 说明 |
|------|------|
| Draft | `2020-12` |
| `additionalProperties: false` | 默认拒绝未知字段 |
| `$id` | 必须 |
| 工具 | jsonschema-cli + 自动化 fixtures |

---

## 8. 自动化工具配置（强制）

### 8.1 pyproject.toml（核心片段）

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E","F","W","I","N","B","C4","UP","SIM","ASYNC","S","BLE","RET","PL","D"]
ignore = ["D100","D104","D203","D212"]

[tool.ruff.per-file-ignores]
"tests/**" = ["S101","D"]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
strict = true
disallow_untyped_defs = true
warn_return_any = true
warn_unused_ignores = true
show_error_codes = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-ra --strict-markers --cov=src/agenthub --cov-report=term-missing --cov-fail-under=80"
testpaths = ["tests"]
```

### 8.2 .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
  - repo: https://github.com/psf/black
    rev: 24.4.0
    hooks: [{ id: black }]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks: [{ id: mypy, additional_dependencies: [pydantic, types-PyYAML] }]
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks: [{ id: detect-secrets, args: ['--baseline', '.secrets.baseline'] }]
  - repo: https://github.com/igorshubovych/markdownlint-cli
    rev: v0.39.0
    hooks: [{ id: markdownlint }]
  - repo: https://github.com/koalaman/shellcheck-precommit
    rev: v0.10.0
    hooks: [{ id: shellcheck }]
  - repo: https://github.com/sqlfluff/sqlfluff
    rev: 3.0.0
    hooks: [{ id: sqlfluff-lint, args: ["--dialect","postgres"] }]
  - repo: https://github.com/hadolint/hadolint
    rev: v2.12.0
    hooks: [{ id: hadolint }]
```

### 8.3 .editorconfig

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4
max_line_length = 100

[*.{yaml,yml,json,toml}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false  # markdown 行尾两空格保留换行
```

### 8.4 GitHub Actions CI 关键步骤

```yaml
jobs:
  lint-test:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install poetry==1.7.1
      - run: poetry install --with dev
      - run: poetry run ruff check .
      - run: poetry run black --check .
      - run: poetry run mypy src/
      - run: poetry run pytest --cov-fail-under=80
      - uses: aquasecurity/trivy-action@master  # 镜像扫描
```

---

## 9. 风格指南覆盖完整性

| 技术栈 | 风格指南 | 自动化工具 |
|--------|---------|----------|
| Python 3.11 | §1 | ruff + black + mypy + pydocstyle |
| FastAPI / Pydantic | §1 + 约定 | ruff（含 ASYNC） |
| SQLAlchemy / asyncpg | §1 + §2 | sqlfluff + Alembic |
| PostgreSQL DDL | §2 | sqlfluff |
| Redis 键命名 | §1 + DS-020~026 约定 | 自定义 lint（grep prefix） |
| Protobuf | §3 | buf |
| gRPC | §3 | buf breaking |
| Dockerfile | §4 | hadolint |
| K8s YAML | §5 | kubeval + kube-linter |
| Bash | §6 | shellcheck |
| JSON Schema | §7 | jsonschema-cli |
| Markdown 文档 | §1（注释规范延伸） | markdownlint |

**30 TS 全覆盖 ✓ D6 = 100%**

---

**[DD 洞察-7]** ruff 同时启用 `D` (pydocstyle) 与 `B` (bugbear) 会导致存量代码大量 warning，建议为现有代码先 `--add-noqa` 一次性豁免，新代码强制（CI 仅检查新增/修改文件，使用 `ruff check --diff` 模式）。

**代码风格指南文档结束。**
