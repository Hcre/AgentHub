# 异常分支演练 — 3 个代表性场景

> 选自 SA-001 EX-MCP-V1.0-20260602（132 条异常）。覆盖 输入异常 / 状态异常 / 通信异常 / 资源异常 / 逻辑异常 五类中的三类，验证 NFR3「明确报错不静默」可被满足。
> 每条按"触发条件 → 捕获模块 → 报错信息 → 用户可执行的下一步 → 流程是否优雅退出"展开。

---

## 场景 1 — URL 私网访问（SSRF 防护）

**编号**：EX-059 + EX-060 + EX-062（综合自 BP-018 sse/http 与 BP-020 dry-run）
**类型**：逻辑异常（SSRF 攻击 / DNS 重绑定）
**对应 PRD**：F-019 创建 MCP - sse/http 传输
**对应文件框架**：`产出物/07-文件框架/M-C06/`（SSRF Guard）+ `M-C04/`（DNS Pinning）+ `M-C05/`（Network ACL）

### 1.1 触发条件
Alice 在创建 SSE 传输 MCP 时填入 URL `http://10.0.0.5/admin`（私网 RFC 1918）— 试图从 AgentHub 后端服务器 SSRF 攻击内网。

### 1.2 捕获链路
1. M-B05 `submit()` 第 4 步 `manifest_validator` 触发 [TD:S-032] yarl.URL 解析
2. M-C06 `URLValidator.run` 链路（5 层 Chain of Responsibility）：
   - 链 1：scheme ∈ {http, https} ✓
   - 链 2：host 解析为 `10.0.0.5` → 命中私网黑名单 ✗
   - 链 3：跳过 DNS pinning（已在前置步骤捕获）
3. M-C04 兜底：即便 host 写成公网域名 `attacker.com` 解析到 `10.0.0.5`，DNS 固定后该 IP 也会被 M-C05 拦截

### 1.3 报错信息
- HTTP 422
- Body：
  ```json
  {
    "error_code": "SSRF_PRIVATE_NETWORK",
    "message": "URL 指向私网/loopback/链路本地地址，已被 AgentHub 安全策略拒绝",
    "field_path": "manifest_json.url",
    "policy_ref": "BR:R-015 / R-016 / SEC:SEC-005",
    "next_action": "请使用公网可访问的 HTTPS 端点。如确需访问内网，请联系 R-01 申请 workspace 白名单。"
  }
  ```

### 1.4 用户可执行的下一步
- 修改 URL 为公网 HTTPS 端点 → 重新提交
- 如确需内网访问 → 联系 R-01（平台管理员）申请 workspace 级 `network_egress` 白名单（DE-011 字段）
- 在 M-B05 `rollback(trace_id)` 中查看详细审计与请求载荷

### 1.5 流程是否优雅退出
**是**。
- `mcp_submission.status = rejected`，无下游副作用
- 事件 `mcp.rollback_done` 发布至 M-EV01（topic `mcp.submission.rejected`）
- 审计日志 M-D02 写入 `args_hash=...` 与 trace_id，R-04 事后可审计
- M-D03 5min 告警去重（[调研 S-066]）不重复触发 R-01 告警

---

## 场景 2 — 工具未在 allowlist 中

**编号**：EX-054 + EX-055（BP-024 权限显式同意 + BP-026 重试降级）
**类型**：状态异常（权限缺失 / 未审批）
**对应 PRD**：F-025 权限/安全策略 + F-022/F-023/F-024 Inbox 审批
**对应文件框架**：`产出物/07-文件框架/M-B04/`（Approval Engine）+ `M-A01/` + `M-C07/`（Secret Manager）

### 2.1 触发条件
Alice 通过 CLI 触发 tool_call `read_secret --args {"key":"OPENAI_API_KEY"}`，但 `read_secret` 不在已审批的 allowlist 中（DE-020）。

