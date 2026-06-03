# FC-M-C01 接口注释清单

> 模块: M-C01 Sandbox Engine
> 版本: V1.0 · 日期: 2026-06-03
> 角色: DD-M-10 详细设计师（模块）
> 来源: [DD-001:IC-008 + MD/M-C01 + FS-010 + CS §1]

## 1. 对外接口清单（与 IC-008 API-200 sandbox.run 对齐）

| 编号 | 名称 | 签名 | 异常 | 注释所在文件 |
|------|------|------|------|-------------|
| API-200 | sandbox.run | `async def run(cmd: list[str], limits: Limits \| None = None, timeout_sec: int \| None = None) -> SandboxResult` | ValidationError(SANDBOX_INVALID_CMD 400) / TimeoutError(SANDBOX_TIMEOUT 408) / SystemError(SANDBOX_OOM 500) / SystemError(SANDBOX_BACKEND_UNAVAILABLE 503) | runner.py: `SandboxRunner.run` |
| API-200 | sandbox.get_backend | `@classmethod def get_backend(cls) -> SandboxBackend` | SystemError(SANDBOX_BACKEND_UNAVAILABLE 503) | factory.py: `SandboxFactory.get_backend` |

## 2. 内部接口清单

| 编号 | 名称 | 签名 | 注释所在文件 |
|------|------|------|-------------|
| IF-MC01-01 | SandboxBackend.run | `async def run(cmd: list[str], limits: Limits) -> SandboxResult` | backends/base.py: `SandboxBackend.run` |
| IF-MC01-02 | SandboxBackend.is_available | `async def is_available() -> bool` | backends/base.py |
| IF-MC01-03 | SandboxBackend.cleanup | `async def cleanup() -> None` | backends/base.py |
| IF-MC01-04 | SandboxRunner._validate_cmd | `@staticmethod def _validate_cmd(cmd: object) -> None` | runner.py |
| IF-MC01-05 | SandboxFactory.reset_cache | `@classmethod def reset_cache(cls) -> None` | factory.py |
| IF-MC01-06 | SandboxFactory._is_wsl2 | `@staticmethod def _is_wsl2() -> bool` | factory.py |
| IF-MC01-07 | SandboxFactory._cgroup_v2_available | `@staticmethod def _cgroup_v2_available() -> bool` | factory.py |
| IF-MC01-08 | SandboxFactory._docker_available | `@staticmethod def _docker_available() -> bool` | factory.py |
| IF-MC01-09 | LinuxCgroupBackend.cleanup_unit | `async def cleanup_unit(unit: str) -> None` | backends/linux_cgroup.py |
| IF-MC01-10 | LinuxCgroupBackend._read_peak | `async def _read_peak(unit: str) -> int` | backends/linux_cgroup.py |
| IF-MC01-11 | DockerBackend._stop_container | `async def _stop_container(name: str) -> None` | backends/docker.py |

## 3. 注释覆盖率统计

| 维度 | 应注释 | 已注释 | 覆盖率 |
|------|--------|--------|--------|
| 文件头 | 13 | 13 | 100% |
| 类 | 9 | 9 | 100% |
| 函数/方法 | 26 | 26 | 100% |
| 测试场景 | 40 | 40 | 100% |
| **合计** | **88** | **88** | **100%** |

## 4. 接口契约在注释中的体现

- IC-008 (API-200 sandbox.run) → 在 `SandboxRunner.run` 的 docstring 中完整复制入参/出参/错误码
- IC-008 (concurrency 5 per-node) → 在 `SandboxRunner.__init__` 注释 + `runner.py` 行注释
- IC-008 (timeout 30s) → 在 `Limits` 默认值 + `SandboxRunner.run` docstring
- IC-008 (rss_peak/duration_ms/backend/killed_reason) → 在 `SandboxResult` 字段注释
- [TD:S-026] 拒绝 str 拼接 → 在 `_validate_cmd` docstring + class-level 行注释
- [TD:TD-003] WSL2 → Docker fallback → 在 `SandboxFactory.get_backend` docstring

## 5. 来源追溯

所有函数/类/字段注释均带 `[DD-001:IC/IC-008]`、`[DD-001:MD/M-C01]`、`[DD-001:TD/S-026]`、`[DD-001:TD/TD-003]`、`[DD-M推断:依据]` 五类来源标注, 可逐条追溯。
