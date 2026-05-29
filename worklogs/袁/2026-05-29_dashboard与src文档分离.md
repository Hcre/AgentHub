# 工作日志：dashboard 适配 + src 代码/内容分离

- **谁**: 袁
- **日期**: 2026-05-29
- **分支**: chore/align-with-conventions

## 目标

修两处：① dashboard.html 解析不出 AgentHub 的 STATUS.md（格式不匹配，全空）；② src/frontend 代码与文档混杂，不符合规范。

## 产出

### dashboard.html 重写
- **根因**：dashboard 来自模板，期望 `## 进度` 功能点表（done/active + BDD 链接）；但 AgentHub 的 STATUS.md 是「我｜正在做｜阻塞？｜这周完成了」按人协作表 → 解析出 0 功能点 → 看板全空。
- **修法**：保留 CSS 皮肤，重写 parse + render：
  - 解析按人协作表 + `## Git ↔ 目录映射`
  - 渲染按人看板卡（正在做 / 阻塞红条 / 本周完成 ✅ 清单 + Git 用户名）
  - 汇总改为「本周完成 N 项 · M 人 · 阻塞数」，chips 筛选：全部 / 进行中 / 有阻塞
  - Git 映射独立表
  - 不动 STATUS.md（check_worklog 依赖其现格式）
- 验证：模拟 parse 跑通——更新日期、3 成员（黎/董/袁）、Git 映射 3 条全部正确解析

### src/frontend 代码/内容分离
前端目录原混入 6 个文档，外迁后只留代码 + README：
| 原 | 新 |
|---|---|
| src/frontend/HANDOFF.md | docs/plan/前端HANDOFF_前端交接说明.md |
| src/frontend/项目交接总文档.md | docs/plan/项目交接总文档.md |
| src/frontend/docs/前端Phase0_转换方案.md | docs/plan/前端Phase0_转换方案.md |
| src/frontend/docs/前端实施计划_v1.md | docs/archive/DEPRECATED_前端实施计划_v1.md（被 docs/plan/前端实施计划.md 取代）|
| src/frontend/问题/2026-05-23_Phase{0,1}-*.md | docs/explore/袁/（前端设计问题，带日期前缀）|

- 删空 src/frontend/{docs,问题}
- 无文件引用旧路径（移动不破坏引用）；迁移文件无相对链接（无断链）
- 同步 meta/FILE_GRAPH.md 前端节点描述

### docs/ 结构核查
- `docs/design/image.png`：被 group-creation 设计文档内联引用、同目录合规设计资产 → 保留
- `docs/design/group-creation_实现文档.md`：命名与同目录 `<feature>_<中文>` 一致 → 保留
- 结论：docs/ 主体合规，核心缺陷（前端文档散在 src）已由上面外迁解决

## 给下一位的交接

> dashboard 现在解析按人协作表，改 STATUS.md 表结构需同步改 dashboard.html 的 parse()。
> 前端目录铁律：src/frontend 只放代码 + README，文档一律进 docs/。
> 看 dashboard：`python scripts/start_server.py` → 浏览器开 http://localhost:8000/dashboard.html（需 HTTP 服务，不能 file:// 直开）。
