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

  /** 抽取 .pptx 每页文本（标题/正文/备注）供 SlideView 渲染。非 pptx 415 / 损坏 422 由 api 抛错。 */
  pptxSlides: (path: string) =>
    api.get<FsPptxSlidesOut>(`/api/fs/pptx-slides?path=${encodeURIComponent(path)}`),

  /** 某文件的 git 提交历史；非 git 仓库 → {ok:false, reason}。 */
  fileHistory: (path: string, limit = 50) =>
    api.get<FsFileHistoryOut>(`/api/fs/file-history?path=${encodeURIComponent(path)}&limit=${limit}`),

  /** 取某文件在某 commit 时的内容；非 git → {ok:false}。 */
  fileAtRev: (path: string, rev: string) =>
    api.get<FsFileAtRevOut>(`/api/fs/file-at-rev?path=${encodeURIComponent(path)}&rev=${encodeURIComponent(rev)}`),

  /** 把内容写回已存在文件（版本回溯）；不存在 404。 */
  fileWrite: (path: string, content: string) =>
    api.post<{ ok: boolean; path: string; size: number }>('/api/fs/file-write', { path, content }),
}

export interface FileCommit {
  sha: string
  short: string
  author: string
  date: string
  subject: string
}

export interface FsFileHistoryOut {
  ok: boolean
  path?: string
  relpath?: string
  count?: number
  commits?: FileCommit[]
  reason?: string
}

export interface FsFileAtRevOut {
  ok: boolean
  rev?: string
  relpath?: string
  content?: string
  /** 该版本 → 当前工作树的 unified diff（供 DiffView 渲染对比） */
  diff?: string
  reason?: string
}

export interface PptxSlide {
  index: number
  title: string
  texts: string[]
  notes: string
}

export interface FsPptxSlidesOut {
  ok: boolean
  path: string
  count: number
  slides: PptxSlide[]
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
