# AgentHub 前端

IM 聊天式多 Agent 协作平台的前端。Vite + React 19 + TypeScript(strict) + Tailwind v4 + Zustand。

当前为 **mock 驱动**（数据来自 `src/data/`，无网络请求）。前端实施计划 §1–6 + §7.3 视觉打磨已完成，真实 API/WS 联调（§7.1/7.2）待后端接入。

## 快速开始

```bash
npm install
npm run dev      # http://localhost:5173
```

## 脚本

| 命令 | 作用 |
|------|------|
| `npm run dev` | 开发服务器（HMR） |
| `npm run build` | 类型检查 + 生产构建 → `dist/` |
| `npm run lint` | ESLint |
| `npm run format` / `format:check` | Prettier |

## 文档

- **接手必读：[`HANDOFF.md`](./HANDOFF.md)** — 结构、各 store→API 接入点、运行、mock 边界、待办
- 群聊专项：[`src/components/group/HANDOFF.md`](./src/components/group/HANDOFF.md)
- 各阶段日志：`../worklogs/袁/`

## 部署

```bash
docker compose -f ../docker/docker-compose.yml up -d --build frontend   # → http://localhost:5173
```

多阶段构建（Node 构建 → nginx 托管 `dist/`），配置见 `Dockerfile` / `nginx.conf`。
