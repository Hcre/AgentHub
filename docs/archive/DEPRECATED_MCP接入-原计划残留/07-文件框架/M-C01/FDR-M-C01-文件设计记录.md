# FDR-M-C01 文件设计记录

> 模块: M-C01 Sandbox Engine
> 角色: DD-M-10
> 日期: 2026-06-03
> 来源: 灵魂行为规范（详细设计师·模块）soul §4.11 + §6.1

## 1. 决策记录

### FDR-MC01-001: Backend 选择策略

**决策**: Linux cgroup v2 优先; WSL2 强制走 Docker 兜底 [DD-001:TD-003]; 原生 OS 后端不可用时降级 Docker.

**对比**:

| 方案 | 复杂度 | 隔离强度 | 跨平台 |
|------|--------|---------|--------|
| A. OS 原生 + Docker 兜底（采纳） | 中 | 强 (cgroup/Job/SBPL) | 中 |
| B. 仅 Docker 统一 | 低 | 中 (容器) | 高 |
| C. 仅 cgroup + 跳过其他平台 | 低 | 强 | 无 |

**选择 A**: 性能优先 (无 Docker 容器启动开销) + 跨平台 (Docker 兜底保证 Windows-WSL 团队可用).

**来源**: [DD-001:MD/M-C01 + IC/IC-008 + TD/TD-003]

### FDR-MC01-002: cmd 强制 list[str]

**决策**: SandboxRunner.run 仅接受 list[str], 拒绝 str 与含 shell 元字符元素.

**理由**:
- shell=True 永远不启用 → 杜绝 [DD-001:TD/S-026] 注入探测
- list 形式让 subprocess.exec 自动按 argv 传参, 避免任何 shell 解释

**来源**: [DD-001:TD/S-026]

### FDR-MC01-003: Limits/SandboxResult 不可变

**决策**: pydantic `ConfigDict(frozen=True, extra="forbid")`.

**理由**: 多线程场景下 backend 读取 limits 时不会读到半修改状态; Result 不可变保证可安全传给上层 Saga 上下文.

**来源**: [DD-M推断:依据] 多线程 + async 混合运行时

### FDR-MC01-004: 并发上限 5/node (Semaphore)

**决策**: SandboxRunner 内置 `asyncio.Semaphore(5)`, 第 6 个 await 阻塞.

**理由**: IC-008 性能约束 "5 并发上限 per-node"; 避免单个 worker 占用所有 fd/cgroup 槽.

**来源**: [DD-001:IC-008]

### FDR-MC01-005: Factory 单例缓存

**决策**: 类级 `_cached_backend` 缓存; `reset_cache()` 仅测试用.

**理由**: 避免每次 Runner 构造都探测 OS / Docker / cgroup; 长生命周期进程一次探测足够.

**来源**: [DD-M推断:依据]

## 2. 文件结构 5 项合规检查（[DD-001:FS §2]）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 目录层级 ≥2 | ✓ | sandbox/ + backends/ + tests/ 三层 |
| 命名规则明确 | ✓ | snake_case 文件 / PascalCase 类 |
| 文件职责定义 | ✓ | runner / factory / limits / backends/base / 4 backend 实现 / 6 测试文件 |
| 依赖关系明确 | ✓ | runner → factory → backends; backends → base; 测试不交叉 |
| 符合最佳实践 | ✓ | FastAPI/src-layout + pydantic frozen + ABC Strategy |

## 3. 代码风格一致性

- 类型注解 100% ([DD-001:CS §1.3] mypy strict)
- docstring Google 风格 ([DD-001:CS §1.4])
- pydocstyle D100/D101/D102/D103/D205/D400 已通过 ruff
- 异常继承 `agenthub.core.exceptions.AgentHubError` 子类 ([DD-001:CS §1.6])
- 禁止 `except: pass` / 禁止循环导入 ([DD-001:CS §1.5/1.6])

## 4. 跨模块文件操作 = 0（D7=100 守护）

本次产出全部位于 `产出物/07-文件框架/M-C01/`, 路径前缀均为 `infrastructure/sandbox/M-C01/*`, 零文件触及其他模块.
