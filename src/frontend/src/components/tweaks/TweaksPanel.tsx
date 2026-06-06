import { useState } from 'react'
import { cn } from '../../lib/cn'
import { ACCENTS } from '../../lib/theme'
import { useUIStore, type Density, type HeadingFont, type Theme } from '../../stores/uiStore'
import { Icon } from '../ui'

const THEMES: { id: Theme; label: string }[] = [
  { id: 'light', label: '浅色' },
  { id: 'dim', label: '柔暗' },
  { id: 'dark', label: '深色' },
]
const DENSITIES: { id: Density; label: string }[] = [
  { id: 'comfort', label: '舒适' },
  { id: 'compact', label: '紧凑' },
]
const FONTS: HeadingFont[] = ['Source Serif 4', 'Geist', 'Instrument Serif', 'IBM Plex Sans']

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { id: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="flex rounded-lg bg-muted p-0.5">
      {options.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          data-active={value === o.id ? 'true' : undefined}
          className={cn(
            'flex-1 rounded-md px-2 py-1 text-[12px] text-muted-foreground transition-colors',
            'data-[active=true]:bg-background data-[active=true]:text-foreground data-[active=true]:shadow-sm',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      {children}
    </div>
  )
}

export function TweaksPanel() {
  const { theme, accent, density, headingFont, setTheme, setAccent, setDensity, setHeadingFont } =
    useUIStore()
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        title="外观调节"
        // 不再 fixed 到 viewport（会被右栏盖住）。改 absolute 到 AppShell 内部右下角，
        // 配合 z-50 永远在右栏之上。
        className="glass-strong absolute bottom-3 right-3 z-50 grid h-9 w-9 place-items-center rounded-full border text-muted-foreground shadow-lg transition-colors hover:text-foreground"
      >
        <Icon name="sliders" className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="animate-[var(--animate-slide-in)] glass-strong absolute bottom-14 right-3 z-50 w-64 rounded-2xl border p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[13px] font-semibold">外观</span>
            <button
              onClick={() => setOpen(false)}
              className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <Icon name="x" className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="space-y-4">
            <Row label="主题">
              <Segmented value={theme} options={THEMES} onChange={setTheme} />
            </Row>

            <Row label="强调色">
              <div className="flex gap-2">
                {ACCENTS.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => setAccent(a.id)}
                    title={a.label}
                    className={cn(
                      'h-7 w-7 rounded-full border-2 transition-transform hover:scale-110',
                      accent === a.id ? 'border-foreground' : 'border-transparent',
                    )}
                    style={{ background: a.hex }}
                  />
                ))}
              </div>
            </Row>

            <Row label="密度">
              <Segmented value={density} options={DENSITIES} onChange={setDensity} />
            </Row>

            <Row label="标题字体">
              <select
                value={headingFont}
                onChange={(e) => setHeadingFont(e.target.value as HeadingFont)}
                className="h-8 w-full rounded-md border border-input bg-transparent px-2 text-[12.5px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {FONTS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </Row>
          </div>
        </div>
      )}
    </>
  )
}
