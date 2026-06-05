import { api } from './client'

/** 文件系统浏览：复用后端 /api/fs/browse + /api/fs/mkdir + /api/fs/read + /api/fs/search */
export const fsApi = {
  /** 浏览某目录；空路径返回可用盘符列表 */
  browse: (path = '') => api.get<FsBrowseOut>(`/api/fs/browse${path ? `?path=${encodeURIComponent(path)}` : ''}`),
  /** 读文本/代码类文件；>2MB 返 413；二进制返 415 */
  readFile: (path: string) => api.post<FsReadOut>('/api/fs/read', { path }),
  /** 新建文件夹 */
  mkdir: (parent: string, name: string) =>
    api.post<FsMkdirOut>('/api/fs/mkdir', { parent, name }),
  /** 在 path 下按文件名模糊搜索（递归） */
  search: (path: string, q: string, limit = 100) =>
    api.get<FsSearchOut>(
      `/api/fs/search?path=${encodeURIComponent(path)}&q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
}

export interface FsItem {
  name: string
  path: string
  type: string
}

export interface FsBrowseOut {
  /** 当 path="" 时返回盘符数组 */
  path?: string
  parent?: string
  items?: FsItem[]
}

export interface FsReadOut {
  path: string
  name: string
  size: number
  content: string
}

export interface FsMkdirOut {
  path: string
  name: string
  parent: string
}

export interface FsSearchResultItem {
  name: string
  path: string
  type: 'file' | 'dir'
}

export interface FsSearchOut {
  results: FsSearchResultItem[]
  truncated: boolean
  query?: string
  error?: string
}
