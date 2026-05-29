# 工作日志：dashboard 集成人向文档 + 图谱 + CODE_MAP 迁移 docs/

- **谁**: 袁
- **日期**: 2026-05-29
- **分支**: main（与近几次提交一致；改动为文档/可视化，非业务域）
- **关联 Spec**: `docs/conventions/08-code-understanding_*`（CODE_MAP 归属）、`docs/conventions/06-documentation_*`

## 目标
把「给人看」的文档与代码图谱集成进 `dashboard.html`，并将 `CODE_MAP.md` 收归 `docs/`，让人类阅读更友好。

## 产出
- [x] `dashboard.html` 三 Tab：📊 看板（原逻辑）/ 📖 文档 / 🗺️ 图谱
  - 文档 Tab：实时 fetch + 内置 mini-markdown 渲染（无外部依赖）5 个人向文档；新增**目录 TOC 侧栏**（h2/h3 自动锚点 + 平滑滚动）；`mermaid` 代码块转为「见图谱」提示而非原始文本
  - 图谱 Tab：内嵌 `.understand-anything/graph.html`（生成产物，未入 git），缺失时提示先跑 `gen_codegraph.py`
- [x] `CODE_MAP.md` → `docs/CODE_MAP.md`（`git mv`）
- [x] 同步引用：`scripts/gen_codegraph.py`（写出路径 + docstring + 日志）、`CLAUDE.md`、`README.md`、`meta/FILE_GRAPH.md`、`.gitignore` 注释
- [x] 验证：
  - Node 抽出实际渲染器跑 5 文档 — 0 哨兵泄漏、TOC 锚点数与目录一致、CODE_MAP 的 Mermaid 块=1 个图谱提示
  - `python scripts/gen_codegraph.py` 重新生成 `docs/CODE_MAP.md`（83 模块/130 类/306 函数/646 边）+ `graph.html`
  - HTTP 实测 dashboard / docs/CODE_MAP.md / graph.html / README 全 200

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| 图谱用 iframe 内嵌而非内联 | graph.html 是完整 HTML 文档，且为 gitignore 生成产物 | 本地/服务环境直接可看；克隆后需先 `gen_codegraph.py` 重建 |
| Mermaid 块转「见图谱」提示，不引入 mermaid.js | 保持无外部依赖（延续去 CDN 方向）；交互图已由图谱 Tab 提供 | dashboard 内 CODE_MAP 不渲染 Mermaid 原图，引导到图谱 Tab |
| 占位哨兵用私有区字符 `/` | NUL 放进 `new RegExp` 不可靠（实测泄漏） | 行内代码/转义管道还原稳定 |
| CODE_MAP 落 `docs/` | conventions/08 允许「根或 docs/」，与文档归集一致 | 写出路径、引用全部跟随 |

## 未完成 / 阻塞
- [ ] 无。`graph.html` 为生成产物未入 git，dashboard 图谱 Tab 依赖本地已生成。

## 给下一位的交接
> dashboard 现为单文件三 Tab 协作中心：`python scripts/start_server.py` → 浏览器。改后端结构后跑 `python scripts/gen_codegraph.py` 会同时刷新 `docs/CODE_MAP.md` 与图谱。内置 markdown 渲染器在 `dashboard.html` 的 `mdToHtml/inline/buildToc`，新增语法在那里扩展。
