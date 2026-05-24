# 前端 Phase 0 — 转换方案

> 版本: v1.0 | 日期: 2026-05-23 | 基于 `前端实施计划_v1.md` Phase 0 展开
> 目标: 在 `frontend/` 重建 Vite + React 18 + TypeScript + Tailwind + Zustand 工程，现有 v0 原型移至 `prototype/` 作为 UX 参考

---

## 一、为什么重搭而非改造

现状 `frontend/` 的架构：

```
AgentHub-v0.html           ← CDN 加载 React UMD + Babel Standalone
  ├── src/data.js           ← 全局变量 window.DATA（mock 数据）
  ├── src/icons.jsx         ← 手写 65 个 SVG 图标
  ├── src/ui.jsx            ← 自实现 shadcn 组件
  ├── src/app.jsx           ← useReducer 状态管理
  ├── src/views.jsx (1614行) ← 全部 Tab 视图挤在一个文件
  └── 其余 8 个 .jsx 文件   ← Babel 浏览器端实时编译
```

无法渐进式改造的原因：

| 问题 | 影响 |
|------|------|
| 无 `package.json` | 没有依赖管理、没有构建脚本 |
| 无 TypeScript | 红线要求 strict mode 零错误（CR-07），必须重建 |
| CDN Babel 编译 | 不支持 `import`/`export`、不支持 HMR、不产生构建产物 |
| `window.DATA` 全局变量 | 无法类型检查、无法 tree-shaking、无法按需加载 |
| `views.jsx` 1614 行单文件 | 红线建议组件 <200 行（CR-09），需拆分 |

结论：**新建 Vite 工程重写 UI，原型代码只做参考不复制粘贴。**

---

## 二、前置检查

```bash
# 1. 确认 git 状态干净
cd C:\Users\yhn\Desktop\字节比赛\AgentHub
git status

# 2. 确认 Node.js >= 18
node --version

# 3. 确认 npm >= 9
npm --version

# 4. 确认后端可联调（可选，Phase 0 不强制）
cd backend
# 确认 uvicorn / alembic 等可用
```

---

## 三、Step-by-Step

### Step 1 — 初始化 Vite + React + TS 项目

```bash
cd C:\Users\yhn\Desktop\字节比赛\AgentHub\frontend

# 在当前目录初始化（注意有 . 表示就地创建）
npm create vite@latest . -- --template react-ts
```

生成内容确认：

```
frontend/
├── package.json          # ← 新增
├── tsconfig.json         # ← 新增（需改为 strict）
├── tsconfig.app.json     # ← 新增
├── tsconfig.node.json    # ← 新增
├── vite.config.ts        # ← 新增
├── index.html            # ← 新增（替换 AgentHub-v0.html 作为入口）
├── public/               # ← 新增
├── src/                  # ← 会被覆盖，稍后处理
│   ├── main.tsx
│   ├── App.tsx
│   ├── vite-env.d.ts
│   └── ...
└── ...
```

**重要：** `npm create vite@latest .` 会覆盖已有 `index.html` 和 `src/`。我们的旧原型文件在下一节移走，所以没关系。

### Step 2 — 配置 TypeScript strict mode

红线 CR-07 要求 `tsc --noEmit` 零错误，禁止 `any`。

编辑 `tsconfig.json`：

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

### Step 3 — 安装生产依赖

```bash
npm install zustand lucide-react
```

| 包 | 作用 | 替代什么 |
|----|------|---------|
| `zustand` (v5) | 状态管理 | `useReducer` + `window.DATA` |
| `lucide-react` | 图标库 | `src/icons.jsx` 手写 65 个 SVG |

### Step 4 — 安装开发依赖

```bash
npm install -D tailwindcss @tailwindcss/vite @tailwindcss/typography
npm install -D eslint @eslint/js typescript-eslint prettier
```

