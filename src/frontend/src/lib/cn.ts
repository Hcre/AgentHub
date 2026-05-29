/** 拼接 className，过滤 falsy 值。轻量替代 clsx。 */
export function cn(...args: Array<string | false | null | undefined>): string {
  return args.filter(Boolean).join(' ')
}
