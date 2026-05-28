# 文档规范 — AgentHub

> **本规范是 ai-workflow 中文档产出环节的细化**：
> - 细化 [第二步 §2.5 更新记录](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md)（worklog / STATUS / CLAUDE）与 [07-汇报](ai-workflow_AI协作开发流程/07-汇报.md)
> - 细化交付物文档（README / 设计文档 / 探索 / ADR）；支撑[收束节点](ai-workflow_AI协作开发流程/06-第三步_收束节点.md)的「文档一致性检查」
>
> **模板权威在 [docs/templates/](../docs/templates/README-模板索引.md)**——本规范只定标准与红线，模板正文不在此重抄。
> **文档自动校验**：`scripts/check_docs.py`（pre-push）。改文档结构时同步改它。

---

## 一、红线（必守）

| # | 红线 | 怎么验证 |
|---|------|---------|
| **D-01** | 项目根有 `README.md`（人类入口）+ `CLAUDE.md`（AI 入口），含「快速开始」（≤ 5 条命令跑起来） | 人工 + `check_docs.py` 校 CLAUDE 引用 |
| **D-02** | 文档与代码在同一个 PR 中改（不脱节、不分离到 Wiki） | CR diff |
| **D-03** | 公共 API 有 docstring（参数 / 返回 / 异常 / 示例） | CR + ruff `D` |
| **D-04** | 注释与代码行为一致，过时注释立即删 | CR |
| **D-05** | docs/ 根命名 `{English}_{中文}.md` 格式（如 `PRD_AgentHub_统一方案.md`） | `check_docs.py:25` DOCS_PATTERN |
| **D-06** | `docs/explore/` 子项命名 `EXP-NN_<topic>.md` / `ADR-NN-<slug>.md`（已弃用，新 ADR 进 `worklogs/decisions/`），或个人子目录 `{黎,董,袁}/<topic>.md` | `check_docs.py:88-97` |
| **D-07** | `docs/archive/` 文件 `DEPRECATED_` 前缀 | `check_docs.py:107` |
| **D-08** | `worklogs/{董,黎,袁}/` 下文件 `YYYY-MM-DD_<desc>.md` | `check_docs.py:120-134` |
| **D-09** | 禁文件名含版本后缀（`_v2` `_final` `_最新` `_old` `_new` `_副本`），需归档 → `docs/archive/DEPRECATED_<原名>.md` | `check_docs.py:147` |
| **D-10** | docs/ 树（除 `reports/`）禁 `.html`；markdown 是源 | `check_docs.py:50,137` |
| **D-11** | `CLAUDE.md` 中所有 `` `xxx.md` `` 引用必须可解析 | `check_docs.py:150-162` |
| **D-12** | pre-commit / pre-push 钩子已安装 | `check_docs.py:164-178` |

---

## 二、落地：模板复用 + 自动校验

### 模板路径

所有文档从 [`docs/templates/`](../docs/templates/README-模板索引.md) 复制起步，不手搓：

| 要写的文档 | 用哪个模板 |
|-----------|-----------|
| 工作日志 | `worklogs/template.md`（AgentHub 现有）或 `docs/templates/worklog模板.md` |
| 功能点 / 收束汇报 | `docs/templates/汇报模板.md` |
| ADR（架构决策记录） | `docs/templates/`（无专门 ADR 模板时可参考 `worklogs/decisions/` 现有文件） |
| 设计文档 | `docs/templates/plan背景模板.md` + 自由扩展 |
| BDD 规格 | `docs/templates/BDD规格模板.md` |
| README / CLAUDE / STATUS | `docs/templates/{README,CLAUDE,STATUS}模板.md`（**给新项目用，AgentHub 自身实例直接维护**） |

### docstring 范例（公共 API 必须）

```python
async def dispatch_message(
    msg: ChatMessage,
    mode: Literal["auto", "direct"] = "auto",
) -> DispatchResult:
    """根据 mention/context 路由消息到目标 Agent 或协调者。

    Args:
        msg: 待路由的聊天消息
        mode: auto 自动判断；direct 强制走到指定 agent_id

    Returns:
        DispatchResult，含 target_type、target_id、reason

    Raises:
        AgentNotFoundError: target_id 对应的 Agent 不存在
        BoundaryViolation: 触发 99-boundaries 权限矩阵的拦截
    """
```

