import type { IconName } from '../../types'

/** 4 种预览模式（tab / 全屏选择器共用）。 */
export type PreviewMode = 'files' | 'diff' | 'deploy' | 'webpage'

export interface PreviewModeDef {
  mode: PreviewMode
  icon: IconName
  title: string
  desc: string
  shortcut?: string
  enabled: boolean
  hint?: string
}

/** 4 种预览模式的单一源（4 卡片大图 / TabBar 下拉共用）。 */
export const PREVIEW_MODES: PreviewModeDef[] = [
  { mode: 'files', icon: 'files', title: '项目文件', desc: '浏览项目文件', shortcut: 'Ctrl+P', enabled: true },
  { mode: 'diff', icon: 'diff', title: '审查 diff', desc: '对比代码变更', enabled: false, hint: '即将到来' },
  { mode: 'deploy', icon: 'rocket', title: '部署', desc: '发布到生产环境', enabled: false, hint: '即将到来' },
  { mode: 'webpage', icon: 'globe', title: '网页', desc: '打开网页', enabled: true },
]
