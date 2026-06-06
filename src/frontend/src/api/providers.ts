import { api } from './client'

/** 对应 backend `DefaultConfigOut`（schemas/provider.py）。
 *  Step 2 选中 CLI 卡片后调此端点拿到本地配置的 4 字段，回填表单。 */
export interface DefaultConfig {
  agent_system: string
  model: string | null
  base_url: string | null
  /** 可能是真 key，也可能是 "(chatgpt-login)" 这种标记字符串（来自 Codex 登录态） */
  api_key: string | null
  provider: string | null
  /** 实际读到的配置文件路径；null = 没找到 */
  source: string | null
  note: string | null
}

/** 对应 backend `ProviderOut`（schemas/provider.py）— 后端 /api/providers 列表返回。 */
export interface ProviderInfo {
  name: string
  display_name: string
  binary: string
  executable_path: string
  version: string | null
  adapter: string
  description: string
  available: boolean
}

/** Provider 相关 API（CLI 自动检测 + 默认配置回填）。 */
export const providersApi = {
  /** 列出当前系统中所有自动检测到的 Agent CLI。 */
  list: () => api.get<ProviderInfo[]>('/api/providers'),
  /** 手动触发重新扫描 PATH，发现新增或移除的 CLI。 */
  scan: () => api.post<ProviderInfo[]>('/api/providers/scan', undefined),
  /** 取某个 CLI 的本地配置（model + base_url + api_key + provider），Step 2 选中卡片后回填用。 */
  getDefaultConfig: (agentSystem: string) =>
    api.get<DefaultConfig>(`/api/providers/${encodeURIComponent(agentSystem)}/default-config`),
}