### 自动校验（pre-push 触发）

```bash
python scripts/check_docs.py
```
检查 D-05 ~ D-12 全部红线。失败提示运行 `/doc-sync` skill 修复。

---

## 三、决策表 / 速查

### 文档放哪？（参考 [meta/FILE_GRAPH.md §三](../meta/FILE_GRAPH.md)）

| 类型 | 位置 |
|------|------|
| 规范正文 | `conventions/NN-<name>_<中文名>.md` |
| 功能规格 | `docs/specs/NN-<name>_<中文名>.md` |
| 项目计划 / PRD / 路线图 | `docs/plan/` |
| 复杂设计文档 | `docs/plan/design/<feature>_<中文>.md` |
| 调研 | `docs/research/<主题>_<中文>.md` |
| 技术探索（个人） | `docs/explore/{黎,董,袁}/<topic>.md` |
| 技术探索（团队 / 编号制） | `docs/explore/EXP-NN_<topic>.md` |
| EVOLUTION 演进日志 | `docs/explore/EVOLUTION.md` |
| ADR（架构决策） | `worklogs/decisions/NNNN-<slug>.md`（收束节点产出） |
| 汇报 / 报告 / HTML 渲染产物 | `docs/reports/` |
| 模板（给新项目复制） | `docs/templates/` |
| 归档 | `docs/archive/DEPRECATED_<原名>.md` |
| 工作日志 | `worklogs/{董,黎,袁}/YYYY-MM-DD_<desc>.md` |

### 命名规约（自动校验）

| 类型 | 格式 | 示例 |
|------|------|------|
| docs/ 根 | `{English}_{中文}.md` | `PRD_AgentHub_统一方案.md` |
| explore EXP | `EXP-NN_<topic>.md` | `EXP-03_websocket-reconnect.md` |
| explore ADR（旧） | `ADR-NN-<slug>.md` | `ADR-01-cli-first-pivot.md`（新增 ADR 改放 `worklogs/decisions/`） |
| explore 个人 | `{黎\|董\|袁}/<topic>.md` | `黎/group-chat-boundary.md` |
| archive | `DEPRECATED_<原名>.md` | `DEPRECATED_PRD_v3_完整流程方案.md` |
| worklog | `YYYY-MM-DD_<desc>.md` | `2026-05-28_phase4-conventions.md` |
| ADR（新位置）| `NNNN-<slug>.md` | `0001-cli-first-pivot.md` |

> 禁空格 / 特殊字符 / 版本后缀。

### 何时写设计文档

| 写 | 不写 |
|----|------|
| 需求不清、需多方对齐 | 简单 CRUD |
| 复杂功能（≥ 3 模块或跨域） | 纯 UI 调整 |
| 重大架构变更（触发 ADR） | 已有明确方案的小改 |

五段式：**背景 / 目标 / 方案（含 Mermaid 图）/ 影响范围 / 风险**。放 `docs/plan/design/`。

### 知识互联

| 规则 | 要点 |
|------|------|
| 文档间双向链接 | 设计文档 ↔ BDD ↔ 规范原文 互相引用 |
| 关键文档入 CLAUDE.md 目录索引 | CLAUDE.md 是 AI 入口，索引帮 AI 找到权威源 |
| 索引链接必须可解析（D-11） | `check_docs.py` 自动校 |

### 收束节点的文档维护

| 规则 | 要点 |
|------|------|
| 收束时逐份对照代码现状 | [ai-workflow/06-第三步_收束节点](ai-workflow_AI协作开发流程/06-第三步_收束节点.md) 四阶段之「文档审计」 |
| 过时文档移 `docs/archive/`，标废弃日期 | 文件首行加 `> ⚠️ 已废弃: YYYY-MM-DD，替代: docs/.../新文档.md` |
| ADR 产出 | 决议写入 `worklogs/decisions/NNNN-<slug>.md` |

