# 实施计划：Agent 模板 Skill 绑定 + 自定义角色弹窗

> 日期：2026-05-25 | 分支：feature/domain2/custom-agent-skill

## 目标

- 预设模板自带 skill 组合，用户不可见
- 自定义角色弹出新窗口，填名称 + 职责 + 自选 skill
- 确认后回到 Step 2 配置 Key

## 实施步骤

### 1. 模板加 skills
`CreateAgentModal.tsx` TEMPLATES 数组每项加 `skills: string[]`

### 2. 后端技能列表
`GET /api/skills/library` → 读 `/skills/` 目录返回文件名列表

### 3. CustomAgentModal 组件
新建弹窗：名称 + 职责 + Skill checkbox + 确认回调

### 4. 集成
Step 1 点"自定义" → CustomAgentModal → 确认后回到 Step 2

## 文件

| 文件 | 操作 |
|------|------|
| `CreateAgentModal.tsx` | 修改 |
| `CustomAgentModal.tsx` | 新建 |
| `src/backend/app/api/routers/skills.py` | 新建 |
