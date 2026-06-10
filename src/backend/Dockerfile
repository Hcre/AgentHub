FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖 + Node.js 20.x + Claude Code CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl ca-certificates gnupg git \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code \
    && npm install -g @earendil-works/pi-coding-agent \
    && npm install -g opencode-ai || echo "opencode-ai skipped (glibc vs musl)"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 容器内以 root 跑 Claude Code CLI（--dangerously-skip-permissions 默认拒绝 root）。
# IS_SANDBOX=1 是 Claude Code 官方的「沙箱/容器」豁免开关：承认是受控环境后放行 root。
# 子进程 env 继承自 os.environ.copy()（见 claude_code_runtime._build_env），故此处即生效。
# 放在 COPY 之后、仅新增一个廉价层，不打断上方 apt/npm/pip 的构建缓存。
ENV IS_SANDBOX=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
