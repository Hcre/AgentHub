# AgentHub 桌面 App 规格

> 版本:v0.1 草案 | 基于 [ADR-0007](../../worklogs/decisions/0007-tauri-desktop-pivot.md) | 2026-06-06
> 状态:**待 PR-01 2 人 Review Approve** — 评审通过后冻结为 v1.0,再启动代码开发
> 关联:[ADR-0007](../../worklogs/decisions/0007-tauri-desktop-pivot.md) · [worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md](../../worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md) · [04-commands](04-commands_命令接口.md)(后端零修改)

---

## 一、范围

### 1.1 本规格覆盖

AgentHub 桌面 App 的**前端壳行为**,包括:

- 启动流程(backend 健康探测、配置加载)
- 窗口与系统集成(单实例、托盘、菜单、通知)
- 用户配置存储(JWT、backend URL、UI 偏好)
- 自动更新
- 三平台打包与分发

### 1.2 本规格不覆盖(明确范围外)

- **后端实现零修改** — 5 层洋葱 / FastAPI / Docker Compose / CLI 优先 / MCP 全部沿用 [01-architecture](01-architecture_架构定义.md)
- **Web 端零修改** — 三栏布局 / AppShell / 现有 React 资产 1:1 复用
- **移动端(iOS / Android)** — 暂不实现,后续 PR 单独评估
- **应用商店上架** — 仅 GitHub Releases

### 1.3 架构定位

```
┌─────────────────────────────────────────────────────────────┐
│  AgentHub 桌面 App(本规格)                                  │
│  ┌─────────────────────────┐  ┌────────────────────────┐   │
│  │ Tauri 2.x WebView 壳    │  │ Tauri 2.x Rust 后端   │   │
│  │ (复用现有 React 资产)   │  │ (单实例/托盘/Updater) │   │
│  └────────────┬────────────┘  └────────────┬───────────┘   │
│               │  HTTP / WS                │               │
└───────────────┼────────────────────────────┼───────────────┘
                │                            │
                ▼                            ▼
       ┌──────────────────┐         ┌──────────────────┐
       │ 用户自部署的      │         │ Tauri Updater    │
       │ AgentHub Backend │         │ (GitHub Releases)│
       │ (FastAPI + PG)   │         │                  │
       │ = 0 修改         │         │                  │
       └──────────────────┘         └──────────────────┘
```

---

## 二、配置管理

### 2.1 Backend URL 配置(已冻结)

| 项 | 规格 |
|---|---|
| 默认值 | `http://localhost:8000` |
| 用户可改 | 是,设置页输入框 |
| 持久化位置 | `tauri-plugin-store` 存到 `~/.agenthub/desktop/config.json` |
| 协议限制 | 仅 `http://` / `https://`,禁止 `file://` / `javascript:` |
| 探测端点 | `GET <baseURL>/health`(后端已有,200 = OK) |
| 探测时机 | 启动时 1 次 + 手动"重试连接"按钮 |
| 探测超时 | 3s(避免网络差时阻塞 UI) |

**验收标准**:
- AC-2.1.1 首次启动时,config.json 不存在 → 默认 `http://localhost:8000` + 立即探测
- AC-2.1.2 探测成功 → 正常加载 React 应用
- AC-2.1.3 探测失败 → 显示「请先启动后端」教程卡片,引导填新 URL
- AC-2.1.4 用户改 URL 后 → 重启或点"重试"生效,持久化到 config.json

### 2.2 JWT 存储(已冻结)

| 项 | 规格 |
|---|---|
| 存储位置 | `tauri-plugin-store`(系统级 keychain 加密,macOS Keychain / Windows Credential Manager / Linux Secret Service) |
| 键名 | `auth.jwt_token` |
| 生命周期 | 登录成功后写入,登出时清除,过期由后端 401 触发前端跳转登录 |
| 多账号 | 不支持(单用户单 token,MVP 范围内) |

