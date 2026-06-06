"""5 个 Core User Story 的 Seed 数据构造函数。

P0-6（roadmap §8.4）：
- S1: 新建会话 → 1v1 流式 → 代码块（1 agent + 1 session + 5 messages）
- S2: 群聊 → @协调者 → 多 Agent 并行（1 group + 4 agents + 6 messages）
- S3: 产物内联预览（1 session + 4 messages: html / diff / URL）
- S4: 自建 Agent（5 agents + 1 session with custom）
- S5: Inbox 审批 + 任务看板（2 inbox + 2 tasks）

设计要点：
- 每个 ORM 对象都打上 ``demo_tag`` (settings JSON 字段或 extra 字段)，便于幂等清理
- ``InboxItem`` 当前 schema 不存在，落地到 ``NotificationModel``：
  category='inbox_approval' (待审) / 'inbox_approved' (已通过)
- 用户/工作区用硬编码 demo user uuid
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import (
    AgentModel,
    GroupMemberModel,
    GroupModel,
    MessageModel,
    NotificationModel,
    SessionModel,
    TaskModel,
)

# 标识："这是 demo seed 插入的" — 用于幂等清理
DEMO_TAG = "demo_p0_6"

# 硬编码的 demo user uuid（与生产 JWT sub 保持 UUID 形态，避免 NOT NULL 约束）
DEMO_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

# 工作目录（避免硬编码 Windows 路径，落到 cwd）
DEMO_WORKSPACE = ""


def _now() -> datetime:
    return datetime.now(UTC)


def _ts(seconds_offset: int = 0) -> datetime:
    """返回相对当前时间的偏移时间戳，用于控制消息顺序。"""
    from datetime import timedelta

    return _now() + timedelta(seconds=seconds_offset)


# ============================================================================
# S1: 新建会话 → 1v1 流式 → 代码块
# ============================================================================


async def create_story_1(db: AsyncSession) -> dict:
    """S1: 1v1 流式对话，含 tsx 代码块。

    数据：1 agent (claude_code) + 1 session + 5 messages (含 ```tsx``` 围栏)
    """
    claude = AgentModel(
        id=uuid4(),
        name="Claude",
        avatar="🤖",
        role="通用编程助手（CLI · Claude Code）",
        agent_system="claude_code",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        status="online",
        is_system=False,
        skills=["code_review", "refactor", "test_gen"],
        capability_tags=["code", "ts", "react"],
        system_prompt="你是一位资深前端工程师，擅长 TypeScript / React 重构。",
        settings={"demo_tag": DEMO_TAG, "story": "S1"},
    )
    db.add(claude)
    await db.flush()

    session = SessionModel(
        id=uuid4(),
        type="private",
        title="S1 - 重构 pricing 页",
        agent_id=claude.id,
        workspace_path=DEMO_WORKSPACE,
    )
    db.add(session)
    await db.flush()

    # 5 条消息：user 提需求 / agent 流式回 3 段（拆为 3 条模拟分片）/ user 确认
    messages = [
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content="帮我把 pricing 页的卡片组件从 class component 重构成 hooks + tsx。",
            content_type="text",
            status="completed",
            created_at=_ts(0),
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=claude.id,
            content=(
                "好的，我先看一下当前实现，再给你重构后的版本。"
                "（第一段：读取现有文件结构）"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(2),
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=claude.id,
            content=(
                "（第二段：分析问题）\n\n"
                "原版是 ClassComponent + lifecycle，每加一个 prop 都要改 constructor。"
                "建议改成函数组件 + useState，把 prop 直接当参数传。"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(4),
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=claude.id,
            content=(
                "（第三段：重构后代码）\n\n"
                "```tsx\n"
                "import { useState } from 'react';\n"
                "\n"
                "export interface PricingCardProps {\n"
                "  title: string;\n"
                "  price: number;\n"
                "  highlight?: boolean;\n"
                "}\n"
                "\n"
                "export function PricingCard({ title, price, highlight = false }: PricingCardProps) {\n"
                "  const [subscribed, setSubscribed] = useState(false);\n"
                "\n"
                "  return (\n"
                "    <div className={highlight ? 'card card--hl' : 'card'}>\n"
                "      <h3>{title}</h3>\n"
                "      <p>${price}/月</p>\n"
                "      <button onClick={() => setSubscribed(true)} disabled={subscribed}>\n"
                "        {subscribed ? '已订阅' : '订阅'}\n"
                "      </button>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
                "```\n\n"
                "已替换原 class 版本，行为等价。"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(6),
            extra={"demo_tag": DEMO_TAG, "language": "tsx"},
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content="好的，我直接用这个版本，CI 通过了。",
            content_type="text",
            status="completed",
            created_at=_ts(8),
        ),
    ]
    for m in messages:
        db.add(m)

    await db.flush()
    return {
        "agents": [claude],
        "sessions": [session],
        "messages": messages,
    }


# ============================================================================
# S2: 群聊 → @协调者 → 多 Agent 并行
# ============================================================================


async def create_story_2(db: AsyncSession) -> dict:
    """S2: 群聊 + @协调者 + 3 个 Agent 并行回复 + 合并汇报。

    数据：1 group + 4 agents (coordinator + 3 workers) + 6 messages
    """
    # 协调者（先建，用于 group.coordinator_id）
    coordinator = AgentModel(
        id=uuid4(),
        name="Coordinator",
        avatar="🧭",
        role="任务拆解与协调者",
        agent_system="claude_code",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        status="online",
        is_system=True,
        skills=["planning", "task_decomposition", "routing"],
        capability_tags=["orchestration"],
        system_prompt="你是群聊协调者，负责拆解任务并分派到合适的 Agent。",
        settings={"demo_tag": DEMO_TAG, "story": "S2", "role": "coordinator"},
    )
    db.add(coordinator)
    await db.flush()

    claude = AgentModel(
        id=uuid4(),
        name="Claude (S2)",
        avatar="🤖",
        role="代码与文案",
        agent_system="claude_code",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        status="online",
        skills=["code", "copy"],
        capability_tags=["code", "copy"],
        settings={"demo_tag": DEMO_TAG, "story": "S2", "role": "worker"},
    )
    opencode = AgentModel(
        id=uuid4(),
        name="OpenCode (S2)",
        avatar="⌨️",
        role="代码生成与重构",
        agent_system="opencode",
        provider="deepseek",
        model="deepseek-v3",
        status="online",
        skills=["code_gen", "refactor"],
        capability_tags=["code"],
        settings={"demo_tag": DEMO_TAG, "story": "S2", "role": "worker"},
    )
    mockbot = AgentModel(
        id=uuid4(),
        name="MockBot (S2)",
        avatar="🎭",
        role="占位回显（Demo 用）",
        agent_system="mock",
        provider="system",
        model="mock-1",
        status="online",
        skills=["echo"],
        capability_tags=["demo"],
        settings={"demo_tag": DEMO_TAG, "story": "S2", "role": "worker"},
    )
    db.add_all([claude, opencode, mockbot])
    await db.flush()

    group = GroupModel(
        id=uuid4(),
        name="S2 - 营销页升级",
        description="营销页 v2 升级：文案 / 代码 / 测试并行。",
        coordinator_id=coordinator.id,
        coordinator_config={"dispatch_mode": "at_routing"},
    )
    db.add(group)
    await db.flush()

    for agent_id in [claude.id, opencode.id, mockbot.id]:
        db.add(GroupMemberModel(group_id=group.id, agent_id=agent_id))
    await db.flush()

    session = SessionModel(
        id=uuid4(),
        type="group",
        title="S2 - 营销页升级",
        group_id=group.id,
        workspace_path=DEMO_WORKSPACE,
    )
    db.add(session)
    await db.flush()

    messages = [
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content=(
                "@Coordinator 这次要升级营销页：1) 重写 Hero 文案 2) "
                "重做 Pricing 卡片组件 3) 加 E2E 测试。麻烦拆解后分派给 @Claude @OpenCode @MockBot。"
            ),
            content_type="text",
            mentions=["Coordinator", "Claude", "OpenCode", "MockBot"],
            status="completed",
            created_at=_ts(0),
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=coordinator.id,
            content=(
                "已拆解为 3 个子任务，并行执行：\n"
                "- @Claude (S2) → Hero 文案 v2\n"
                "- @OpenCode (S2) → Pricing 卡片组件重构\n"
                "- @MockBot (S2) → E2E 测试桩\n\n预计 2 分钟后合并汇报。"
            ),
            content_type="text",
            mentions=["Claude", "OpenCode", "MockBot"],
            status="completed",
            created_at=_ts(2),
            extra={"demo_tag": DEMO_TAG, "role": "coordinator"},
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=claude.id,
            content=(
                "Hero 文案 v2 已交付：\n\n"
                "**主标题**：让 AI 真正进入你的工作流\n"
                "**副标题**：4 CLI 适配器 + 统一记忆，复杂任务秒级拆解。\n"
                "**CTA**：免费试用 14 天"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(10),
            extra={"demo_tag": DEMO_TAG, "deliverable": "copy"},
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=opencode.id,
            content=(
                "Pricing 卡片组件重构完成。新增 `PricingCard.tsx` (function component + "
                "TypeScript)，已替换原 class 版本。\n\n下一步：等测试桩。"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(15),
            extra={"demo_tag": DEMO_TAG, "deliverable": "code"},
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=mockbot.id,
            content=(
                "E2E 测试桩就绪：`tests/e2e/pricing.spec.ts`\n"
                "覆盖 3 个用例：1) 卡片渲染 2) 高亮态切换 3) 订阅按钮禁用态。"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(20),
            extra={"demo_tag": DEMO_TAG, "deliverable": "test"},
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=coordinator.id,
            content=(
                "**合并汇报**：✅ 3/3 子任务完成。\n\n"
                "| 任务 | 负责人 | 状态 |\n|------|--------|------|\n"
                "| Hero 文案 v2 | @Claude (S2) | ✅ |\n"
                "| Pricing 卡片重构 | @OpenCode (S2) | ✅ |\n"
                "| E2E 测试桩 | @MockBot (S2) | ✅ |\n\n"
                "建议下一步：跑 `pnpm test:e2e` 全量回归。"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(25),
            extra={"demo_tag": DEMO_TAG, "role": "coordinator", "summary": True},
        ),
    ]
    for m in messages:
        db.add(m)

    await db.flush()
    return {
        "agents": [coordinator, claude, opencode, mockbot],
        "groups": [group],
        "sessions": [session],
        "messages": messages,
    }


# ============================================================================
# S3: 产物内联预览
# ============================================================================


async def create_story_3(db: AsyncSession) -> dict:
    """S3: 产物内联预览（HTML / Diff / URL 链接）。

    数据：1 session + 4 messages（含 ```html 围栏 + ```diff 围栏 + URL 链接）
    共用 S1 的 Claude agent，避免再造一个；找不到则创建一个。
    """
    # 复用 S1 的 Claude：按 name 查
    from sqlalchemy import select

    result = await db.execute(
        select(AgentModel).where(AgentModel.name == "Claude", AgentModel.is_deleted.is_(False))
    )
    claude = result.scalar_one_or_none()
    if claude is None:
        claude = AgentModel(
            id=uuid4(),
            name="Claude",
            avatar="🤖",
            role="通用编程助手（CLI · Claude Code）",
            agent_system="claude_code",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            settings={"demo_tag": DEMO_TAG, "story": "S3"},
        )
        db.add(claude)
        await db.flush()

    session = SessionModel(
        id=uuid4(),
        type="private",
        title="S3 - 提案预览",
        agent_id=claude.id,
        workspace_path=DEMO_WORKSPACE,
    )
    db.add(session)
    await db.flush()

    messages = [
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content="把上次的提案生成一个 HTML 预览页，并对比新旧两版差异。",
            content_type="text",
            status="completed",
            created_at=_ts(0),
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=claude.id,
            content=(
                "已生成 HTML 预览（落地到 /workspace/proposal.html）：\n\n"
                "```html\n"
                "<!doctype html>\n"
                '<html lang="zh">\n'
                "  <head>\n"
                '    <meta charset="utf-8" />\n'
                "    <title>AgentHub 提案 v2</title>\n"
                "  </head>\n"
                "  <body>\n"
                '    <h1>AgentHub · Demo 提案 v2</h1>\n'
                '    <p>CLI 适配器 + 协调者 + 产物预览 = 一站式多 Agent 平台。</p>\n'
                '    <button>立即试用</button>\n'
                "  </body>\n"
                "</html>\n"
                "```\n\n"
                "在线预览：https://agenthub-demo.example.com/proposal-v2.html"
            ),
            content_type="preview_card",
            status="completed",
            created_at=_ts(3),
            extra={
                "demo_tag": DEMO_TAG,
                "preview_url": "https://agenthub-demo.example.com/proposal-v2.html",
                "language": "html",
            },
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=claude.id,
            content=(
                "新旧版本差异：\n\n"
                "```diff\n"
                "--- proposal.v1.html\n"
                "+++ proposal.v2.html\n"
                "@@ -1,7 +1,9 @@\n"
                " <!doctype html>\n"
                ' <html lang="zh">\n'
                '   <head>\n'
                '-    <title>AgentHub 提案</title>\n'
                '+    <title>AgentHub 提案 v2</title>\n'
                "+    <meta name=\"description\" content=\"多 Agent 协作平台\" />\n"
                "   </head>\n"
                "   <body>\n"
                '-    <h1>AgentHub</h1>\n'
                '+    <h1>AgentHub · Demo 提案 v2</h1>\n'
                "-    <p>AI 协作平台。</p>\n"
                "+    <p>CLI 适配器 + 协调者 + 产物预览 = 一站式多 Agent 平台。</p>\n"
                "+    <button>立即试用</button>\n"
                "   </body>\n"
                " </html>\n"
                "```"
            ),
            content_type="diff",
            status="completed",
            created_at=_ts(6),
            extra={"demo_tag": DEMO_TAG, "language": "diff"},
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content=(
                "看起来不错。我把链接 https://agenthub-demo.example.com/proposal-v2.html "
                "发给老板过目。"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(9),
            extra={"demo_tag": DEMO_TAG, "contains_url": True},
        ),
    ]
    for m in messages:
        db.add(m)

    await db.flush()
    return {
        "agents": [claude],
        "sessions": [session],
        "messages": messages,
    }


# ============================================================================
# S4: 自建 Agent
# ============================================================================


async def create_story_4(db: AsyncSession) -> dict:
    """S4: 自建 Agent + 与之对话。

    数据：5 agents (4 预设 + 1 自建) + 1 session (与自建 Agent 对话)
    """
    # 4 预设 Agent
    claude = AgentModel(
        id=uuid4(),
        name="Claude (S4)",
        avatar="🤖",
        role="通用编程助手",
        agent_system="claude_code",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        settings={"demo_tag": DEMO_TAG, "story": "S4", "role": "preset"},
    )
    opencode = AgentModel(
        id=uuid4(),
        name="OpenCode (S4)",
        avatar="⌨️",
        role="代码生成与重构",
        agent_system="opencode",
        provider="deepseek",
        model="deepseek-v3",
        settings={"demo_tag": DEMO_TAG, "story": "S4", "role": "preset"},
    )
    pibot = AgentModel(
        id=uuid4(),
        name="Pi (S4)",
        avatar="π",
        role="多 Provider 适配",
        agent_system="pi_agent",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        settings={"demo_tag": DEMO_TAG, "story": "S4", "role": "preset"},
    )
    codexbot = AgentModel(
        id=uuid4(),
        name="Codex (S4)",
        avatar="📦",
        role="OpenAI Codex CLI",
        agent_system="codex",
        provider="openai",
        model="gpt-5",
        settings={"demo_tag": DEMO_TAG, "story": "S4", "role": "preset"},
    )
    # 1 自建 Agent（system_prompt 由用户自定义）。
    # agent_system 用 mock 避免 anthropic_api 模式强校验 api_key——自建演示重点是 system_prompt
    mybot = AgentModel(
        id=uuid4(),
        name="MyBot",
        avatar="✍️",
        role="营销文案专家（自建）",
        agent_system="mock",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        is_system=False,
        skills=["copywriting", "marketing"],
        capability_tags=["copy", "marketing"],
        system_prompt="你是营销文案专家，专注于 4 CLI 适配器平台的卖点提炼。",
        settings={"demo_tag": DEMO_TAG, "story": "S4", "role": "user_built"},
    )
    db.add_all([claude, opencode, pibot, codexbot, mybot])
    await db.flush()

    # 与自建 Agent 对话的 session
    session = SessionModel(
        id=uuid4(),
        type="private",
        title="S4 - 与 MyBot 试用",
        agent_id=mybot.id,
        workspace_path=DEMO_WORKSPACE,
    )
    db.add(session)
    await db.flush()

    messages = [
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content="你好，我刚自建了你（MyBot · 营销文案专家）。先给我 3 句 Hero 备选。",
            content_type="text",
            status="completed",
            created_at=_ts(0),
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=mybot.id,
            content=(
                "收到～我的定位是营销文案，3 句 Hero 备选：\n\n"
                "1. **多 Agent 协作，一句话搞定**\n"
                "2. **4 CLI 适配器，把每个 AI 拉进你的工作流**\n"
                "3. **让 AI 真正成为你的团队成员**\n\n"
                "需要更短版本或英文版随时说。"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(3),
            extra={"demo_tag": DEMO_TAG, "agent_role": "user_built"},
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content="第 2 句好，就用它。请把它压到 12 字以内。",
            content_type="text",
            status="completed",
            created_at=_ts(6),
        ),
        MessageModel(
            id=uuid4(),
            session_id=session.id,
            role="assistant",
            sender_agent_id=mybot.id,
            content=(
                "压到 12 字：**4 CLI 适配器，AI 进工作流**（9 个字）\n\n"
                "或者更激进：**AI 团队，秒级上线**（8 个字）"
            ),
            content_type="text",
            status="completed",
            created_at=_ts(9),
            extra={"demo_tag": DEMO_TAG, "agent_role": "user_built"},
        ),
    ]
    for m in messages:
        db.add(m)

    await db.flush()
    return {
        "agents": [claude, opencode, pibot, codexbot, mybot],
        "sessions": [session],
        "messages": messages,
    }


# ============================================================================
# S5: Inbox 审批 + 任务看板
# ============================================================================


async def create_story_5(db: AsyncSession) -> dict:
    """S5: Inbox 审批 + 任务看板。

    数据：2 inbox items (1 待审 + 1 已通过) + 2 tasks (1 done + 1 in_progress)

    说明：schema 当前无 InboxItem 模型；按 spec 落地到 NotificationModel。
    - category='inbox_approval' → 待审
    - category='inbox_approved' → 已通过
    """
    inbox_pending = NotificationModel(
        id=uuid4(),
        user_id=DEMO_USER_ID,
        category="inbox_approval",
        title="【待审】S2 协调者请求：合并 3 个子任务交付",
        content=(
            "Coordinator 已合并 S2 群聊的 3 个子任务交付（Hero 文案 / Pricing 重构 / "
            "E2E 测试桩）。点击查看详情并确认是否通过。"
        ),
        is_read=False,
        action_url="/inbox/s2-summary",
    )
    inbox_approved = NotificationModel(
        id=uuid4(),
        user_id=DEMO_USER_ID,
        category="inbox_approved",
        title="【已通过】S1 Claude 重构 Pricing 卡片组件",
        content=(
            "Claude 已完成 Pricing 卡片组件 class→hooks 重构，CI 全绿。"
            "已于 14:32 由你审批通过。"
        ),
        is_read=True,
        action_url="/inbox/s1-approved",
    )
    db.add_all([inbox_pending, inbox_approved])
    await db.flush()

    # 2 任务：1 done + 1 in_progress
    task_done = TaskModel(
        id=uuid4(),
        title="S1 重构 Pricing 卡片组件（class → hooks）",
        description=(
            "把 ClassComponent 重构为函数组件 + useState + TypeScript，"
            "保证行为等价，CI 全绿。"
        ),
        status="completed",
        priority="high",
        assignee_id=None,  # 关联到 Claude 的话需要查 agent；此处演示用 None
        assignee_type="agent",
        tags=["refactor", "react", "ts"],
        source="chat",
        retry_count=0,
    )
    task_inprogress = TaskModel(
        id=uuid4(),
        title="S2 营销页 v2 升级（Hero / Pricing / E2E）",
        description="3 个子任务并行，合并后回归全量。",
        status="running",
        priority="high",
        assignee_id=None,
        assignee_type="group",
        tags=["marketing", "e2e", "refactor"],
        source="chat",
        retry_count=0,
    )
    db.add_all([task_done, task_inprogress])
    await db.flush()

    return {
        "inbox": [inbox_pending, inbox_approved],
        "tasks": [task_done, task_inprogress],
    }


# ============================================================================
# 全部 5 个 story 的顺序执行入口
# ============================================================================


async def create_all_stories(db: AsyncSession) -> dict:
    """按 S1→S2→S3→S4→S5 顺序创建所有 demo 数据。"""
    result = {
        "agents": [],
        "sessions": [],
        "messages": [],
        "groups": [],
        "inbox": [],
        "tasks": [],
    }

    r1 = await create_story_1(db)
    result["agents"].extend(r1.get("agents", []))
    result["sessions"].extend(r1.get("sessions", []))
    result["messages"].extend(r1.get("messages", []))

    r2 = await create_story_2(db)
    result["agents"].extend(r2.get("agents", []))
    result["sessions"].extend(r2.get("sessions", []))
    result["messages"].extend(r2.get("messages", []))
    result["groups"].extend(r2.get("groups", []))

    r3 = await create_story_3(db)
    result["agents"].extend(r3.get("agents", []))
    result["sessions"].extend(r3.get("sessions", []))
    result["messages"].extend(r3.get("messages", []))

    r4 = await create_story_4(db)
    result["agents"].extend(r4.get("agents", []))
    result["sessions"].extend(r4.get("sessions", []))
    result["messages"].extend(r4.get("messages", []))

    r5 = await create_story_5(db)
    result["inbox"].extend(r5.get("inbox", []))
    result["tasks"].extend(r5.get("tasks", []))

    return result
