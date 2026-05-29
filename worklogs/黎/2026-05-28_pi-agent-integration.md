# Pi Agent 接入 + API Key Manager

日期: 2026-05-28

## 完成

- [x] Pi Agent 适配器 PiAgentRuntime（pi --mode rpc JSONL 协议）
- [x] AgentSystem.PI_AGENT 枚举 + 工厂路由
- [x] Pi Agent 代理模式：ClaudeAdapter → AgentHub Proxy → DeepSeek
- [x] ClaudeAdapter 支持 base_url 参数
- [x] redis_client 开发环境 fakeredis fallback
- [x] ApiKeyStore (localStorage persist) + ApiKeyManager 页面
- [x] Dialog 组件 createPortal 修复侧边栏卡住
- [x] DeepSeek API key 端到端验证通过
- [x] Docker 部署验证：喵娘 agent 正常对话
- [x] 分支合并：api-key-manager + main 开发规范

## 给下一位的交接

- Pi Agent 当前使用 ClaudeAdapter + proxy 模式（Pi CLI 在 Windows 下有网络问题）
- 如果要在 Linux/Mac 上用真正的 Pi CLI，改 factory.py 中 proxy_base 为 "" 即可
- API Key Manager 存在浏览器 localStorage，创建 Agent 时可选择已保存的 key
