// MCP (Model Context Protocol) API client — 封装后端 /api/mcp/* 全部端点
// 对齐 `docs/specs/04-commands_命令接口.md` §2.6 + `app/schemas/mcp.py`
//
// 范围:
//   F1 市场浏览 + 详情 (GET market, market/templates, market/{id})
//   F2 安装/卸载 (POST/DELETE installations)
//   F2.5 绑定/解绑 (POST/DELETE bindings)
//   F3 创建 (POST servers) — owner-override 已闭环

import { api } from './client'

export type McpTransport = 'stdio' | 'sse' | 'streamable_http'

export interface McpMarketItem {
  mcp_id: string
  name: string
  slug: string
  description: string
  transport: McpTransport
  version: string
  tags: string[]
  official: boolean
  install_count: number
}

export interface McpMarketList {
  items: McpMarketItem[]
  total: number
  page: number
  page_size: number
}

export interface McpServerDetail {
  mcp_id: string
  name: string
  slug: string
  description: string
  transport: McpTransport
  config_schema: Record<string, unknown>
  version: string
  tags: string[]
  official: boolean
  status: string
  created_by: string | null
  created_at: string
  updated_at: string
  dry_run_result: Record<string, unknown> | null
}

export interface McpTemplate {
  template_id: string
  name: string
  transport: McpTransport
  version: string
  tags: string[]
  mcp_config: Record<string, unknown>
}

export interface McpTemplateList {
  templates: McpTemplate[]
}

export interface McpInstallation {
  installation_id: string
  status: string
  mcp_id: string
  instance_name: string
  created_at: string
}

export interface McpBinding {
  binding_id: string
  agent_id: string
  installation_id: string
  tool_subset: string[]
  status: string
  created_at: string
}

export interface InstallMcpInput {
  workspace_id: string
  mcp_id: string
  instance_name: string
  config_overrides?: Record<string, unknown>
}

export interface BindMcpInput {
  agent_id: string
  installation_id: string
  tool_subset?: string[]
}

export interface CreateMcpServerInput {
  name: string
  slug: string
  description?: string
  transport: McpTransport
  config_json: Record<string, unknown>
  version?: string
  tags?: string[]
  template_id?: string
  dry_run?: boolean
}

export interface McpServerCreated {
  mcp_id: string
  name: string
  slug: string
  description: string
  transport: McpTransport
  version: string
  tags: string[]
  status: string
  created_by: string | null
  dry_run_result: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

function qs(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export const mcpApi = {
  // ── F1 市场 ──
  listMarket: (params: {
    workspace_id: string
    q?: string
    tag?: string
    transport?: McpTransport
    official_only?: boolean
    page?: number
    page_size?: number
  }) => {
    return api.get<McpMarketList>(
      `/api/mcp/market${qs({
        workspace_id: params.workspace_id,
        q: params.q,
        tag: params.tag,
        transport: params.transport,
        official_only:
          params.official_only === undefined ? undefined : String(params.official_only),
        page: params.page,
        page_size: params.page_size,
      })}`,
    )
  },

  listTemplates: (params: { workspace_id: string }) =>
    api.get<McpTemplateList>(
      `/api/mcp/market/templates${qs({ workspace_id: params.workspace_id })}`,
    ),

  getMarketDetail: (mcpId: string) => api.get<McpServerDetail>(`/api/mcp/market/${mcpId}`),

  // ── F2 安装/卸载 ──
  install: (input: InstallMcpInput) => api.post<McpInstallation>('/api/mcp/installations', input),

  uninstall: (installationId: string, workspaceId: string) =>
    api.del<void>(`/api/mcp/installations/${installationId}${qs({ workspace_id: workspaceId })}`),

  // ── F2.5 绑定/解绑 (agent ↔ installation) ──
  bind: (input: BindMcpInput) => api.post<McpBinding>('/api/mcp/bindings', input),

  unbind: (bindingId: string) => api.del<void>(`/api/mcp/bindings/${bindingId}`),

  // ── F3 创建 ──
  createServer: (input: CreateMcpServerInput) =>
    api.post<McpServerCreated>('/api/mcp/servers', input),
}
