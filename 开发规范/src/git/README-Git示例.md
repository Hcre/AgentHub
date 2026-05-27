# Git + 文档示例

> **👤 人类参考** | 对应规范：`conventions/03-git_Git协作规范.md` 和 `conventions/06-documentation_文档规范.md`

## 示例列表

| 文件 | 对应规范 | 说明 |
|------|---------|------|
| `.gitignore` | 03 §二 | 标准 .gitignore 模板 |
| `.pre-commit-config.yaml` | 02 §二 + 03 §二 | pre-commit：ruff + ruff-format + gitleaks + commitlint |
| `commitlint.config.js` | 03 §一 红线2 | Conventional Commits 格式校验 |

> 安装：`pip install pre-commit && pre-commit install && pre-commit install --hook-type commit-msg`