### 2.2 捕获链路
1. M-A01 网关层 → M-B03 透传 → 拍 4 命中 M-B04 `check_allowlist`
2. M-B04 流程：
   - 计算 `args_hash = SHA256(sorted_json({"key":"OPENAI_API_KEY"}))` → `3a8e...`
   - Redis `allow:{user}:{mcp}` MISS → DB `mcp_inbox_allowlist` 查 → 0 行
   - 返回 `allowlist_miss`
3. M-B04 触发 M-A01 返回 HTTP 412 Precondition Required（非 200 也非 5xx，明确告知）
4. CLI 端弹出 Inbox 审批 UI（10min 软超时 + 30min 硬拒绝，[调研 S-018] HITL 模式）

### 2.3 报错信息
- HTTP 412
- Body：
  ```json
  {
    "error_code": "TOOL_NOT_IN_ALLOWLIST",
    "message": "工具 'read_secret' 未在 allowlist 中（args_hash=3a8e...），需 R-03 显式同意后 30 天内有效。",
    "approval_url": "/inbox/approve?trace_id=tr-0f3a...&tool=read_secret&expires=1800s",
    "fallback_chain": ["10min 软提醒", "30min 硬拒绝"],
    "policy_ref": "BR:R-017 / R-028 / [调研 S-018, S-030]"
  }
  ```
- CLI 终端展示：`Tool not in allowlist. Approve at <approval_url> (or pass --auto-approve in 10min)`

### 2.4 用户可执行的下一步
- 在 10min 内点击 approval_url 完成 Inbox 审批 → 工具调用自动重放
- 超 10min：再次 CLI 调用 --auto-approve 重置 10min 软计时
- 超 30min：硬拒绝，需 R-01 介入审计（CE-010 immutable consent 修复）
- 若不想被此类提示打断：预热阶段批量 allowlist（`agenthub mcp allow --tool ...`）

### 2.5 流程是否优雅退出
**是**。
- tool_call 状态保留为 `pending_approval`，未执行、未生成审计（防止"未授权已执行"）
- 30min 硬超时后 M-A04 Cron Scheduler 触发 `expire_pending_approvals`，状态转 `expired`
- M-C07 Secret Manager 即使被调用也会返回 `PERMISSION_DENIED`（5 层防御兜底）
- 符合 NFR3：用户拿到明确的"该做什么"，而非"5xx 未知"

---

## 场景 3 — ffmpeg/Whisper 不可用（基础设施缺失）

**编号**：EX-049（BP-020 dry-run 资源异常）+ EX-057（BP-017 stdio 资源异常 综合）
**类型**：资源异常（基础设施缺失）
**对应 PRD**：F-018 创建 MCP - stdio 传输（[任务场景隐含：CLI 调用转写子命令]）+ F-021 dry-run 沙箱
**对应文件框架**：`产出物/07-文件框架/M-C01/`（Sandbox Engine）

### 3.1 触发条件
R-02 Bob 提交一个 stdio MCP（`my-whisper`），manifest 中 `cmd=["/usr/local/bin/whisper-transcribe", "--lang", "zh"]`，但在 dry-run 沙箱内 `/usr/local/bin/whisper-transcribe` 不存在（PATH 中无 ffmpeg、whisper 二进制），进程立即 exit 127（command not found）。

### 3.2 捕获链路
1. M-B05 `submit()` 启动 Saga 链 → 第 3 步 `dry_run`（API-Saga-003）
2. M-C01 `SandboxRunner.run(cmd, limits, timeout_sec=30)`：
   - `_validate_cmd` 通过（list 形式，路径存在性不预检）
   - 后端选择：Linux cgroup v2
   - `LinuxCgroupBackend.run` → `subprocess.run([...], capture_output=True)`
   - exit code 127，stderr=`/bin/sh: whisper-transcribe: command not found`