| 包 | 作用 | 对应红线 |
|----|------|---------|
| `tailwindcss` + `@tailwindcss/vite` | 替代 CDN Tailwind 3 | — |
| `@tailwindcss/typography` | AI 回复 prose 样式 | — |
| `eslint` + `typescript-eslint` | 代码检查 | CR-11（禁止 console.log）|

### Step 5 — 配置 Vite + Tailwind

编辑 `vite.config.ts`：

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

**proxy 的作用**：开发时前端 `fetch('/api/agents')` 自动转发到后端 `localhost:8000`，避免 CORS 问题。

### Step 6 — 迁移设计 Token（从原型提取）

从 `AgentHub-v0.html` `<style>` 块中提取三项，写入 `src/styles/index.css`：

```css
@import "tailwindcss";

@theme {
  /* ── 品牌色（从原型 CSS 变量提取） ── */
  --color-brand: hsl(17 56% 53%);
  --color-brand-foreground: hsl(36 50% 98%);
  --color-brand-soft: hsl(22 60% 91%);
  --color-brand-deep: hsl(16 60% 33%);

  /* ── 磨砂玻璃 ── */
  --color-glass: hsl(38 60% 97%);
  --glass-alpha: 0.66;
  --glass-strong-alpha: 0.82;
  --glass-soft-alpha: 0.50;

  /* ── 阴影/分割 ── */
  --radius: 0.875rem;

  /* ── 动画 ── */
  --animate-fade-in: fade-in .3s cubic-bezier(.22,1,.36,1) both;
  --animate-slide-in: slide-in .25s cubic-bezier(.22,1,.36,1) both;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes slide-in {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── 打字动效 ── */
.typing-dot { animation: bounce-dot 1.2s ease-in-out infinite; }
.typing-dot:nth-child(2) { animation-delay: .15s; }
.typing-dot:nth-child(3) { animation-delay: .3s; }
@keyframes bounce-dot {
  0%,60%,100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-3px); opacity: 1; }
}

/* ── 磨砂玻璃面板 ── */
.glass-panel {
  background: hsl(var(--glass) / var(--glass-alpha));
  backdrop-filter: saturate(160%) blur(22px);
}
```

### Step 7 — 移动原型文件到 prototype/

```bash
mkdir prototype

# 主入口
mv AgentHub-v0.html prototype/

# 组件源码
mv src/ prototype/src/     # 整个旧的 src/ 移走

# 部署配置
mv Dockerfile prototype/
mv nginx.conf prototype/

# 截图、设计文档
mv screenshots/ prototype/
mv docs/ prototype/docs/     # 前端实施计划_v1.md 仍保留在 docs/

# 其他设计资产
mv uploads/ prototype/

# .gitignore 不动（已排除 docs/ screenshots/ uploads/）
```

移动后 `frontend/` 结构：

```
frontend/
├── prototype/             # ← 旧的完整原型（只读参考）
│   ├── AgentHub-v0.html
│   ├── src/               # ← 旧组件代码
│   ├── uploads/
│   ├── screenshots/
│   └── Dockerfile         # ← 旧部署配置
├── package.json           # ← 新工程
├── tsconfig.json
├── vite.config.ts
├── index.html
├── src/                   # ← 新工程源码
│   ├── main.tsx
│   ├── App.tsx
│   ├── styles/
│   │   └── index.css
│   ├── types/
│   ├── stores/
│   ├── hooks/
│   ├── api/
│   └── components/
├── public/
├── docs/                  # ← 保留，前端实施计划仍在
│   └── 前端实施计划_v1.md
└── 前端Phase0_转换方案.md  # ← 本文档
```

### Step 8 — 验证工程能跑

```bash
# 构建检查
npx tsc --noEmit          # 零错误（红线 CR-07）
npm run build              # 产出 dist/

# 开发服务器
npm run dev                # 访问 http://localhost:5173

# lint
npx eslint src/            # 无 console.log（红线 CR-11）
```

---

## 四、部署改造

### 旧部署（原型模式）

