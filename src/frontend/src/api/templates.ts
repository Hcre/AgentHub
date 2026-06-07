import { api } from "./client";

export interface TemplateApiItem {
  id: string;
  source: string;
  source_path: string;
  name: string;
  description: string;
  model_tier: string;
  tools: string[];
  color: string | null;
  display_name_zh: string | null;
  description_zh: string | null;
  recommended_skills: string[];
  compatible_agent_systems: string[];
  compatible_providers: string[];
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateDetail extends TemplateApiItem {
  system_prompt: string;
}

export interface TemplateListResponse {
  items: TemplateApiItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface SourceStatusResponse {
  id: string;
  url: string;
  branch: string;
  description_zh: string | null;
  enabled: boolean;
  template_count: number;
  last_synced: string | null;
  created_at: string;
}

export interface SyncResultResponse {
  source_id: string;
  added: number;
  updated: number;
  deleted: number;
  total: number;
  error: string | null;
}

export interface CreateTemplateInput {
  name: string;
  description?: string;
  system_prompt?: string;
  model_tier?: string;
  recommended_skills?: string[];
  display_name_zh?: string | null;
  description_zh?: string | null;
  compatible_agent_systems?: string[];
  compatible_providers?: string[];
}

export const templatesApi = {
  list: (params?: {
    q?: string;
    model_tier?: string;
    page?: number;
    page_size?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.set("q", params.q);
    if (params?.model_tier) sp.set("model_tier", params.model_tier);
    if (params?.page) sp.set("page", String(params.page));
    if (params?.page_size) sp.set("page_size", String(params.page_size));
    const qs = sp.toString();
    return api.get<TemplateListResponse>(
      `/api/templates/${qs ? `?${qs}` : ""}`,
    );
  },

  get: (id: string) =>
    api.get<TemplateDetail>(`/api/templates/${id}`),

  create: (input: CreateTemplateInput) =>
    api.post<TemplateApiItem>("/api/templates/", input),

  update: (id: string, input: Partial<CreateTemplateInput>) =>
    api.patch<TemplateApiItem>(`/api/templates/${id}`, input),

  delete: (id: string) =>
    api.del<void>(`/api/templates/${id}`),

  sync: () =>
    api.post<SyncResultResponse>("/api/templates/sync", {}),

  getSourceStatus: () =>
    api.get<SourceStatusResponse | null>("/api/templates/source/status"),

  /** Download .md file via Blob to trigger browser save dialog. */
  exportMarkdown: async (id: string) => {
    const BASE = import.meta.env.VITE_API_BASE_URL || "";
    const res = await fetch(`${BASE}/api/templates/${id}/export`);
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`API ${res.status}: ${detail}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?(.+?)"?$/);
    const filename = match?.[1] || "template.md";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};
