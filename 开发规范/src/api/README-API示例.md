# API 设计示例

> **👤 人类参考** | 对应规范：`conventions/04-api_API设计规范.md`
> 运行：`pip install fastapi uvicorn && uvicorn main:app --reload`

一个完整的 RESTful API 微服务，演示：
- URL 设计（资源名词 + HTTP 方法）
- 统一响应格式（code + message + data）
- 错误码体系
- 分页/排序/过滤
- 输入校验 + 白名单

运行后访问 http://localhost:8000/docs 查看交互式 API 文档。

## 契约校验（红线落地）

`.spectral.yaml` 把 URL 命名、禁动词、认证声明等红线写成 OpenAPI lint 规则（对应规范 §二）：

```bash
# 导出 schema 后 lint
python -c "import json,main; print(json.dumps(main.app.openapi()))" > openapi.json
npx @stoplight/spectral-cli lint openapi.json --ruleset src/api/.spectral.yaml
```
