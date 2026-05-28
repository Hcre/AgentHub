# BDD 规格: 示例代码库

> 对应 `src/` 目录

---

## 功能：示例代码库

### 场景 1：每个规范维度有对应的代码示例

- 前置条件：7 份规范文档（01-06 + AI 协作流程）已完成
- 操作步骤：
  1. 进入 `src/` 目录
  2. 查看各子目录
- 预期结果：
  - `src/architecture/` — 分层架构示例（表现层/应用层/领域层/基础设施层）
  - `src/coding/` — 命名、错误处理、安全编码示例
  - `src/git/` — .gitignore、pre-commit hook 示例
  - `src/api/` — RESTful API 完整示例（含统一响应格式、错误码）
  - `src/testing/` — 单元测试 + Mock 示例
  - `src/documentation/` — 文档模板示例（README/CHANGELOG/docstring）
  - `src/code-understanding/` — 代码知识图谱构建示例（调用图抽取 + 图 schema + Cypher 查询模板 + CI 门禁）

### 场景 2：代码可运行可验证

- 前置条件：开发者 clone 后
- 操作步骤：
  1. 进入任一示例子目录
  2. 按 README 安装依赖并运行
- 预期结果：
  - 每个示例目录有独立的 `README-<维度>示例.md`（说明依赖、运行方式、对应规范章节）
  - 代码通过 lint 检查
  - 测试可运行通过

### 场景 3：单一参考语言 + 规范覆盖语言差异

- 前置条件：规范文档本身语言无关
- 操作步骤：
  1. 查看各示例目录
- 预期结果：
  - 示例统一以 **Python** 为参考实现，降低维护成本（无需为每个示例维护多语言镜像）
  - 跨语言差异点（如命名 snake_case vs camelCase）在规范正文中说明，示例不重复实现
  - 每个示例目录的 `README-<维度>示例.md` 注明对应的规范章节
