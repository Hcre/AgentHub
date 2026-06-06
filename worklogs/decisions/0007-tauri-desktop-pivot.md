# ADR-07: Web → 桌面 App 转向 Tauri 2 + 瘦客户端分发

> 日期:2026-06-06 | 状态:**Accepted** | 决策人:黎(Claude Agent 协助)
> 关联:[worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md](../黎/2026-06-06_讨论-web转桌面app可行性.md) · 即将落地的 `docs/specs/06-desktop-app_桌面App规格.md` · `worklogs/decisions/0001-cli-first-pivot.md` 共享的"CLI 优先"价值观

## 一、背景

AgentHub v0.x 已完成 web 化交付:FastAPI 后端 + React 19 + Vite + Tailwind 4 前端,5 层洋葱 + CLI 优先双轨 + Docker Compose 单机部署,在 web 端可用且功能持续迭代。

为面向 GitHub 开源社区扩大触达(开发者更愿意在桌面端"装一个"而非"启 docker"),2026-06-06 与 Claude Agent 集中讨论了"把现有项目从 web 搬到 app 的可行性"。本次 ADR 记录讨论中收口的所有决策及其依据。

讨论的核心前提(三条红线):
1. **后端不重写** —— 已投入的 5 层洋葱 / CLI 优先 / Docker 部署是 AgentHub 真正的壁垒,UI 不是
2. **面向 GitHub 开源** —— 意味着零安装摩擦、跨平台、贡献者门槛低、用户可"自下截自跑"而非经过商店审核
3. **零团队原生开发经验** —— 选型必须最简单、文档最多、社区最大

## 二、问题

需要回答三个问题:

1. 目标平台:移动端(iOS/Android)还是桌面端(macOS/Windows/Linux)?
2. 5 条候选技术路径中,哪条最适合"零经验 + 桌面端 + 开源"?
3. 桌面 App 与现有 FastAPI 后端如何耦合?是 App 自带 backend,还是 App 只装壳连用户已有 backend?

## 三、5 路径横向对比

| 方案 | 改造成本 | 性能 | 包体 | GitHub 生态 | 零经验友好 | 上手 1 个 release |
|---|---|---|---|---|---|---|
| A. **Capacitor** (套 WebView) | 极低 | 中 | 5-10MB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 3-4 周 |
| B. **Tauri 2** (WebView + Rust) | 低-中 | 高 | 3-5MB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 5-7 周(瘦客户端) |
| C. **React Native** 重写 UI | 高 | ⭐⭐⭐⭐⭐ | 20-30MB | ⭐⭐⭐⭐⭐ | ⭐⭐ | 12+ 周 |
| D. **Flutter** 重写 | 高(Dart) | ⭐⭐⭐⭐⭐ | 15-20MB | ⭐⭐⭐⭐ | ⭐⭐ | 12+ 周 |
| E. **PWA + TWA** | 极低 | 中 | 0 | ⭐⭐ | ⭐⭐⭐⭐ | 1 周(但 iOS 残废) |

**为什么排除 C/D(RN/Flutter 重写)**:5 层洋葱 + CLI 优先的核心资产全部在后端,前端 React 栈已是熟练域。重写 UI 是负 ROI,且把"贡献者门槛"从"懂 React 即可"拉高到"懂 React + RN/Flutter"。

**为什么不选 PWA/TWA**:开源 App 上架需要 iOS App Store / Play Store 原生包,PWA 在 iOS 至今残废(iOS Push / 后台同步 / 安装体验都不达标)。

**Capacitor vs Tauri 抉择**:Capacitor 在"零经验友好"和"GitHub 生态"两项胜出,但 Tauri 2 在"包体 + 性能"两项数量级胜出(Electron 100MB → Tauri 3MB)。AgentHub 已经有 FastAPI + Postgres + Redis 在吃内存,前端壳不应该再叠 100MB Chromium。最终选 Tauri 2。

## 四、决策

### 4.1 第一轮决策:目标平台 + UI 改造度(AskUserQuestion 收口)

| 决策 | 选定 | 否决 |
|---|---|---|
| 目标平台 | **桌面 App(macOS / Windows / Linux)** | iOS/Android 移动端、桌面+移动全都要 |
| UI 改造度 | **保持现有 React 资产,三栏布局直接搬** | 重写移动端专用 UI、只做适配(MVP) |

**理由**:现有 LeftPanel / CenterPanel / RightPanel 三栏布局本就是为桌面设计,搬到桌面端是 1:1 还原,零改造。引入移动端意味着重排 + 双套代码,违背"后端才是壁垒"的判断。

### 4.2 第二轮决策:后端耦合方式(3 选 1)

| 模式 | 描述 | 包体 | 上手 release | 否决理由 |
|---|---|---|---|---|
| M1. **Sidecar** | App 启动 spawn 本地 FastAPI 进程,内嵌 Postgres/Redis | ~200MB+ | 8-12 周 | 包体过大,签名复杂,违反"瘦客户端"价值观 |
| M2. **瘦客户端** | App 只装壳,连用户自部署的 backend | ~3-5MB | **5-7 周** ✓ | - |
| M3. **全栈换骨** | 后端 FastAPI 迁 Rust(Tauri 后端),DB 换 SQLite | ~10MB | 16+ 周 | **重写后端,违反 [ADR-0001](0001-cli-first-pivot.md) CLI 优先,完全否决** |

**选定 M2 瘦客户端**。具体形态:
- App 启动时探测 `http://localhost:8000/health`
- 设置页可填 backend URL(局域网 / 远程都可)
- JWT 存 Tauri secure storage(`tauri-plugin-store`)
- 用户部署体验和现状完全一致:`docker compose up` 起 backend,装 App 连本地

### 4.3 第三轮决策:分发渠道(3 选 1)