**验收标准**:
- AC-2.2.1 登录成功 → token 写入 keychain,后续启动免登录
- AC-2.2.2 登出 → token 清除,config.json 中 `auth.jwt_token` 键消失
- AC-2.2.3 后端返回 401 → 前端清 token + 跳登录页

### 2.3 UI 偏好(已冻结)

复用现有 `useUIStore`(theme / accent / density / headingFont),无需新增数据。App 启动时从后端拉(已实现)。

---

## 三、启动流程(已冻结)

```
[双击 App]
   │
   ▼
[Tauri 主进程启动]
   │
   ▼
[读 config.json] ─── 不存在 ──→ [使用默认 http://localhost:8000]
   │                              │
   │ 存在                         ▼
   ▼                       [GET {baseURL}/health]
[GET {baseURL}/health]           │
   │                              ├── 200 ──→ [加载 React 应用]
   │                              │              │
   │                              │              ▼
   │                              │         [useAgentStore.loadAgents()]
   │                              │         [useGroupStore.fetchGroups()]
   │                              │
   │                              └── 失败/超时 ──→ [显示「后端未启动」引导页]
   │
   └── 200/失败 同上
```

### 3.1 引导页规格(已冻结)

| 元素 | 内容 |
|---|---|
| 标题 | "未检测到 AgentHub 后端" |
| 主提示 | "请先启动后端服务,然后在下方填入后端 URL" |
| URL 输入框 | 预填当前探测失败的 URL |
| "重试连接"按钮 | 触发再次 `GET /health` |
| "如何启动后端"折叠面板 | 链接到 `README.md` 部署段(锚点 `#本地部署-docker`) |
| "退出"按钮 | 调 Tauri `app.exit()` |

**验收标准**:
- AC-3.1.1 引导页 URL 输入框只允许 `http://` / `https://` 开头,提交时校验
- AC-3.1.2 "重试连接"按钮 loading 态禁用,避免重复探测
- AC-3.1.3 探测成功 → 自动跳转到正常应用(无需手动刷新)

---

## 四、窗口行为(已冻结)

### 4.1 主窗口

| 项 | 规格 |
|---|---|
| 初始尺寸 | 1280 × 800(适配三栏布局) |
| 最小尺寸 | 1024 × 640 |
| 标题 | "AgentHub" |
| 是否可调整 | 是 |
| 关闭按钮语义 | 最小化到托盘(**不退出进程**),见 §5.2 |
| 启动时位置 | 记忆上次关闭位置(`window-state` plugin),首次居中 |

### 4.2 系统托盘(已冻结)

| 项 | 规格 |
|---|---|
| 图标 | 复用 App 图标(同 bundle) |
| 左键单击 | 显示/隐藏主窗口(无窗口则创建并聚焦) |
| 右键菜单 | "显示主窗口" / "退出 AgentHub" |
| 退出行为 | 杀所有进程 + 杀单实例锁 + `app.exit(0)` |

### 4.3 单实例(已冻结)

| 项 | 规格 |
|---|---|
| 机制 | `tauri-plugin-single-instance` |
| 行为 | 二次启动时,把已有窗口聚焦到前台,新进程退出 |
| 锁文件位置 | OS 临时目录(`/tmp/agenthub.lock` 等) |

**验收标准**:
- AC-4.3.1 双击 .exe / .dmg / .AppImage 启动两次 → 只有一个进程,主窗口聚焦

### 4.4 应用菜单(已冻结,仅 macOS 必需)

| 菜单 | 项 |
|---|---|
| App | 关于 AgentHub / 偏好设置...(打开设置页) / 退出 |
| 编辑 | 撤销 / 重做 / 剪切 / 复制 / 粘贴 / 全选(标准) |
| 视图 | 重新加载 / 开发者工具(开发模式) / 全屏 |
| 窗口 | 最小化 / 缩放 / 全部置前 |
| 帮助 | 文档(打开 `https://github.com/.../README`) / 查看更新 |

Windows / Linux 暂不实现(用 Web 端 UI 操作替代)。

---

