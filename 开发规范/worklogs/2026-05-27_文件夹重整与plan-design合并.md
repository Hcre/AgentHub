# 工作日志：文件夹重整 + plan/design 合并

> 日期: 2026-05-27
> 功能点: #27 文件夹重整 + #28 plan/design 合并
> 关联 BDD: docs/specs/10-templates-reporting.md

## 做了什么

### #27 文件夹重整 — 提取隐藏模板 + 补齐AI模板 + 消除重叠

**提取埋藏模板**（从 `06-第三步_收束节点.md`）:
- `AI审计报告模板.md` — AI 全量代码扫描报告
- `人审计签核模板.md` — 人工审计签核
- `收束报告模板.md` — 四阶段收束整合报告（含整理/测试/审计/验证子模板）
- 原文模板代码块替换为 `> 模板文件：docs/templates/{X}.md` 引用，节省 ~1182 字符

**增强汇报模板**:
- 汇报模板 三档→四档（+收束报告档位）
- 新增"AI 填写指引"（哪些段 AI 自动填充、哪些人工确认）

**新建 AI 使用模板**（2 个）:
- `AI协作提示词模板.md` — 四步开发标准提示词（调研/计划/开发/回顾 + 收束节点）
- `AI会话启动模板.md` — 新会话初始化清单（三层读取 + 状态恢复检查 + 角色切换）

**清理根目录**:
- `start_server.py` + `打开仪表盘.bat` → `scripts/`
- 修正 `start_server.py` 根目录指向（`os.path.dirname` ×2）

**消除重叠**（3 处）:
- `01-角色分工` 中的重复目录树 → 替换为引用表格
- `06-第三步` 缺陷检测表 → 改为引用 08 规范 §3.3
- `specs/10-templates-reporting` → 精简为验收场景，覆盖新增模板

**更新索引**（4 个文件）:
- `docs/templates/README.md` — +5 模板登记
- `meta/FILE_GRAPH.md` — +scripts/ 节点 + 新模板 + 决策树更新
- `CLAUDE.md` — 目录结构更新
- `README.md` — dashboard 路径修正

### #28 合并 plan/ + design/ → docs/plan/

- `plan/`（根目录）→ `docs/plan/`
- `docs/design/` → `docs/plan/design/`
- 同步更新 FILE_GRAPH.md、CLAUDE.md、README.md、STATUS.md、开发清单 中所有路径引用

## 验证结果

- 模板总数: 9 → 14（+5 个）
- 根目录文件: 7 → 5（-2 个脚本文件，移入 scripts/）
- `docs/templates/README.md` 索引覆盖全部 14 个模板 ✅
- `06-第三步_收束节点.md` 模板引用可追溯 ✅
- `start_server.py` 在 scripts/ 下可正常启动 ✅
- FILE_GRAPH / CLAUDE / README / STATUS / 开发清单 全部路径一致 ✅

## 变更影响

- 涉及文件: 14 个（3 新建模板 + 2 新建 AI 模板 + 2 移动脚本 + 7 编辑）
- `start_server.py` 路径变更不影响功能（`os.path.dirname` ×2 回到项目根）
- `打开仪表盘.bat` 使用 `%~dp0`，同目录内调用不受影响
- 新项目模板复制命令已更新（README.md）

## 给下一位的交接

> 本次重整后，`docs/` 成为所有非规范正文的唯一归宿。新增文件时参考 `meta/FILE_GRAPH.md` 决策树——plan 和 design 现在都在 `docs/plan/` 下。
