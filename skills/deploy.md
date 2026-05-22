---
name: deploy
description: Deploy AgentHub locally via Docker Compose. Use when setting up the project for the first time or restarting after changes.
---

# deploy: 部署 AgentHub

## 首次部署

### 1. 进 WSL Ubuntu

```powershell
wsl -d Ubuntu
```

### 2. 启动 Docker

```bash
sudo service docker start
docker ps
```

### 3. 部署

```bash
cd /mnt/d/AgentHub/repo
docker compose -f docker/docker-compose.yml up --build -d
```

### 4. 验证

- http://localhost:8000/health → `{"status":"ok"}`
- http://localhost:8000/docs → API 文档
- http://localhost:5173 → 前端 UI

---

## 日常开发

### 重新构建

```bash
cd /mnt/d/AgentHub/repo
docker compose -f docker/docker-compose.yml up --build -d
```

### 查看日志

```bash
docker compose -f docker/docker-compose.yml logs -f <service>
```

### 停止

```bash
docker compose -f docker/docker-compose.yml down
```

---

## 故障排查

| 问题 | 解决 |
|------|------|
| Docker 连不上 | `sudo service docker start` |
| 拉镜像超时 | 检查 `/etc/docker/daemon.json` 镜像源 |
| 端口冲突 | `netstat -ano | findstr 8000` 检查占用 |
| 容器异常 | `docker compose logs <service>` 看日志 |
