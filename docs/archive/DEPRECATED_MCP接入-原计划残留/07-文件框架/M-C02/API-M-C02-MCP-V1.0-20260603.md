# 接口注释清单 API-M-C02-MCP-V1.0-20260603

> M-C02 K4 Analyzer 模块接口注释清单
> 覆盖 IC-009 K4Analyzer.Analyze / Calibrate（来自 DD-001）
> 来源 [DD-001:IC-009 + API-210 + MD-MCP-V1.0#M-C02]

---

## API-001 K4Analyzer.Analyze（对应 IC-009）

```
[接口编号] API-001
[关联契约] IC-009（来自DD-001）
[实现文件] src/agenthub/infrastructure/k4/grpc_server.py（K4Servicer.Analyze）
[调用方法] gRPC K4Analyzer.Analyze
[函数签名注释]
  ```python
  async def Analyze(
      request: K4AnalyzeRequest,    # [gRPC AnalyzeRequest]
      context: ServicerContext        # [gRPC ServicerContext]
  ) -> K4AnalyzeResponse:             # [gRPC AnalyzeResponse]
      """
      K4 gRPC Analyze RPC：静态分析 manifest.

      Args:
          request: gRPC AnalyzeRequest
              - manifest_json: bytes, 必填, manifest 字节流 (< 1MB)
              - rule_set_version: str, 必填, 规则集版本
              - trace_id: str, 必填, 追踪 ID
          context: gRPC ServicerContext（用于设置 status code 与 abort）

      Returns:
          gRPC AnalyzeResponse
              - score: int, 0-100 综合评分
              - tags: list[str], 风险标签集合
              - matches: list[MatchItem], 命中列表
              - rule_set_version: str, 实际生效版本
              - trace_id: str, 追踪 ID

      Raises:
          INVALID_ARGUMENT (gRPC 3): manifest 非法（不可解析/编码错误）
          RESOURCE_EXHAUSTED (gRPC 8): 队列满（>100）
          DEADLINE_EXCEEDED (gRPC 4): 超时（>10s）
          UNAVAILABLE (gRPC 14): gRPC 服务不可用 → 降级本地分析

      Example:
          >>> request = K4AnalyzeRequest(manifest_json=b"...", ...)
          >>> response = await servicer.Analyze(request, context)
          >>> assert response.score < 70
      """
  ```
[参数说明]
  参数1: manifest_json bytes 必填 < 1MB
  参数2: rule_set_version str 必填 规则集版本
  参数3: trace_id str 必填 UUID v4
[返回值说明]
  score: 综合评分（0=安全，100=极危险）
  tags: 风险标签集合（high_risk/warning/pass/...）
  matches: 命中列表（按 severity 降序）
  rule_set_version: 实际生效版本
  trace_id: 透传
[错误码说明]
  INVALID_ARGUMENT: manifest 不可解析
  RESOURCE_EXHAUSTED: 队列满，客户端重试
  DEADLINE_EXCEEDED: 单次 > 10s 超时
  UNAVAILABLE: gRPC 不可用，降级本地
[并发安全] 8 worker pool 并发；规则集 reload 时新请求走旧版本
[幂等性] 是；(manifest_hash, rule_set_version) → 缓存
[性能约束] P95 ≤ 10s/MCP
[来源标注] [DD-001:IC-009 + API-210]
```

---

## API-002 K4Analyzer.Calibrate（对应 IC-009）

```
[接口编号] API-002
[关联契约] IC-009（来自DD-001）
[实现文件] src/agenthub/infrastructure/k4/grpc_server.py（K4Servicer.Calibrate）
[调用方法] gRPC K4Analyzer.Calibrate
[函数签名注释]
  ```python
  async def Calibrate(
      request: K4CalibrateRequest,  # [gRPC CalibrateRequest]
      context: ServicerContext       # [gRPC ServicerContext]
  ) -> K4CalibrateResponse:         # [gRPC CalibrateResponse]
      """
      K4 gRPC Calibrate RPC：基于语料库校准规则集.

      Args:
          request: gRPC CalibrateRequest
              - rule_set_id: UUID, 必填
              - corpus_id: UUID, 必填
              - trace_id: str, 必填
          context: gRPC ServicerContext

      Returns:
          gRPC CalibrateResponse
              - rule_set_id: UUID
              - corpus_id: UUID
              - rule_metrics: dict[str, RuleMetrics]
              - overall_accuracy: float
              - generated_at: str (ISO8601)

      Raises:
          INVALID_ARGUMENT: rule_set_id 非法
          NOT_FOUND: corpus_id 不存在
      """
  ```
[参数说明]
  参数1: rule_set_id UUID 必填
  参数2: corpus_id UUID 必填
  参数3: trace_id str 必填
[返回值说明]
  rule_metrics: {rule_name: (precision, recall, f1)}
  overall_accuracy: 总体准确率（0-1）
  generated_at: 生成时间 ISO8601
[错误码说明]
  INVALID_ARGUMENT: 规则集 ID 非法
  NOT_FOUND: 语料库不存在
[并发安全] 校准期间 corpus 不可写
[幂等性] 是
[性能约束] P95 ≤ 30s
[来源标注] [DD-001:IC-009 + API-210]
```

---

## API-003 ASTAnalyzer.analyze（in-proc）

```
[接口编号] API-003
[关联契约] IC-009（in-proc 等价）
[实现文件] src/agenthub/infrastructure/k4/analyzer.py（ASTAnalyzer.analyze）
[函数签名注释]
  ```python
  def analyze(
      manifest_json: bytes,           # [manifest 字节流]
      trace_id: str | None = None      # [追踪 ID，缺省 UUID4]
  ) -> ScoreResult:                   # [综合评分结果]
      """
      模板方法入口：编排 parse→walk→score→tag.

      Args:
          manifest_json: manifest 字节流（< 1MB）
          trace_id: 追踪 ID，缺省自动生成

      Returns:
          ScoreResult：综合评分结果

      Raises:
          SyntaxError: manifest 不可解析
          UnicodeDecodeError: 编码错误
      """
  ```
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + IC-009 in-proc]
```

---

## API-004 CorpusCalibrator.calibrate（in-proc）

```
[接口编号] API-004
[关联契约] IC-009
[实现文件] src/agenthub/infrastructure/k4/corpus.py
[函数签名注释]
  ```python
  def calibrate(
      analyzer: ASTAnalyzer,           # [待校准分析器]
      rule_set_id: UUID,               # [规则集 ID]
      corpus_id: UUID                  # [语料库 ID]
  ) -> CalibrationReport:              # [校准报告]
      """
      对语料库执行校准，输出 precision/recall/F1.
      """
  ```
[来源标注] [DD-001:MD-MCP-V1.0#M-C02]
```

---

## API-005 RuleSetCache.reload（in-proc）

```
[接口编号] API-005
[关联契约] 无（in-proc 内部 API）
[实现文件] src/agenthub/infrastructure/k4/cache.py
[函数签名注释]
  ```python
  async def reload(self, new_version: str) -> None:
      """
      触发规则集热重载（双缓冲）.

      Args:
          new_version: 新规则集版本

      Raises:
          RuleLoadError: 加载失败时保留旧版本 + 告警
      """
  ```
[来源标注] [DD-M推断:依据 MD-MCP-V1.0#M-C02 状态机]
```

---

## 接口契约覆盖率

| 契约 | 实现 API | 注释状态 | 覆盖率 |
|------|---------|---------|--------|
| IC-009.Analyze | API-001 + API-003 | 完整 | 100% |
| IC-009.Calibrate | API-002 + API-004 | 完整 | 100% |

**[DD-M洞察-3]** IC-009 仅在 DD-001 中给出 gRPC 形态；DD-M 补充了 in-proc 形态 API-003/API-004 以便 M-B05.application.create.Saga 在同进程内调用，避免不必要的 gRPC 自调用开销。

**接口注释清单文档结束。**
