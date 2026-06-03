# M-B05 — DEPRECATED 标记

> **上一版模块名**：create（创建服务）
> **DEPRECATED 时间**：2026-06-03
> **修订依据**：[可行性问题清单_2026-06-03.md](../../../可行性问题清单_2026-06-03.md) I-01/I-02/I-03/I-04/I-05
> **处置**：**[RETAIN] 保留作设计参考**
> **真实落点**：映射到 src/backend/app/application/mcp/create.py（F-018/F-019/F-020）
> **单一权威入口**：[`../../../README-REVISION.md`](../../../README-REVISION.md)

---

## 0. 为什么 DEPRECATED

本模块的上一版设计落到虚构的 `src/agenthub/` Poetry monorepo（**真实代码树中不存在**），与现有 `src/backend/app/` 5 层洋葱冲突，且违反 AR-01/AR-02 项目红线。

可行性清单 12 项问题中，本模块归属的类别：
- [BLOCK] I-01 落地目标是虚构的 `src/agenthub/` 新仓
- [BLOCK] I-02 分层语义和 AR-01 洋葱相反
- [BLOCK] I-03 违反 AR-02（扩展应只加 Adapter）
- [BLOCK] I-04 技术栈漂移（Poetry/gRPC/Vault/OTel/K8s 全非现有栈）
- [BLOCK] I-05 13/22 模块与 MCP 正交（超 MVP 范围）

## 1. 本目录内的文件处置

| 文件类型 | 数量 | 处置 |
|----------|------|------|
| API-*.md | 1 | [RETAIN] 保留作方法清单参考（不直接落地） |
| FC-*.md | 1 | [RETAIN] 保留作接口注释参考 |
| FDR-*.md | 1 | [RETAIN] 保留作文件设计记录参考 |
| FF-*.md | 1 | [RETAIN] 保留作功能函数清单参考 |
| FH-*.md | 1 | [RETAIN] 保留作接口头注释参考 |
| 桩代码（.py） | 视目录 | [X] import 不存在的 `agenthub.*` 包；**不要直接拷进 `src/backend/app/`** |

## 2. 不再使用

- [X] 引用 `from agenthub.<x> import ...` 的所有内容（x ∈ core,access,application,infrastructure,data,eventbus）
- [X] Poetry 配置 / gRPC proto / Vault / OTel / K8s manifests
- [X] 自建进程池 / eventbus / 多 OS 沙箱矩阵

## 3. 真正落点

**[RETAIN] 保留作设计参考**

真实目标：映射到 src/backend/app/application/mcp/create.py（F-018/F-019/F-020）

落地细节见：
- `../../../README-REVISION.md`（单一权威入口）
- `../../../06-详细设计/FS-MCP-V1.0-20260602.md`（文件结构）
- `../../../06-详细设计/SA-MCP-V1.0-20260602.md`（架构概览）
- `../../../06-详细设计/MD-MCP-V1.0-20260602.md`（数据模型）
- `../../../06-详细设计/IC-MCP-V1.0-20260602.md`（接口契约）

## 4. 重新启用条件

如需重新启用本模块：
1. 提交 ADR 到 `worklogs/decisions/` 说明复用场景
2. 明确所属下期 NB-XX 编号
3. 通过 PR-01 接口冻结 + PR-09 SPEC 同步
4. 更新本文档 `处置` 字段

---

*本 DEPRECATED 标记是 MCP 接入**模块废弃**唯一记录。如需重新启用，按 §4 流程走。*