## 五、原生通知(待 Review)

> 建议:通知 **可选开启**(默认关),MVP 范围内先发桌面通知给用户的"@我 / 新消息",避免通知轰炸。

| 项 | 规格 |
|---|---|
| 触发条件 | 用户在设置中开启 + 后端 WebSocket 推 `@用户` / `私聊` 事件 + 主窗口最小化/隐藏 |
| 通知库 | `tauri-plugin-notification` |
| 点击行为 | 聚焦主窗口 + 跳到对应会话 |
| 用户偏好 | `notifications.enabled`(bool,默认 false) |

**Review 关注点**:
- Q5-1 是否需要在 v0.1 就实现通知?(可降级到 v0.2)
- Q5-2 通知频控策略?(M2 不做,先发即发)

---

## 六、自动更新(已冻结)

| 项 | 规格 |
|---|---|
| 库 | `tauri-plugin-updater`(官方) |
| 检查时机 | 启动时静默检查(可设置关闭) |
| 更新源 | GitHub Releases `latest.json` |
| 签名 | Tauri 自动生成(`tauri-build` 内置 keypair),私钥存 CI secret |
| 强制/可选 | 都是可选,用户点"稍后"可推迟 |
| 失败处理 | 静默,下次启动再试,设置页可"立即检查" |

**验收标准**:
- AC-6.1.1 有新版本 → 设置页"检查更新"按钮变为"有可用更新,点击查看"
- AC-6.1.2 用户点确认 → 下载进度条显示
- AC-6.1.3 下载完成 → 弹窗"重启以应用更新",确认后退出 + 安装
- AC-6.1.4 用户取消 → 7 天内不再提示(可设置覆盖)

---

## 七、打包与分发(已冻结)

### 7.1 三平台产物

| 平台 | 格式 | 命名 | 签名 |
|---|---|---|---|
| macOS | `.dmg` + `.app` | `AgentHub_{version}_x64.dmg` / `aarch64.dmg` | v0.1 不签,README 写"右键打开";v0.2 加 notarization |
| Windows | `.msi` + `.exe` | `AgentHub_{version}_x64-setup.exe` | v0.1 自签,v0.2 买 Authenticode |
| Linux | `.AppImage` + `.deb` | `AgentHub_{version}_amd64.AppImage` / `.deb` | 不签 |

### 7.2 CI 矩阵(已冻结)

```yaml
# .github/workflows/release-desktop.yml(待写)
strategy:
  matrix:
    include:
      - platform: macos-latest    # 仅 release 时跑(贵)
        args: --target aarch64-apple-darwin,x86_64-apple-darwin
      - platform: ubuntu-22.04
        args: --target x86_64-unknown-linux-gnu
      - platform: windows-latest
        args: --target x86_64-pc-windows-msvc
```

### 7.3 版本号(已冻结)

- 跟随根 `package.json` 的 `version` 字段
- 首次发布:`v0.1.0-desktop-preview`(标记为 preview,不强制覆盖 web 用户)
- 正式版:`v0.1.0`

---

## 八、安全边界(已冻结)

### 8.1 CSP(Content Security Policy)

| 源 | 允许 |
|---|---|
| `default-src` | `'self'` |
| `connect-src` | `'self' <用户配置的 backend URL>`(动态注入) |
| `script-src` | `'self'` |
| `img-src` | `'self' data:` |
| `style-src` | `'self' 'unsafe-inline'`(Tailwind 运行时需要) |

### 8.2 危险操作隔离

- App 启动时,WebView `nodeIntegration: false`、`contextIsolation: true`(Tauri 默认)
- 所有后端调用走 `fetch` + JWT,**禁止** WebView 内的 JS 直接读本地文件
- 读本地文件(导入 skill 等)必须走 Tauri `dialog` + `fs` 插件,**不**用 `<input type="file">`

### 8.3 后端 URL 防注入(已冻结)

