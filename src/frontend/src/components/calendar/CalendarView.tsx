import { useState } from 'react'
import { cn } from '../../lib/cn'
import {
  addDays,
  addMonths,
  DOW_ABBR,
  fmtDate,
  MONTH_NAMES,
  parseDate,
  startOfWeek,
} from '../../lib/date'
import { calendarEvents, TODAY_STR } from '../../data/extra'
import { Button, Icon, Tabs, TabsList, TabsTrigger } from '../ui'
import type { CalendarEvent } from '../../types'

type View = 'month' | 'week' | 'day'
const HOURS = Array.from({ length: 12 }, (_, i) => i + 1) // 1..12，每格 56px

const ROW = 56
const toneCls = (tone: CalendarEvent['tone']) =>
  tone === 'brand'
    ? 'bg-brand/10 border-brand text-brand'
    : 'bg-emerald-500/10 border-emerald-500 text-emerald-700 dark:text-emerald-300'

function eventsOn(date: string) {
  return calendarEvents.filter((e) => e.date === date)
}

function DayColumn({ date }: { date: string }) {
  return (
    <div className="relative border-r last:border-r-0">
      {HOURS.map((h) => (
        <div key={h} className="h-[56px] border-b transition-colors hover:bg-accent/30" />
      ))}
      {eventsOn(date).map((e) => (
        <div
          key={e.id}
          className={cn('absolute left-1 right-1 rounded-md border-l-2 px-2 py-1', toneCls(e.tone))}
          style={{ top: (e.startHour - 1) * ROW, height: (e.endHour - e.startHour) * ROW - 4 }}
        >
          <div className="text-[12px] font-medium leading-tight">{e.title}</div>
          <div className="font-mono text-[10px] opacity-75">
            {e.startHour}:00 — {e.endHour}:00
          </div>
        </div>
      ))}
    </div>
  )
}

