# 示例代码库 (src/)

> **👤 人类参考** — 演示"规范怎么落地成代码"。AI Agent 请读 `CLAUDE.md` 了解项目全貌。
> 对应 BDD 规格：`docs/specs/08-examples.md`

---

## ⚠️ 组织方式说明

本目录**按规范维度分目录**（每个规范一个文件夹），让示例与 `conventions/` 一一对应、便于查阅——**这不是推荐的产品代码结构**。

真实项目应按 `conventions/01-architecture_架构设计规范.md` 的建议组织：
- 业务复杂 → 按业务域分（`src/user/`、`src/order/`…）
- 项目简单 → 按技术层次分（`src/controllers/`、`src/services/`…）

`src/architecture/` 子目录内部演示的才是真实可用的分层结构。

---

## 目录索引

| 子目录 | 对应规范 | 演示内容 | 落地配置（规范 §二） |
|--------|---------|---------|------|
| `architecture/` | 01-架构设计 | 四层架构 + 依赖注入 | `importlinter.ini` |
| `coding/` | 02-代码编写 | 命名正反例、错误处理、安全 | `ruff.toml` |
| `git/` | 03-Git 协作 | .gitignore、提交流程 | `.pre-commit-config.yaml`（ruff+gitleaks+commitlint）|
| `api/` | 04-API 设计 | FastAPI：URL/响应/错误码/分页 | `.spectral.yaml` |
| `testing/` | 05-测试 | pytest：正常/边界/异常 + Mock | `pytest.ini`（覆盖率门禁）|
| `documentation/` | 06-文档 | CHANGELOG、docstring 示例 | （链 docs/templates/）|
| `code-understanding/` | 08-图谱 | 调用图构建、图 schema、Cypher、CI | `graph_schema.json` |

> 每个维度的"落地配置"与对应规范 §二「落地」的复制即用片段一致——示例即规范的可运行版本。

每个子目录内有独立的 `README-<维度>示例.md` 说明详细用法。

---

## 快速运行

```bash
# 架构示例
python -m src.architecture.main

# 测试示例
pytest src/testing/

# API 示例（需先 pip install fastapi uvicorn）
cd src/api && uvicorn main:app --reload

# 图谱示例（需先 pip install tree-sitter）
cd src/code-understanding && python call_graph_example.py .
```

> 语言统一用 Python（参考实现）。跨语言差异在规范正文中说明，示例不重复实现（见 `docs/specs/08-examples.md` 场景 3）。
