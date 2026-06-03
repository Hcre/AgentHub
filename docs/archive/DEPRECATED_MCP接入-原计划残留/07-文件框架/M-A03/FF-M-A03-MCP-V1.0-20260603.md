# 文件框架结构 FF-M-A03-MCP-V1.0-20260603

> 负责模块：M-A03 Webhook Receiver
> 设计模式：Chain of Responsibility（HMAC 验签 → 重放校验 → 异步入队）
> 来源：[DD-001:FS-003 + MD-M-A03 + IC-003]

---

## 1. 模块文件结构

```
[模块编号] M-A03
[模块名称] Webhook Receiver
[文件框架]
  src/agenthub/access/webhook/
    __init__.py                  ← [职责：模块初始化，导出公共接口]
    app.py                       ← [职责：WebhookApp FastAPI 独立端口入口（Chain 编排）]
      - [类注释: WebhookApp]
      - [类注释: WebhookAck]
    exceptions.py                ← [职责：领域异常定义]
      - [类注释: WebhookError / HMACMismatchError / ReplayDetected / EnqueueError]
    verifiers/
      __init__.py                ← [职责：verifiers 子包导出]
      base.py                    ← [职责：HMACVerifier ABC + verify_hmac 工具]
        - [类注释: HMACVerifier]
        - [函数注释: verify_hmac]
      github.py                  ← [职责：GitHubVerifier 实现]
        - [类注释: GitHubVerifier]
      gitlab.py                  ← [职责：GitLabVerifier 实现]
        - [类注释: GitLabVerifier]
      bitbucket.py               ← [职责：BitbucketVerifier 实现]
        - [类注释: BitbucketVerifier]
    replay_guard.py              ← [职责：5min 窗口 nonce + timestamp 重放检测]
      - [类注释: ReplayGuard]
    enqueuer.py                  ← [职责：arq 异步入队 + 重试]
      - [类注释: Enqueuer]
    tests/
      __init__.py                ← [职责：测试包初始化]
      test_app.py                ← [职责：WebhookApp 集成测试 8 场景]
        - [测试场景1: 有效签名 → 200]
        - [测试场景2: 伪造签名 → 401]
        - [测试场景3: 重放 → 409]
        - [测试场景4: arq 失败 → 503]
        - [测试场景5: 未知 source → 404]
        - [测试场景6: 时钟漂移 → 409]
        - [测试场景7: payload 超限 → 413]
        - [测试场景8: 幂等重发 → 同 ack]
      test_verifiers.py          ← [职责：Verifier 单元测试 9 场景]
      test_replay_guard.py       ← [职责：ReplayGuard 单元测试 5 场景]
      test_enqueuer.py           ← [职责：Enqueuer 单元测试 4 场景]

[文件间依赖关系]
  app.py → verifiers/{base,github,gitlab,bitbucket}.py → base.verify_hmac
  app.py → replay_guard.py → M-D03 (Redis)
  app.py → enqueuer.py → arq
  app.py → exceptions.py
  __init__.py → {app, verifiers, replay_guard, enqueuer, exceptions}
  tests/ → 被测试文件
  无循环依赖；分层 app → 子模块

[来源标注] [DD-001:FS-003 + MD-M-A03]
```

---

## 2. 框架深度阶梯

| 阶梯 | 退出条件 | 状态 |
|------|---------|------|
| L0 分配模块识别 | M-A03 已分类、FS-003 已识别、D1 ≥ 70 | ✓ |
| L1 文件结构创建 | 13 个文件已创建、命名合规、D2 ≥ 70 | ✓ |
| L2 注释编写 | F3/F4/F4.5/F5 全部完成、D3 ≥ 80、D4 ≥ 80 | ✓ |
| L3 风格检查+自评审 | 风格合规、自评审通过、D5 ≥ 80、D6 ≥ 60 | ✓ |

---

## 3. 模块边界守护

| 项 | 数值 |
|----|------|
| 负责模块 | M-A03 |
| 操作文件数 | 13 |
| 跨模块文件数 | 0 |
| D7 状态 | 合规（100%） |

---

## 4. 注释 100% 覆盖清单

| 文件 | 文件头注释 | 类注释 | 函数注释 | 测试场景注释 |
|------|----------|--------|---------|------------|
| __init__.py | ✓ | - | - | - |
| app.py | ✓ | ✓ 2 | ✓ | - |
| exceptions.py | ✓ | ✓ 4 | - | - |
| verifiers/__init__.py | ✓ | - | - | - |
| verifiers/base.py | ✓ | ✓ 1 | ✓ 1 | - |
| verifiers/github.py | ✓ | ✓ 1 | ✓ 1 | - |
| verifiers/gitlab.py | ✓ | ✓ 1 | ✓ 1 | - |
| verifiers/bitbucket.py | ✓ | ✓ 1 | ✓ 1 | - |
| replay_guard.py | ✓ | ✓ 1 | ✓ 2 | - |
| enqueuer.py | ✓ | ✓ 1 | ✓ 1 | - |
| tests/__init__.py | ✓ | - | - | - |
| tests/test_app.py | ✓ | - | - | ✓ 8 场景 |
| tests/test_verifiers.py | ✓ | - | - | ✓ 9 场景 |
| tests/test_replay_guard.py | ✓ | - | - | ✓ 5 场景 |
| tests/test_enqueuer.py | ✓ | - | - | ✓ 4 场景 |

[来源标注] [DD-001:FS-003 + MD-M-A03]
