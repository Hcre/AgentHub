// 轻量日期工具（日历用）。字符串格式统一 YYYY-MM-DD。

export const MONTH_NAMES = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]
export const DOW_ABBR = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

export function parseDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1)
}

export function fmtDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function addDays(s: string, n: number): string {
  const d = parseDate(s)
  d.setDate(d.getDate() + n)
  return fmtDate(d)
}

export function addMonths(s: string, n: number): string {
  const d = parseDate(s)
  d.setMonth(d.getMonth() + n)
  return fmtDate(d)
}

export function startOfWeek(s: string): string {
  const d = parseDate(s)
  d.setDate(d.getDate() - d.getDay())
  return fmtDate(d)
}