| 渠道 | 费用 | 门槛 | 选定 |
|---|---|---|---|
| GitHub Releases 自下载(.dmg / .exe / .AppImage) | 0 | 0 | ✓ |
| + Mac App Store | ¥688/年 + 审核 | 中 | ✗ |
| + 三商店全上 | 高 + 包跡合规 | 高 | ✗ |

**只走 GitHub Releases**。理由:开源早期,商店审核会拖慢迭代节奏 + 增加包跡合规风险;GitHub Releases 配合 `tauri-action` 自动发布是开源项目天然分发渠道。

### 4.4 最终方案汇总

```
平台:    macOS / Windows / Linux 桌面 App
壳:      Tauri 2.x
后端:    瘦客户端 — App 不带 backend,连用户自部署的 FastAPI
分发:    GitHub Releases 自下载(.dmg / .exe / .AppImage),不进任何商店
UI:      100% 复用现有 React 资产,三栏布局直接搬
后端:    零修改 — 5 层洋葱 / CLI 优先 / Docker Compose 全部保留
```

## 五、落地路径与工作量(M2 模式校准后)

| 阶段 | 内容 | 估时 | 阻塞 |
|---|---|---|---|
| 0. 决策冻结 | 本 ADR + docs/specs/06-desktop-app 规格 + STATUS.md 同步 | 1-2 天 | 等 PR-01 spec 2 人 Review |
| 1. Tauri 套壳 Hello World | `npm create tauri-app` 引入 Vite,AppShell 直接复用,设置页加 backend URL 输入 | 1 周 | - |
| 2. Backend 连接 + 鉴权 | 启动 health 探测、动态 baseURL(fetch / WS 拦截)、`tauri-plugin-store` 存 JWT | 1 周 | - |
| 3. 原生体验 | 系统托盘 + 单实例 + 原生通知 + 应用菜单 + 跟随系统深色 | 1-2 周 | - |
| 4. 自动更新 | Tauri Updater 集成 + GitHub Releases 签名 | 1 周 | - |
| 5. 打包 + 文档 | 三平台产物,README 加"桌面版"段,首发 v0.1.0 | 1-2 周 | - |

**总计:5-7 周到第一个公开 release**(比 M1 Sidecar 模式省 3-5 周)。

## 六、后果

### 6.1 正面

- **包体小 ~3-5MB** vs Electron 100MB+ vs Capacitor 50-80MB,下载即用,符合开源"零安装摩擦"
- **后端零修改** — 9 个 router / WS / mcp / skills / memory 全部沿用,2 年的工程积累不被背叛
- **零经验友好** — Tauri scaffold 出的 Rust 代码 80% 不用改,卡住就 GitHub issue / Discord
- **跨平台** — macOS / Windows / Linux 三端 GitHub Actions matrix,CI 一次配齐
- **CLI 优先价值观延续** — App 是"用户访问已有 backend 的另一种形态",而不是另一个平行产品

### 6.2 负面(已知负债)

- **macOS Gatekeeper 拦首次启动** — 未签名的 .dmg 双击会被系统拦,需 README 写"右键打开"步骤
- **Windows Defender 误报** — 未签名的 .exe / .msi 高概率被杀软标,需 v0.2 买 Authenticode 证书
- **WS 在 Tauri WebView 偶发断连** — 需加自动重连,与 web 端复用同一份重连逻辑
- **三平台打包 CI 资源贵** — macOS runner 是 GitHub Actions 最贵的,只在 release 时跑
- **backend 分离部署体验** — 用户必须同时装 backend + App,首启失败率高(空白页 + 困惑)

### 6.3 缓解措施

| 负债 | 缓解 |
|---|---|
| macOS Gatekeeper | README 写明"右键 → 打开",后续 v0.2 上 notarization |
| Windows Defender | 第一版自签 + 文档说明,第二版买签名证书 |
| WS 断连 | 复用 web 端 WS 重连逻辑(`docs/specs/04-commands` §WS 段) |
| CI 成本 | macos-13 旧 runner,只在 tag release 时跑 mac 矩阵 |
| 首启空白页 | 启动 health 探测失败 → 显示"请先 docker compose up"教程卡片 + 设置页引导填 URL |

## 七、与现有 ADR 的关系

| 现有 ADR | 关系 |
|---|---|
| [ADR-0001](0001-cli-first-pivot.md) CLI 优先 | **共享价值观** — App 是"访问 backend 的另一种形态",不引入平行运行时 |
| [ADR-0002](0002-phase1-long-running-cli.md) | 不冲突 — 长驻 CLI 仍跑在用户后端,App 只是 WebView 壳 |
| [ADR-0003~0006](0003-mcp-url-prefix-and-ap05-deferral.md) MCP 系列 | 不冲突 — App 通过标准 HTTP/WS 访问现有 MCP endpoint |
| (待写) `docs/specs/06-desktop-app` | **本 ADR 的落地规格** — 冻结 backend URL 配置 / 窗口行为 / 单实例 / 托盘 / 自动更新,等 PR-01 2 人 Review |

## 八、相关文档

| 文档 | 内容 |
|---|---|
| `worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md` | 本次讨论的工作日志(给下一位的交接) |
| `docs/specs/06-desktop-app_桌面App规格.md`(即将落地) | 桌面 App 规格(冻结接口,供 PR-01 Review) |
| `docs/specs/01-architecture_架构定义.md` | 5 层洋葱(本 ADR 不修改) |
| `docs/specs/04-commands_命令接口.md` | 后端 9 个 router(本 ADR 不修改) |
| [Tauri 2 官方文档](https://tauri.app/v2/) | 技术参考 |

---

*Decision by: 黎 (DRI).  Reviewer: 待 PR-01 spec 2 人 Review 通过后正式生效.*
