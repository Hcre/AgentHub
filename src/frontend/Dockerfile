# 单 stage dev 模式：
#   容器内跑 vite dev server，源文件由 docker-compose volume mount 注入
#   （host 改文件即生效，HMR 实时刷新，避免 docker compose build 等待）
# 注意：原多阶段 build 模式被替换。如果未来要切回 nginx serve 静态产物，
#      走 Dockerfile.build（多阶段 build + nginx）。
FROM node:22-alpine

WORKDIR /app

# 装依赖（只 COPY package.json/lock，源文件 src/ 由 volume mount 覆盖）
COPY package*.json ./
# 占位文件：build 期间 npm ci / vite dev 启动时能找到这些文件；
# volume mount 时会被 host 的实时文件覆盖。
COPY index.html ./
COPY vite.config.ts ./
COPY tsconfig.json ./
COPY tsconfig.node.json ./
# src/ 目录必须有（即使空）— vite dev 启动时会扫它；volume mount 会用 host 内容覆盖
RUN mkdir -p /app/src /app/public

RUN npm ci

# 跨平台 HMR：Windows + Docker Desktop + volume mount 必开 polling
ENV CHOKIDAR_USEPOLLING=true
# 容器外可访问：--host 0.0.0.0
# 端口：vite.config.ts 已设 5173，CLI 再显式声明一次保险
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
