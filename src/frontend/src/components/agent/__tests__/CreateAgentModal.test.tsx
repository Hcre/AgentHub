import { describe, it, expect } from 'vitest'
import { classifyCreateAgentError } from '../CreateAgentModal'

/**
 * BDD B-4-P2-AG01（Day 2 t2-createagent-502）— CreateAgentModal 错误分类
 *
 * 用户截图：后端 502 时看到「API 502: <html><body>nginx/1.x 502 Bad
 * Gateway...</body></html>」，无 actionable 提示。
 *
 * 验收点（来自 docs/specs/04-commands §6.4.6）：
 *   When-1 5xx → 「后端服务未启动或网络不通」 + 隐藏 nginx HTML
 *   When-2 4xx → 保留 detail（用户需要看到「API key 无效」之类的具体反馈）
 *   When-3 网络（fetch TypeError）→ 「网络连接失败 — 请检查网络」
 *   Then-? 文案长度 < 200（防止 detail 巨长撑爆 UI）
 *   Then-? 任何未知/非 Error 输入 → 优雅兜底，不抛
 *
 * 5 个 it：5xx / 4xx / 网络 / 长度 / 兜底。
 */
describe('CreateAgentModal error classification (B-4-P2-AG01)', () => {
  it('5xx (502/503/504): returns "后端服务未启动或网络不通" and hides nginx HTML', () => {
    // 用户截图原貌：API 502: <html>...nginx/1.x 502 Bad Gateway...</html>
    const err502 = new Error(
      'API 502: <html><body><h1>502 Bad Gateway</h1>' +
        '<p>nginx/1.27.0</p></body></html>',
    )
    const msg = classifyCreateAgentError(err502)
    expect(msg).toContain('后端服务未启动或网络不通')
    // 关键：原始 nginx HTML 必须被隐藏
    expect(msg).not.toContain('nginx')
    expect(msg).not.toContain('<html')
    expect(msg).not.toContain('502 Bad Gateway')

    // 503 / 504 同路径
    expect(classifyCreateAgentError(new Error('API 503: Service Unavailable'))).toContain(
      '后端服务未启动或网络不通',
    )
    expect(classifyCreateAgentError(new Error('API 504: Gateway Timeout'))).toContain(
      '后端服务未启动或网络不通',
    )
  })

  it('4xx (400/401/403/422): preserves original detail (e.g. "API key 无效")', () => {
    const cases: Array<[string, string]> = [
      ['API 400: 缺少必填字段 name', '缺少必填字段 name'],
      ['API 401: API key 无效', 'API key 无效'],
      ['API 403: 没有权限', '没有权限'],
      ['API 422: model 不存在', 'model 不存在'],
    ]
    for (const [raw, expectedFragment] of cases) {
      const msg = classifyCreateAgentError(new Error(raw))
      // 用户需要看到原始 detail（剥掉 "API NNN: " 前缀）
      expect(msg, `case: ${raw}`).toContain(expectedFragment)
      // 不应包含 status code 前缀（避免泄漏技术细节给最终用户）
      expect(msg).not.toMatch(/^API \d/)
    }
  })

  it('network error (TypeError from fetch): returns "网络连接失败"', () => {
    // fetch 失败（断网/CORS/上游拒连）→ TypeError: Failed to fetch
    const cases = [
      new TypeError('Failed to fetch'),
      new TypeError('NetworkError when attempting to fetch resource'),
      new Error('fetch failed'),
      new Error('net::ERR_CONNECTION_REFUSED'),
      new Error('upstream connect error or disconnect/reset before headers'),
    ]
    for (const e of cases) {
      const msg = classifyCreateAgentError(e)
      expect(msg, `case: ${String(e)}`).toContain('网络连接失败')
      // 不应泄漏技术细节
      expect(msg).not.toContain('Failed to fetch')
      expect(msg).not.toContain('ERR_CONNECTION_REFUSED')
    }
  })

  it('long 4xx detail is truncated to < 200 chars (UI does not overflow)', () => {
    const long = 'API 400: ' + 'x'.repeat(500)
    const msg = classifyCreateAgentError(new Error(long))
    expect(msg.length).toBeLessThan(200)
    // 截断后应该是「创建失败，请检查配置」之类的兜底，而不是 500 字符 x
    expect(msg).not.toContain('x'.repeat(100))
  })

  it('unknown / non-Error input: graceful fallback (no crash, returns a string)', () => {
    // 兜底：null / undefined / string / number / object — 都不应抛
    const inputs: unknown[] = [
      null,
      undefined,
      '',
      'plain string error',
      12345,
      { foo: 'bar' },
      new Error(''), // 空 message
    ]
    for (const input of inputs) {
      expect(() => classifyCreateAgentError(input)).not.toThrow()
      const msg = classifyCreateAgentError(input)
      expect(typeof msg).toBe('string')
      expect(msg.length).toBeGreaterThan(0)
      expect(msg.length).toBeLessThan(200)
    }
  })
})