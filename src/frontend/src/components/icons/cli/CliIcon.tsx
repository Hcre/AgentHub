import ClaudeSvg from './claudecode-color.svg'
import OpenCodeSvg from './opencode.svg'
import PiSvg from './pi-coding-agent.svg'
import CodexSvg from './codex-color.svg'
import MockSvg from './mock.svg'
import { CLI_LABEL } from './cliLabels'

/** 5 个 CLI 系统 → 自包含 SVG（用户提供的品牌资源，普通 URL 导入） */
const SRC_MAP: Record<string, string> = {
  claude_code: ClaudeSvg,
  pi_agent: PiSvg,
  opencode: OpenCodeSvg,
  codex: CodexSvg,
  mock: MockSvg,
}

export interface CliIconProps {
  /** CLI 系统 id（来自 ApiAgent.agent_system / store）；未知值回退到 mock 图标 */
  agentSystem?: string
  /** 显示大小（宽高），默认 12 */
  size?: number
  className?: string
}

/** 渲染 CLI 品牌图标。未匹配时用 mock 图标兜底。
 *  注：用 <img> 渲染（不用 ?react 导入，免去 vite-plugin-svgr 依赖）。
 *  品牌色直接来自 SVG 资源（不再 currentColor）。
 */
export function CliIcon({ agentSystem, size = 12, className }: CliIconProps) {
  const src = SRC_MAP[agentSystem ?? ''] ?? MockSvg
  return (
    <img
      src={src}
      width={size}
      height={size}
      alt={CLI_LABEL[agentSystem ?? ''] ?? 'Mock'}
      className={className}
      draggable={false}
    />
  )
}