### worklog 写作要点（AgentHub 现实）

- 文件名 `YYYY-MM-DD_<简短描述>.md`，放 `worklogs/{你的名字}/` 下
- 每次 push 前必更新（pre-push 校验，落 PR-08）
- 重点是「给下一位的交接」那一段——让接手的人无缝继续
- 关键决策记 worklog 「关键决策」段；上升到架构决策则收束时产 ADR

---

## 四、反模式

### ❌ README 有名无实

```
# AgentHub
A multi-agent collab platform.
Usage: See code.
```
✅ 30 秒内回答 5 问：做什么 / 怎么跑 / 有什么功能 / 技术栈 / 主要 API 在哪。

### ❌ 文档与代码 PR 分离

PR-A 改代码、PR-B 改文档 → 中间窗口文档/代码不一致，读者按文档跑错。
✅ 同 PR 一起改，diff 一同 review。

### ❌ 命名带版本后缀

`PRD_AgentHub_v3.md` / `架构设计_最新.md` / `API_final.md` → 5 个月后有 8 个版本，没人知道哪个是真。
✅ 现行文件保持稳定名；历史版本归 `docs/archive/DEPRECATED_<原名>_v3.md`。`check_docs.py` 自动拦截 D-09。

### ❌ docs/ 根混入 .html

PRD 写完导出 PRD.html 放 docs/ 根 → 与 md 源争权威。
✅ md 是源，html 渲染产物归 `docs/reports/`。`check_docs.py` 自动拦截 D-10。

### ❌ ADR 直接写在 docs/explore/

`docs/explore/ADR-XX-foo.md` → 与新位置 `worklogs/decisions/` 冲突。
✅ 新 ADR 一律放 `worklogs/decisions/NNNN-<slug>.md`；历史 ADR 待迁移时一并移过去。

### ❌ 注释与代码不符

`"""通过 agent_id 查询"""` 但实际 `def find_by_name(name)` → 比没注释更危险。
✅ 改代码同步改注释，参数名 / 字段名 / 行为描述三者一致。

---

## 五、检查清单

- [ ] **D-01** 根 README.md + CLAUDE.md 存在，含快速开始
- [ ] **D-02** 文档与代码同 PR
- [ ] **D-03** 公共 API 有 docstring
- [ ] **D-04** 注释与代码一致
- [ ] **D-05** docs/ 根新文件命名 `{English}_{中文}.md`
- [ ] **D-06** explore/ 子项命名规范
- [ ] **D-07** archive/ 有 `DEPRECATED_` 前缀
- [ ] **D-08** worklog 命名 `YYYY-MM-DD_*.md`
- [ ] **D-09** 无版本后缀文件
- [ ] **D-10** docs/ 树无 .html（reports/ 例外）
- [ ] **D-11** CLAUDE.md 所有 `` `xxx.md` `` 引用可解析
- [ ] **D-12** pre-commit + pre-push 钩子已装
- [ ] `scripts/check_docs.py` 通过
- [ ] 文档间双向链接（设计 ↔ BDD ↔ 规范）
- [ ] 复杂功能（≥ 3 模块）有五段设计文档

---

## 六、关联

| 方向 | 链接 |
|------|------|
| 细化自 | [§2.5 更新记录](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) · [07-汇报](ai-workflow_AI协作开发流程/07-汇报.md) |
| 模板权威 | [docs/templates/README-模板索引.md](../docs/templates/README-模板索引.md) |
| 文件归类权威 | [meta/FILE_GRAPH.md](../meta/FILE_GRAPH.md) |
| 文档自动校验脚本 | `scripts/check_docs.py` |
| ADR 时机 | [第三步·收束节点](ai-workflow_AI协作开发流程/06-第三步_收束节点.md) |
| 代码地图 / 知识图谱 | [08-代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md) |
| Skill: 文档同步 | `skills/doc-sync/` |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-28 | v3.0 | 按模板骨架重写；红线 D-01~D-12 全部对齐 `check_docs.py` 实测规则；新增 explore EXP/个人子目录约定、ADR 新位置 `worklogs/decisions/`、版本后缀禁令 |
