import type { AccentId, Density, HeadingFont, Theme } from '../stores/uiStore'

export interface AccentDef {
  id: AccentId
  label: string
  hex: string
  brand: string // HSL 三元组（不含 hsl()）
  deep: string
  soft: string
}

export const ACCENTS: AccentDef[] = [
  {
    id: 'coral',
    label: '珊瑚',
    hex: '#c96342',
    brand: '17 56% 53%',
    deep: '16 60% 33%',
    soft: '22 60% 91%',
  },
  {
    id: 'blue',
    label: '靛蓝',
    hex: '#4a6fa5',
    brand: '214 38% 47%',
    deep: '214 50% 30%',
    soft: '214 50% 92%',
  },
  {
    id: 'sage',
    label: '鼠尾草',
    hex: '#5f7a68',
    brand: '143 13% 43%',
    deep: '143 20% 26%',
    soft: '143 25% 91%',
  },
  {
    id: 'plum',
    label: '梅',
    hex: '#7d4f6e',
    brand: '322 22% 40%',
    deep: '322 30% 26%',
    soft: '322 30% 92%',
  },
]

const HEAD_FONT_STACK: Record<HeadingFont, string> = {
  Geist: '"Geist", ui-sans-serif, system-ui, sans-serif',
  'Source Serif 4': '"Source Serif 4", "Tiempos Headline", Georgia, serif',
  'Instrument Serif': '"Instrument Serif", Georgia, serif',
  'IBM Plex Sans': '"IBM Plex Sans", ui-sans-serif, sans-serif',
}

/** 把 tweak 设置写到 <html>：主题 class、accent CSS 变量、密度、标题字体。 */
export function applyTweaks(opts: {
  theme: Theme
  accent: AccentId
  density: Density
  headingFont: HeadingFont
}): void {
  const root = document.documentElement
  root.classList.toggle('dark', opts.theme === 'dark')
  root.classList.toggle('dim', opts.theme === 'dim')
  root.dataset.density = opts.density

  const accent = ACCENTS.find((a) => a.id === opts.accent) ?? ACCENTS[0]!
  root.style.setProperty('--brand', accent.brand)
  root.style.setProperty('--brand-deep', accent.deep)
  root.style.setProperty('--brand-soft', accent.soft)
  root.style.setProperty('--ring', accent.brand)
  root.style.setProperty('--ah-head-font', HEAD_FONT_STACK[opts.headingFont])
}
