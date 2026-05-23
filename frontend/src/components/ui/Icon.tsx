import {
  Activity,
  Brain,
  Calendar,
  Check,
  ChevronDown,
  FileDiff,
  FileText,
  Files,
  Hash,
  Inbox,
  Info,
  ListChecks,
  MessageSquare,
  Moon,
  MoreHorizontal,
  PanelLeft,
  PanelRight,
  Plus,
  Search,
  Settings,
  Sparkles,
  Sun,
  type LucideIcon,
} from 'lucide-react'
import type { IconName } from '../../types'

const MAP: Record<IconName, LucideIcon> = {
  inbox: Inbox,
  listCheck: ListChecks,
  calendar: Calendar,
  chat: MessageSquare,
  activity: Activity,
  channels: Hash,
  files: Files,
  sparkle: Sparkles,
  brain: Brain,
  settings: Settings,
  search: Search,
  plus: Plus,
  chevronDown: ChevronDown,
  panelLeft: PanelLeft,
  panelRight: PanelRight,
  info: Info,
  moreHorizontal: MoreHorizontal,
  check: Check,
  diff: FileDiff,
  doc: FileText,
  sun: Sun,
  moon: Moon,
}

export interface IconProps {
  name: IconName
  className?: string
  size?: number
  strokeWidth?: number
}

/** 统一图标入口：按名取 lucide-react 图标，统一 strokeWidth/className 接口。 */
export function Icon({ name, className, size, strokeWidth = 1.75 }: IconProps) {
  const Cmp = MAP[name]
  return <Cmp className={className} size={size} strokeWidth={strokeWidth} />
}
