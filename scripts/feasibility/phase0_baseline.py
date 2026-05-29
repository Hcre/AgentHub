"""Phase 0 量化基线：固定场景 × N=20，测量身份互串率。

固定场景：
- 3 个 Agent：喵娘（猫娘 persona）、技术负责人（严肃后端）、产品经理（需求方）
- 固定 trigger：「请大家自我介绍一下，说说各自负责什么」
- 使用 Claude CLI（CLAUDE_CODE）真实 LLM 调用

每轮检测：
- 身份互串：发言内容是否自称其他角色的名字/身份
- 自己 @ 自己：发言中是否 @ 了自己的名字
- 口吻传染：非喵娘是否说了「喵」或「～」

决策阈值：
- 身份互串率 <5%（20 轮 ≤1 次）→ Phase 1 推迟
- 身份互串率 ≥5% → Phase 1 启动
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# backend 在 PYTHONPATH 上
_backend = str(Path(__file__).resolve().parents[2] / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

# 环境初始化（必须在导入 app 之前）
os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENV", "test")
# 不设 LLM_ADAPTER_MODE=mock，让 agent_system 决定适配器

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.infrastructure.db.models  # noqa: F401
from app.application.commands import CreateSessionCommand, SendMessageCommand
from app.application.services import ChatService, SessionService
from app.application.services.context_builder import ContextBuilder
from app.application.services.discussion_orchestrator import DiscussionOrchestrator
from app.application.services.selector import Selector
from app.core.events import InMemoryEventBus
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.entities.session import Session
from app.domain.enums import AgentSystem, DispatchMode, SessionType
from app.domain.llm.protocol import StreamEventType
from app.infrastructure.cache.memory_l1 import InMemoryL1Store
from app.infrastructure.cache.watermark_store import InMemoryWatermarkStore
from app.infrastructure.db.base import Base
from app.infrastructure.llm.factory import build_adapter_for_agent
from app.infrastructure.llm.mock_adapter import MockAdapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)

# ---------------------------------------------------------------------------
# 场景定义
# ---------------------------------------------------------------------------

AGENT_DEFS = [
    {
        "name": "喵娘",
        "avatar": "🐱",
        "role": "前端工程师",
        "system_prompt": (
            "你是「喵娘」，一个可爱猫娘风格的前端工程师。"
            "你说话时句末经常加「喵～」，语气活泼可爱。"
            "你只代表你自己发言，不要自称别人的名字或身份。"
        ),
    },
    {
        "name": "技术负责人",
        "avatar": "🔧",
        "role": "后端技术负责人",
        "system_prompt": (
            "你是「技术负责人」，一个严肃的后端技术专家。"
            "你说话简洁直接，不卖萌，不模仿他人。"
            "你只代表你自己发言，不要自称别人的名字或身份。"
            "特别注意：永远不要用「喵」字结尾，不要说「～」。"
        ),
    },
    {
        "name": "产品经理",
        "avatar": "📋",
        "role": "产品经理",
        "system_prompt": (
            "你是「产品经理」，负责需求分析和产品规划。"
            "你说话专业有条理，关注用户体验和商业价值。"
            "你只代表你自己发言，不要自称别人的名字或身份。"
        ),
    },
]

TRIGGER_TEXT = "请大家自我介绍一下，说说各自负责什么"


# ---------------------------------------------------------------------------
# 检测逻辑
# ---------------------------------------------------------------------------

@dataclass
class RoundResult:
    round_num: int
    agent_name: str
    agent_role: str
    response_text: str
    identity_confusion: bool = False  # 自称别人的名字/身份
    self_at: bool = False  # @ 了自己
    tone_contagion: bool = False  # 非喵娘说了「喵」或「～」
    notes: list[str] = field(default_factory=list)


def detect_identity_confusion(agent_name: str, agent_role: str, text: str) -> bool:
    """检测该 Agent 是否在发言中自称别人的名字或身份。

    例如：喵娘的发言中出现「我是技术负责人」或「作为技术负责人」。
    """
    other_names = {
        "喵娘": ["技术负责人", "产品经理"],
        "技术负责人": ["喵娘", "产品经理"],
        "产品经理": ["喵娘", "技术负责人"],
    }
    others = other_names.get(agent_name, [])
    for other in others:
        # 检查「我是 X」「作为 X」「X 负责」等身份声明模式
        patterns = [
            f"我是{other}",
            f"作为{other}",
            f"{other}负责",
            f"{other}来",
            f"我叫{other}",
        ]
        for pat in patterns:
            if pat in text:
                return True
    return False


def detect_self_at(agent_name: str, text: str) -> bool:
    """检测是否 @ 了自己。"""
    return f"@{agent_name}" in text


def detect_tone_contagion(agent_name: str, text: str) -> bool:
    """非喵娘是否出现了喵娘的口癖标记（喵、～）。"""
    if agent_name == "喵娘":
        return False  # 喵娘自己用喵是正常的
    return "喵" in text or "～" in text


# ---------------------------------------------------------------------------
# 管线构建
# ---------------------------------------------------------------------------

def _build_pipeline(db_session: AsyncSession):
    """构建群聊全链路（不使用 MockAdapter，Agent 各自指定适配器）。"""
    bus = InMemoryEventBus()
    msg_repo = PostgresMessageRepository(db_session)
    agent_repo = PostgresAgentRepository(db_session)
    group_repo = PostgresGroupRepository(db_session)
    session_repo = PostgresSessionRepository(db_session)
    l1 = InMemoryL1Store(window=20)
    wm = InMemoryWatermarkStore()
    ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)

    discussion = DiscussionOrchestrator(
        message_repo=msg_repo,
        agent_repo=agent_repo,
        l1_memory=l1,
        watermarks=wm,
        context_builder=ctx,
        selector=Selector(),
        event_bus=bus,
    )

    chat = ChatService(
        session_repo, msg_repo, agent_repo, group_repo,
        l1, wm, ctx, discussion,
        llm=MockAdapter(delay=0),  # per-agent 适配器由 send_and_stream 内部按 agent.agent_system 路由
        event_bus=bus,
    )
    return chat, l1, wm, bus, session_repo


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

async def run_one_round(
    db_session: AsyncSession,
    round_id: int,
) -> list[RoundResult]:
    """执行一轮群聊（自建 agents + group + session），收集所有 Agent 回复并检测。"""
    results: list[RoundResult] = []

    agent_repo = PostgresAgentRepository(db_session)

    # 协调者（占位，Selector / Orchestrator 会排除它）
    coord = Agent(
        name=f"协调者-r{round_id}", avatar="🤖", role="Coordinator",
        is_system=True, agent_system=AgentSystem.MOCK,
    )
    await agent_repo.save(coord)

    # 三个群成员
    agents_map: dict[str, Agent] = {"coordinator": coord}
    for ad in AGENT_DEFS:
        a = Agent(
            name=ad["name"], avatar=ad["avatar"], role=ad["role"],
            system_prompt=ad["system_prompt"],
            agent_system=AgentSystem.CLAUDE_CODE,
        )
        await agent_repo.save(a)
        agents_map[ad["name"]] = a

    # 建 group + session
    member_ids = [agents_map[n].id for n in ["喵娘", "技术负责人", "产品经理"]]

    group = Group(
        name=f"baseline-r{round_id}",
        coordinator_id=coord.id,
        member_ids=member_ids,
    )
    group.set_dispatch_mode(DispatchMode.DISCUSSION)
    await PostgresGroupRepository(db_session).save(group)

    session = Session(type=SessionType.GROUP, group_id=group.id, title=f"r{round_id}")
    await PostgresSessionRepository(db_session).save(session)

    # 构建管线 + 发触发消息
    chat, _l1, _wm, _bus, _session_repo = _build_pipeline(db_session)

    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content=TRIGGER_TEXT)
        )
    ]

    # 收集各 Agent 的完整 TEXT 回复
    agent_texts: dict[str, str] = {}
    for e in events:
        if e.type == StreamEventType.TEXT and e.sender_agent_id:
            aid = str(e.sender_agent_id)
            agent_texts.setdefault(aid, "")
            agent_texts[aid] += (e.content or "")

    # 名称映射
    id_to_name = {str(agents_map[n].id): n for n in ["喵娘", "技术负责人", "产品经理"]}
    id_to_role = {str(agents_map[n].id): agents_map[n].role for n in ["喵娘", "技术负责人", "产品经理"]}

    # 检测每个 Agent 的回复
    for aid, text in agent_texts.items():
        name = id_to_name.get(aid, "未知")
        role = id_to_role.get(aid, "未知")
        rr = RoundResult(
            round_num=round_id,
            agent_name=name,
            agent_role=role,
            response_text=text,
            identity_confusion=detect_identity_confusion(name, role, text),
            self_at=detect_self_at(name, text),
            tone_contagion=detect_tone_contagion(name, text),
        )
        if rr.identity_confusion:
            rr.notes.append("身份互串")
        if rr.self_at:
            rr.notes.append("自己@自己")
        if rr.tone_contagion:
            rr.notes.append("口吻传染")
        results.append(rr)

    return results


async def main() -> None:
    N = 20
    print(f"=== Phase 0 量化基线 === N={N} ===")
    print(f"场景：3 Agent（喵娘/技术负责人/产品经理）")
    print(f"触发：{TRIGGER_TEXT}")
    print(f"开始时间：{datetime.now(timezone.utc).isoformat()}")
    print()

    # 创建内存 DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    all_results: list[RoundResult] = []

    for r in range(1, N + 1):
        print(f"[{r}/{N}] 执行中...", end=" ", flush=True)
        try:
            async with factory() as db_session:
                results = await run_one_round(db_session, r)
                all_results.extend(results)
                confusion_count = sum(1 for rr in results if rr.identity_confusion)
                self_at_count = sum(1 for rr in results if rr.self_at)
                contagion_count = sum(1 for rr in results if rr.tone_contagion)
                total = len(results)
                print(
                    f"Agent={total} | "
                    f"互串={confusion_count} | "
                    f"自@={self_at_count} | "
                    f"传染={contagion_count}"
                )
        except Exception as exc:
            print(f"FAILED: {exc}")
            continue

    await engine.dispose()

    # ── 汇总统计 ──
    total_responses = len(all_results)
    identity_confusions = [rr for rr in all_results if rr.identity_confusion]
    self_ats = [rr for rr in all_results if rr.self_at]
    tone_contagions = [rr for rr in all_results if rr.tone_contagion]

    confusion_rate = len(identity_confusions) / total_responses * 100 if total_responses else 0
    self_at_rate = len(self_ats) / total_responses * 100 if total_responses else 0
    contagion_rate = len(tone_contagions) / total_responses * 100 if total_responses else 0

    print()
    print("=" * 60)
    print("量化基线结果")
    print("=" * 60)
    print(f"总轮次：{N}")
    print(f"总 Agent 发言数：{total_responses}")
    print()
    print(f"身份互串：{len(identity_confusions)}/{total_responses} ({confusion_rate:.1f}%)")
    print(f"自己 @ 自己：{len(self_ats)}/{total_responses} ({self_at_rate:.1f}%)")
    print(f"口吻传染：{len(tone_contagions)}/{total_responses} ({contagion_rate:.1f}%)")
    print()

    # 阈值判定
    if confusion_rate < 5.0:
        verdict = "PASS — Phase 1 推迟，措辞修复已够用"
    else:
        verdict = "NOT PASS — Phase 1 启动，做长驻 + stream-json"
    print(f"判定：{verdict}")

    # 详细日志
    print()
    print("--- 身份互串详情 ---")
    for rr in identity_confusions:
        print(f"  [{rr.round_num}] {rr.agent_name}: {rr.response_text[:120]}...")
    if not identity_confusions:
        print("  (无)")

    print()
    print("--- 自己 @ 自己详情 ---")
    for rr in self_ats:
        print(f"  [{rr.round_num}] {rr.agent_name}: {rr.response_text[:120]}...")
    if not self_ats:
        print("  (无)")

    print()
    print("--- 口吻传染详情 ---")
    for rr in tone_contagions:
        print(f"  [{rr.round_num}] {rr.agent_name}: {rr.response_text[:120]}...")
    if not tone_contagions:
        print("  (无)")

    # 保存完整结果到文件
    output_path = os.path.join(
        os.path.dirname(__file__) if "__file__" in dir() else ".",
        "phase0_baseline_result.json",
    )
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "N": N,
        "total_responses": total_responses,
        "confusion_rate_pct": round(confusion_rate, 1),
        "self_at_rate_pct": round(self_at_rate, 1),
        "contagion_rate_pct": round(contagion_rate, 1),
        "verdict": verdict,
        "identity_confusions": [
            {"round": rr.round_num, "agent": rr.agent_name, "text": rr.response_text}
            for rr in identity_confusions
        ],
        "self_ats": [
            {"round": rr.round_num, "agent": rr.agent_name, "text": rr.response_text}
            for rr in self_ats
        ],
        "tone_contagions": [
            {"round": rr.round_num, "agent": rr.agent_name, "text": rr.response_text}
            for rr in tone_contagions
        ],
    }
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "phase0_baseline_result.json",
    )
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
