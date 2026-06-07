import { useState } from 'react'
import { Button, Icon } from '../ui'
import { CreateAgentModal } from '../agent/CreateAgentModal'

/**
 * Skill 设计师模板数据：pre-selected 到 CreateAgentModal，
 * 跳过 Step 1（选模板），直接进入 Step 2（配 CLI/Provider）。
 */
const SKILL_CREATOR_TEMPLATE = {
  name: 'Skill 设计师',
  systemPrompt: `你是一位 **Skill 设计师**，专门帮助用户设计和创建高质量、可复用的 Claude Code Skills。你通过多轮对话引导用户从模糊想法逐步打磨出完整、可发布的 Skill。

## Purpose
引导用户完成 Skill 创建的完整生命周期：需求梳理 → 元数据定义 → 指令编写 → 范例编写 → 多轮打磨 → 发布建议。

## Response Approach
多轮对话按以下阶段推进：
1. **需求梳理**：你的 Skill 解决什么问题？谁会用它，在什么场景下？
2. **元数据定义**：建议 kebab-case 名字、一句描述、触发关键词
3. **指令编写**：按 Purpose / Capabilities / Behavioral Traits / Response Approach / Constraints 编排
4. **范例编写**：基于真实场景写 2-3 个 INPUT → OUTPUT 范例
5. **评审与打磨**：对照检查清单逐项评审，最终输出完整 SKILL.md

## Constraints
- 不替用户决定 Skill 的领域/用途
- 每轮只聚焦 1 个维度，不贪多
- 所有输出需为 markdown 格式的 SKILL.md 片段

你的第一句话应该是：**你想创建什么类型的 skill？**`,
  skills: [],
  capabilityTags: ['skill-creation'],
  model: 'sonnet',
}

export function SkillCreationWizard({ onClose }: { onClose: () => void }) {
  const [started, setStarted] = useState(false)

  // 用户点击「开始」→ 打开 CreateAgentModal，预填 Skill 设计师模板
  if (started) {
    return (
      <CreateAgentModal
        open
        onClose={() => {
          setStarted(false)
          onClose()
        }}
        preSelectedTemplate={SKILL_CREATOR_TEMPLATE}
      />
    )
  }

  // 确认界面：说明 AI 引导创建流程
  return (
    <div className="flex flex-col items-center gap-5 px-6 py-10">
      <div className="grid h-14 w-14 place-items-center rounded-full bg-brand/10 text-brand">
        <Icon name="sparkle" className="h-7 w-7" />
      </div>

      <div className="text-center">
        <h3 className="text-[16px] font-semibold">AI 助手引导创建 Skill</h3>
        <p className="mt-2.5 text-[13px] text-muted-foreground max-w-[300px] leading-relaxed">
          将为你创建一个 Skill 设计师 Agent，通过多轮对话引导你完成 Skill
          的需求梳理、元数据定义、指令编写和范例创作。
        </p>
        <p className="mt-1.5 text-[12px] text-muted-foreground/70">
          AI 助手会逐步提问，把你模糊的想法打磨成完整的 SKILL.md
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onClose}>
          取消
        </Button>
        <Button variant="brand" size="sm" onClick={() => setStarted(true)}>
          <Icon name="sparkle" className="h-3.5 w-3.5" />
          开始
        </Button>
      </div>
    </div>
  )
}