export function CalendarView() {
  const [cursor, setCursor] = useState(TODAY_STR)
  const [view, setView] = useState<View>('week')

  const navPrev = () =>
    setCursor(view === 'month' ? addMonths(cursor, -1) : addDays(cursor, view === 'week' ? -7 : -1))
  const navNext = () =>
    setCursor(view === 'month' ? addMonths(cursor, 1) : addDays(cursor, view === 'week' ? 7 : 1))

  let rangeLabel: string
  if (view === 'month') {
    const d = parseDate(cursor)
    rangeLabel = `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`
  } else if (view === 'week') {
    const s = parseDate(startOfWeek(cursor))
    const e = new Date(s)
    e.setDate(s.getDate() + 6)
    rangeLabel = `${MONTH_NAMES[s.getMonth()]} ${s.getDate()} – ${MONTH_NAMES[e.getMonth()]} ${e.getDate()}, ${e.getFullYear()}`
  } else {
    const d = parseDate(cursor)
    rangeLabel = `${MONTH_NAMES[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
  }

  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(cursor), i))
  const monthStart = (() => {
    const d = parseDate(cursor)
    d.setDate(1)
    return startOfWeek(fmtDate(d))
  })()
  const monthCells = Array.from({ length: 42 }, (_, i) => addDays(monthStart, i))
  const cursorMonth = parseDate(cursor).getMonth()

  return (
    <div className="flex h-full flex-col gap-4 px-6 py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant={cursor === TODAY_STR ? 'brand' : 'outline'}
            size="sm"
            onClick={() => setCursor(TODAY_STR)}
          >
            今天
          </Button>
          <Button variant="ghost" size="iconSm" onClick={navPrev}>
            <Icon name="chevronLeft" className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="iconSm" onClick={navNext}>
            <Icon name="chevronRight" className="h-3.5 w-3.5" />
          </Button>
          <span className="ml-1 text-[14px] font-medium">{rangeLabel}</span>
        </div>
        <Tabs value={view} onValueChange={(v) => setView(v as View)}>
          <TabsList className="h-8">
            <TabsTrigger value="month" className="h-6 px-3 text-[12px]">
              月
            </TabsTrigger>
            <TabsTrigger value="week" className="h-6 px-3 text-[12px]">
              周
            </TabsTrigger>
            <TabsTrigger value="day" className="h-6 px-3 text-[12px]">
              日
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden rounded-xl border bg-card">
        {view === 'month' && (
          <div className="grid h-full grid-rows-[auto_1fr]">
            <div className="grid grid-cols-7 border-b bg-muted/30">
              {DOW_ABBR.map((d) => (
                <div
                  key={d}
                  className="px-2 py-1.5 text-center font-mono text-[10px] uppercase tracking-wider text-muted-foreground"
                >
                  {d}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 grid-rows-6">
              {monthCells.map((ds) => {
                const d = parseDate(ds)
                const isMonth = d.getMonth() === cursorMonth
                const isToday = ds === TODAY_STR
                const evs = eventsOn(ds)
                return (
                  <div
                    key={ds}
                    className={cn(
                      'flex flex-col gap-1 border-b border-r px-2 py-1.5 last:border-r-0',
                      !isMonth && 'bg-muted/20 text-muted-foreground/60',
                    )}
                  >
                    <div
                      className={cn(
                        'font-mono text-[11px]',
                        isToday &&
                          'grid h-5 w-5 place-items-center rounded-full bg-brand font-semibold text-brand-foreground',
                      )}
                    >
                      {d.getDate()}
                    </div>
                    <div className="space-y-0.5">
                      {evs.slice(0, 3).map((e) => (
                        <div
                          key={e.id}
                          className={cn(
                            'truncate rounded px-1.5 py-0.5 text-[10px]',
                            e.tone === 'brand'
                              ? 'bg-brand/10 text-brand'
                              : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
                          )}
                        >
                          {e.title}
                        </div>
                      ))}
                      {evs.length > 3 && (
                        <div className="px-1 font-mono text-[10px] text-muted-foreground">
                          +{evs.length - 3} more
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {view !== 'month' && (
          <div
            className="grid h-full"
            style={{
              gridTemplateColumns: `60px repeat(${view === 'week' ? 7 : 1}, 1fr)`,
              gridTemplateRows: '56px 1fr',
            }}
          >
            {/* 角 */}
            <div className="flex items-center justify-center border-b border-r">
              <span className="font-mono text-[10.5px] text-muted-foreground">GMT+8</span>
            </div>
            {/* 日期表头 */}
            {(view === 'week' ? weekDays : [cursor]).map((ds) => {
              const d = parseDate(ds)
              const isToday = ds === TODAY_STR
              return (
                <div
                  key={ds}
                  className={cn(
                    'flex flex-col items-center justify-center gap-0.5 border-b',
                    view === 'week' && 'border-r',
                    isToday && 'bg-muted/30',
                  )}
                >
                  <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {DOW_ABBR[d.getDay()]}
                  </div>
                  {isToday ? (
                    <div className="grid h-7 w-7 place-items-center rounded-full bg-brand text-[14px] font-semibold text-brand-foreground">
                      {d.getDate()}
                    </div>
                  ) : (
                    <div className="text-[16px] font-semibold tracking-tight">{d.getDate()}</div>
                  )}
                </div>
              )
            })}
            {/* 时间列 */}
            <div className="overflow-y-auto border-r">
              {HOURS.map((h) => (
                <div
                  key={h}
                  className="flex h-[56px] items-start justify-center border-b pt-1 font-mono text-[10.5px] text-muted-foreground"
                >
                  {h} {h < 12 ? 'AM' : 'PM'}
                </div>
              ))}
            </div>
            {/* 天列 */}
            <div
              className="overflow-y-auto"
              style={{ gridColumn: `2 / span ${view === 'week' ? 7 : 1}` }}
            >
              <div
                className="grid h-full"
                style={{ gridTemplateColumns: `repeat(${view === 'week' ? 7 : 1}, 1fr)` }}
              >
                {(view === 'week' ? weekDays : [cursor]).map((ds) => (
                  <DayColumn key={ds} date={ds} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
