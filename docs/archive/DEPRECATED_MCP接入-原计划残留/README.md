# DEPRECATED — MCP 接入原计划残留（2026-06-03 归档）

> ⚠️ **本目录全部弃用,仅作历史追溯,禁止据此落地。**
> 现行权威：[`docs/plan/后续升级计划/MCP接入/README-REVISION.md`](../../plan/后续升级计划/MCP接入/README-REVISION.md)

## 归档原因

MCP 接入计划在 2026-06-03 经可行性核验(12 项问题,见 `可行性问题清单_2026-06-03.md`)后做了修订版重写。以下内容是修订前的残留,与真实代码树 `src/backend/app/` 冲突,按用户决策(目录治理 = 移 archive 加 DEPRECATED_ 前缀)归档于此。

| 子目录 | 内容 | 弃用原因 |
|--------|------|----------|
| `07-文件框架/` | 445 个文件:22 模块 × 巨型 docstring 空桩 | 全部 `import agenthub.*` 引用**不存在的包**;落地树是虚构的 `src/agenthub/` monorepo(可行性 I-01/I-09) |
| `bak/` | 01-需求澄清 / 02-调研验证 的早期备份快照 | 修订迭代过程产物,已被定稿版取代 |
| `02-重复变体/` | `*-MCP接入-*` 命名的 PRD-REVISION / RESEARCH / SOURCES 三份 | 与 `02-调研验证/` 下 `*-MCP-*` 权威版重复且更短/更旧;权威版已保留在原位 |

## 现行落地以这些为准(均在 `docs/plan/后续升级计划/MCP接入/`)

- `README-REVISION.md` — 单一权威入口
- `06-详细设计/{FS,MD,IC}-MCP-V1.0` — 文件结构 / 数据模型 / 接口契约(已按真实代码树重写)
- 接口冻结草案 → `docs/specs/04-commands_命令接口.md` §2.6（🔒 PR-01 待 Review）
