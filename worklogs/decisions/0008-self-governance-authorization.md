# 0008 用户授权 owner 全权自主决策（plan_bc385bbe 期间）

- **日期**: 2026-06-06 23:17 (Asia/Shanghai)
- **授权方**: 用户 (id: mvs_715760f5649343da8eff29e13ce8f29c)
- **生效范围**: plan_bc385bbe「明早验收冲刺：核心 P0 + Demo 视频 + 飞书文档」运行期间
- **失效时机**: 用户明早到岗并接管（届时口头/打字宣布恢复 PR-01 模式）

## 授权边界

- ✅ owner 可自主做判断：verifier FAIL retry、范围微调、worker steer、降级方案、P0 子任务边界调整、临时改 plan 内的 prompt
- ✅ owner 可创建临时文件、worklog、scratchpad 笔记
- ✅ owner 可 git commit / git push（按 PR-07 流程，但**不**做 merge 决策）
- ❌ **不可删除用户文件**（除 `.mavis/`/`.harness/`/`build/`/`node_modules/` 等已 gitignored 的产物；其他需先备份再删）
- ⚠️ 不可对 main 做 force push、reset --hard、rebase --interactive 等改历史操作

## 记录义务

- 每个**重大决定**（影响 plan 范围 / 推翻原 prompt / 改 ver 口径 / 跳过任务）必须落 `worklogs/decisions/0009+NNN-<slug>.md`
- 单次「retry / steer / 改 prompt 文案」级别的小决定**不需要** ADR，在 cycle decision 的 reason 里说清即可
- plan 完成后，owner 写一个 `00NN-plan-summary.md` 汇总所有重大决定 + 最终交付物清单

## 上下文管理（用户特别提醒）

- 用户担心**上下文过长导致中断**，要求 owner 自我克制
- 规则：
  - 收到 engine signal → 优先 (c) `<mavis-thinking>`，只在 milestone 用 (a) alert
  - cron 触发 → silently 处理；只在 critical 决策点 alert
  - **不**主动更新 STATUS（除非 critical 改动）
  - **不**主动写 worklog（除非用户明早要看的关键节点）
  - 大块工作记录 → 委派给 worker 写 deliverable.md / 临时文件
- 兜底：cron `mvp-acceptance-watch` 30 min tick；TTL 14d

## 给明早（2026-06-07 上午）的用户

明早到岗后，**第一件事**：让我（owner）输出一份「昨夜交付清单 + 我做了什么决定」摘要。
然后我们一起看：
- plan 状态 + 视频成片
- STATUS.md（保持 6/06 22:45 版本；中间不更新以省上下文）
- 任何 0009+ ADR（如果有的话）
- 视频 + 文档 + Demo 数据集

如果 plan 还没跑完，我们决定是再等还是接管。