- 仅允许 `http://` / `https://` 协议
- 禁止 `file://` / `javascript:` / `data:` / `vbscript:`
- URL 长度 ≤ 2048 字符
- 提交到 fetch 之前由 Rust 端二次校验

**验收标准**:
- AC-8.3.1 输入 `file:///etc/passwd` → 拒绝 + 提示"仅支持 http/https 协议"

---

## 九、依赖与基础设施(已冻结)

| 依赖 | 用途 | 许可 |
|---|---|---|
| `@tauri-apps/api` ^2 | Tauri JS API | MIT / Apache-2.0 |
| `tauri-plugin-store` ^2 | 配置 + JWT 存储 | MIT |
| `tauri-plugin-updater` ^2 | 自动更新 | MIT |
| `tauri-plugin-single-instance` ^2 | 单实例锁 | MIT |
| `tauri-plugin-notification` ^2 | 桌面通知 | MIT |
| `tauri-plugin-window-state` ^2 | 窗口位置记忆 | MIT |
| `tauri-plugin-dialog` ^2 | 文件对话框 | MIT |
| `tauri-plugin-fs` ^2 | 文件读取(技能导入) | MIT |

Rust 端(`src-tauri/Cargo.toml`)依赖随 Tauri scaffold 生成的 `[dependencies]`。

---

## 十、测试策略(已冻结)

> 通用测试规范见 [05-testing-strategy](05-testing-strategy_测试策略.md),本节仅列桌面 App 特有路径。

| 路径 | 覆盖方式 |
|---|---|
| 配置读写 | Vitest 单测,Mock `tauri-plugin-store` |
| 启动探测 | Playwright + Tauri WebDriver 集成测 |
| 窗口行为 | 手动验收(无自动化,小屏机器拍屏) |
| 单实例 | CI 跑 bash 脚本双进程启动验证 |
| 自动更新 | Mock GitHub Releases,本地起 minio / `python -m http.server` 模拟 |
| 三平台打包 | `tauri build` 跑通即认为通过 |

**MVP 范围内不测项**:
- 跨进程 IPC 性能(依赖 Tauri 内部)
- 系统托盘菜单点击(OS 级,自动化 ROI 低)

---

## 十一、风险与缓解(已冻结)

| 风险 | 缓解 |
|---|---|
| macOS Gatekeeper 拦首次启动 | README 写"右键打开";v0.2 上 notarization |
| Windows Defender 误报 | 第一版自签 + 文档说明,第二版买签名证书 |
| WS 在 WebView 偶发断连 | 复用 web 端 WS 重连逻辑 |
| 三平台 CI 资源贵 | macos runner 仅 release 触发 |
| 用户不跑 backend 双击 App 空白 | §3.1 引导页 + 设置页 |
| Tauri 2 仍 RC 中(若) | 锁定具体小版本,跟踪 changelog,锁升级前先内部验证 |

---

## 十二、待 Review 项(PR-01 必须答完)

1. **Q5-1**:原生通知是否在 v0.1 范围?(建议降级 v0.2)
2. **Q5-2**:Web 端用户与桌面端用户身份是否打通?(建议走同一 JWT 体系,后端零改)
3. **Q7-1**:首次发布 tag 命名为 `v0.1.0-desktop-preview` 还是直接 `v0.1.0`?
4. **Q11-1**:遇到 Tauri 2 bug 时,降级方案是 Capacitor 还是 Electron?

---

## 十三、相关文档

| 文档 | 内容 |
|---|---|
| [ADR-0007](../../worklogs/decisions/0007-tauri-desktop-pivot.md) | 本规格依据的架构决策 |
| [worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md](../../worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md) | 决策讨论日志 |
| [01-architecture](01-architecture_架构定义.md) | 5 层洋葱(不修改) |
| [04-commands](04-commands_命令接口.md) | 后端 API(不修改) |
| [05-testing-strategy](05-testing-strategy_测试策略.md) | 测试通用规范 |

---

*草案 by: 黎 + Claude Agent.  待 2 人 Review Approve 后冻结 v1.0.*
