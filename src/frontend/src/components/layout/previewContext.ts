import { useChatStore } from '../../stores/chatStore'
import { useGroupStore } from '../../stores/groupStore'
import { useUIStore } from '../../stores/uiStore'

/** 按当前 section 推断预览工作目录（带兜底）
 *  - section=chat → 当前 conversation.workdir（私聊）
 *  - section=group → 当前 group.workdir
 *  - 都没拿到 → uiStore.fileWorkdir（用户在文件面板里手动设的全局兜底）
 *  - 都没有 → undefined（预览面板显示"未设置"）
 */
export function useCurrentWorkdir(): string | undefined {
  const section = useUIStore((s) => s.section)
  const activeConversationId = useUIStore((s) => s.activeConversationId)
  const activeAgentId = useUIStore((s) => s.activeAgentId)
  const activeGroupId = useUIStore((s) => s.activeGroupId)
  const fileWorkdir = useUIStore((s) => s.fileWorkdir)

  if (section === 'chat' && activeAgentId && activeConversationId) {
    const convs = useChatStore.getState().conversations[activeAgentId] ?? []
    const convWd = convs.find((c) => c.id === activeConversationId)?.workdir
    if (convWd) return convWd
  } else if (section === 'group' && activeGroupId) {
    const g = useGroupStore.getState().groups.find((g) => g.id === activeGroupId)
    if (g?.workdir) return g.workdir
  }
  return fileWorkdir ?? undefined
}