```dockerfile
FROM nginx:alpine
COPY AgentHub-v0.html /usr/share/nginx/html/
COPY src/ /usr/share/nginx/html/src/
# 无构建步骤，CDN 加载 React + Babel
```

### 新部署（生产构建）

```dockerfile
# Stage 1: 构建
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: 运行
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
```

`nginx.conf` 只需改一行：

```
# 旧
index AgentHub-v0.html;
try_files $uri $uri/ /AgentHub-v0.html;

# 新
index index.html;
try_files $uri $uri/ /index.html;
```

### 联调模式

开发阶段不依赖 Docker：前端 `npm run dev`（port 5173）+ 后端 `uvicorn`（port 8000），Vite proxy 自动转发 API 请求。

---

## 五、目录结构参考

新 `src/` 的推荐初始结构（按 `前端实施计划_v1.md` §1.1-1.4）：

```
src/
├── main.tsx                # ReactDOM.createRoot
├── App.tsx                 # 根布局 + 路由
├── vite-env.d.ts
├── styles/
│   └── index.css           # Tailwind + 设计 token
├── types/                  # 类型定义（对接 backend/schemas）
│   ├── agent.ts
│   ├── session.ts
│   └── message.ts
├── stores/                 # Zustand
│   ├── agentStore.ts
│   ├── chatStore.ts
│   └── sessionStore.ts
├── hooks/                  # 自定义 hooks
│   └── useWebSocket.ts
├── api/                    # HTTP 客户端
│   ├── client.ts           # fetch 封装 + 错误处理
│   ├── agents.ts
│   └── sessions.ts
├── components/
│   ├── ui/                 # shadcn 基件（从 prototype/src/ui.jsx 移植）
│   │   ├── Button.tsx
│   │   ├── Avatar.tsx
│   │   ├── Badge.tsx
│   │   └── ...
│   ├── layout/             # 三栏布局
│   │   ├── Sidebar.tsx
│   │   ├── CenterPanel.tsx
│   │   └── RightPanel.tsx
│   └── chat/               # Phase 2 聊天组件
│       ├── ChatView.tsx
│       ├── MessageBubble.tsx
│       └── StreamingText.tsx
└── assets/
    └── ...
```

**注意**：Phase 0 只搭骨架，`components/` 内的具体组件在 Phase 1+ 逐步填入。

---

## 六、风险与注意事项

| # | 风险 | 缓解措施 |
|---|------|---------|
| 1 | `npm create vite@latest .` 覆盖现有 `src/` | Step 7 先移走原型，覆盖无损失 |
| 2 | 原型 1614 行 `views.jsx` 无法直接复制 | 只做参考对照，重写时按 Phase 拆分 |
| 3 | Tailwind CSS v4 API 与 v3 有差异 | 使用 `@tailwindcss/vite` 插件 + `@import "tailwindcss"` 语法，不从 CDN 加载 |
| 4 | 后端 proxy 需后端已启动 | Vite proxy 可配置 `bypass`，后端未启动时前端 mock 数据兜底 |
| 5 | .gitignore 需更新 | 新增 `prototype/` 的行为需确认——原型文件是参考，是否入库由团队决定 |

---

## 七、验收标准

Phase 0 完成时验收：

- [ ] `npm run dev` 正常启动，访问 `http://localhost:5173` 显示空白 Vite 页面
- [ ] `npx tsc --noEmit` 零错误
- [ ] `npm run build` 产出 `dist/` 目录
- [ ] Tailwind 设计 token 已配置，`bg-brand` / `glass-panel` 等类名可用
- [ ] `lucide-react` 图标可渲染（`import { MessageSquare } from 'lucide-react'`）
- [ ] Zustand store 可创建基础 store 实例
- [ ] 原型文件已移至 `prototype/`，`AgentHub-v0.html` 可双击打开
- [ ] `.gitignore` 包含 `node_modules/` `dist/`
- [ ] `eslint` 运行无报错