3. M-C01 上报 `SandboxResult(status=failed, exit_code=127, killed_reason=exec_not_found, duration_ms=42)`
4. M-C01 → Saga 第 3 步返回 `error_code=SANDBOX_EXEC_NOT_FOUND`（沿用 4xx 而非 5xx，便于客户端重试）
5. M-B05 Saga 链终止：状态 `rejected`（无补偿，未对外可见，[DD 洞察-3]）
6. M-B05 发布事件 `mcp.submission.rejected` 至 M-EV01

### 3.3 报错信息
- HTTP 422
- Body：
  ```json
  {
    "error_code": "SANDBOX_EXEC_NOT_FOUND",
    "message": "MCP 进程在 dry-run 沙箱中启动失败：可执行文件不存在",
    "sandbox_diagnostics": {
      "exit_code": 127,
      "stderr_tail": "/bin/sh: whisper-transcribe: command not found",
      "killed_reason": "exec_not_found",
      "duration_ms": 42,
      "sandbox_backend": "linux_cgroup_v2",
      "dryrun_log_url": "/v1/dryrun/jobs/{job_id}/log?expires=7d"
    },
    "next_action": "请检查 manifest.cmd 是否指向正确的可执行文件；如需在沙箱内使用，请改用 Docker 镜像 manifest 或将二进制打包到 MCP 资源中。",
    "policy_ref": "[DD-001:MD/M-C01] + BR:R-011 / R-012"
  }
  ```

### 3.4 用户可执行的下一步
- 下载 dryrun 日志（保留 7 天，[PRD:F-021 验收③]）→ 分析完整 stderr
- 修复 manifest 后重新 submit（幂等键 (mcp_id, version) 命中会返回已有 trace_id，需 mgr 端先 reset）
- 切换为 Docker manifest：`cmd=["docker", "run", "--rm", "-i", "myregistry/whisper:latest"]`（走 Docker backend）
- 若属网络问题（CDN 拉镜像失败）：[反例 CE-006] Windows 缺失 Docker 时 R-01 强制阻断 + 明确提示

### 3.5 流程是否优雅退出
**是**。
- `mcp_submission.status = rejected`，无 Saga 补偿（K4 / Dry-run 失败不需补偿）
- 事件 `mcp.rollback_done` + `mcp.submission.rejected` 已发
- 5min 告警去重不重复触发 R-01
- 资源回收：cgroup v2 slice 已自动清理（pids.max=1 时无遗留子进程）
- 满足 NFR3：客户端拿到 exit_code + stderr_tail + dryrun_log_url，5s 内可定位

---

## 综合判定

| 维度 | 场景 1（SSRF） | 场景 2（Allowlist） | 场景 3（ffmpeg/Whisper） |
|---|---|---|---|
| 是否触发 NFR3 明确报错 | ✅ | ✅ | ✅ |
| 是否明确 error_code | ✅ SSRF_PRIVATE_NETWORK | ✅ TOOL_NOT_IN_ALLOWLIST | ✅ SANDBOX_EXEC_NOT_FOUND |
| 是否含 next_action | ✅ | ✅ | ✅ |
| 是否含 field_path / log_url | ✅ field_path | ✅ approval_url | ✅ dryrun_log_url |
| 是否生成审计 | ✅ | ✅ | ✅ |
| 是否触发告警 | ✅（去重 5min） | ❌（用户态） | ❌（用户态） |
| 流程优雅退出 | ✅ | ✅ | ✅ |
| 涉及模块数 | 4 | 3 | 2 |
| 涉及 EX 条目数 | 3 | 2 | 2 |
| 涉及调研来源数 | 3（S-032/S-052/RSK-02） | 2（S-018/S-030） | 2（S-025/RSK-04） |

**结论**：三个异常场景均能在 5 秒内返回明确 error_code + 错误路径 + next_action + 审计行 +（必要时）UI 提示，符合 NFR3「明确报错不静默」；流程均能优雅退出（不残留 cgroup 资源 / 不双写审计 / 不误触发告警）。
