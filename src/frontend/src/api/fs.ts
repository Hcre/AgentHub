import { api } from './client'

/** 文件系统浏览：复用后端 /api/fs/browse + /api/fs/mkdir + /api/fs/read + /api/fs/search */
export const fsApi = {
  /** 浏览某目录；空路径返回可用盘符列表 */
  browse: (path = '') =>
    api.get<FsBrowseOut>(`/api/fs/browse${path ? `?path=${encodeURIComponent(path)}` : ''}`),
  /** 读文本/代码类文件；>2MB 返 413；二进制返 415 */
  readFile: (path: string) => api.post<FsReadOut>('/api/fs/read', { path }),
  /** 新建文件夹 */
  mkdir: (parent: string, name: string) => api.post<FsMkdirOut>('/api/fs/mkdir', { parent, name }),
  /** 在 path 下按文件名模糊搜索（递归） */
  search: (path: string, q: string, limit = 100) =>
    api.get<FsSearchOut>(
      `/api/fs/search?path=${encodeURIComponent(path)}&q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  /** 在 path（git 工作目录）跑 `git diff [--staged]`，返 unified diff 文本。
   *  非 git 仓库 / git 缺失 / 超时 → 200 + {ok:false, reason:string}，前端不抛异常。 */
  gitDiff: (path: string, staged = false) =>
    api.get<FsGitDiffOut>(`/api/fs/git-diff?path=${encodeURIComponent(path)}&staged=${staged}`),

  /** M3-B：抽取 .pptx 文件的页文本（python-pptx 后端实现） */
  pptxSlides: (path: string) => api.post<PptxSlidesOut>('/api/fs/pptx-slides', { path }),

  /** M3-C：某文件的 git commit 列表（owner override降级：只读，无 fs_write） */
  fileHistory: (path: string, limit = 50) =>
    api.post<FileHistoryOut>('/api/fs/file-history', { path, limit }),
  /** M3-C：取某文件在某 commit 时的内容（git show <sha>:<path>） */
  fileAtRev: (path: string, rev: string) =>
    api.post<FileAtRevOut>('/api/fs/file-at-rev', { path, rev }),
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
  items: FsSearchResultItem[]  // backend returns 'items' not 'results'
  truncated: boolean
  query?: string
  error?: string
}

export interface FsGitDiffOut {
  /** 后端 git 命令是否成功执行（在 git 仓库内 + git 可用 + 10s 内完成） */
  ok: boolean
  /** unified diff 文本；ok=true 时为空串表示"无变更" */
  diff: string
  /** 输出 >2MB 时被截断 */
  truncated?: boolean
  /** 是否查询的是 staged 区（`git diff --staged`） */
  staged?: boolean
  /** ok=false 时的错误描述（中文，来自后端） */
  reason?: string
}

// M3-B PPT 抽页端点返回结构
export interface PptxSlidesOut {
  path: string
  slide_count: number
  slides: Array<{
    index: number
    texts: string[]
    text_count: number
  }>
}

// M3-C 版本历史读端点返回结构
export interface FileHistoryCommit {
  sha: string
  author: string
  time: string
  message: string
}
export interface FileHistoryOut {
  path: string
  is_git: boolean
  commits: FileHistoryCommit[]
}
export interface FileAtRevOut {
  path: string
  rev: string
  content: string
  size: number
}
