"""技能库路由：本地 library、市场搜索（skillhub.cn）、安装（下载 + 解压到 SKILLS_DIR）。"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.db.base import get_session
from app.infrastructure.db.models import AgentModel

router = APIRouter(prefix="/api/skills", tags=["skills"])

# 解析后的绝对路径（启动时一次性 resolve）
logger = logging.getLogger(__name__)

SKILLS_DIR = settings.skills_dir_path


def _extract_description(skill_md_path: Path, max_chars: int = 200) -> str:
    """从 SKILL.md 提取首段文字作为 description。

    规则（按顺序）：
      1) 跳过文件开头的 YAML frontmatter（`---` ... `---` 块）
      2) 跳过 # 标题行
      3) 跳过 ``` 代码块标记 + 代码块内
      4) 跳过空行
      5) 取第一段非空连续行（直到下一个空行）
    """
    try:
        text = skill_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    lines = text.splitlines()
    para: list[str] = []
    in_code = False
    in_yaml = False
    yaml_seen = False  # 是否见过起始的 ---
    for line in lines:
        stripped = line.strip()
        # YAML frontmatter 检测：文件开头的第一个 --- 起到下一个 --- 止
        if stripped == "---":
            if not yaml_seen:
                in_yaml = True
                yaml_seen = True
                continue
            if in_yaml:
                in_yaml = False
                continue
        if in_yaml:
            continue
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            if para:
                break
            continue
        if stripped.startswith("#"):
            continue
        para.append(stripped)
    desc = " ".join(para)
    if len(desc) > max_chars:
        desc = desc[: max_chars - 3] + "..."
    return desc


# ── skillhub.cn 上游契约 ──────────────────────────────────────────
# 公开端点（无需鉴权），见 docs/reports 或 worklog：
#   GET /api/skills?keyword=X&page=1&pageSize=N
#     → { code:0, data:{ skills:[{name, slug, description, description_zh,
#                                   ownerName, stars, downloads, installs,
#                                   category, homepage, version, score,
#                                   created_at(ms), updated_at(ms)}]}}
#   GET /api/v1/showcase/{section}  section ∈ {hot_downloads, newest,
#                                                trending, hot, featured}
SKILLHUB_API = "https://api.skillhub.cn"
SKILLHUB_WEB = "https://www.skillhub.cn"
HTTPX_TIMEOUT = 15.0


# ── Pydantic models ──────────────────────────────────────────────


class MarketSearchRequest(BaseModel):
    q: str = ""
    page: int = 1
    limit: int = 20
    # sort_by: 'default' | 'stars' | 'downloads' — 上游不接受自定义 sort，全在客户端 sort
    sort_by: str = "default"


class MarketInstallRequest(BaseModel):
    skill_id: str
    name: str


# ── 本地 metadata（写进 skill 目录的 .agenthub.json sidecar）──
class LocalMeta(BaseModel):
    slug: str
    name: str
    author: str  # 显示用的作者名（owner.displayName）
    owner_id: str = ""  # 内部 ID
    version: str = ""
    source: str = "skillhub"  # 安装来源（未来可加 git/local）
    installed_at: int = 0  # unix ts（落地时间）


class DeleteSkillRequest(BaseModel):
    name: str  # skill 目录名（slug）


class BatchDeleteRequest(BaseModel):
    names: list[str]


class CreateSkillRequest(BaseModel):
    """用户用自然语言 / 表单填的字段，落到本地 SKILL.md + .agenthub.json。"""

    name: str  # slug（也作目录名）
    author: str = "local"
    description: str  # 用户自然语言描述
    triggers: list[str] = []  # 触发关键词
    instructions: str = ""  # instructions markdown
    examples: list[str] = []  # usage examples


class GenerateSkillRequest(BaseModel):
    """AI 渐进对话生成：用户一段自然语言 → LLM 抽出 4 字段。"""

    description: str  # 用户用自然语言描述的 skill
    # 现有字段（如果用户在中间步填过，AI 生成时纳入上下文避免覆盖）
    name_hint: str = ""
    triggers_hint: list[str] = []


class GenerateSkillResponse(BaseModel):
    name: str
    description: str
    triggers: list[str]
    instructions: str


# ── Library ──────────────────────────────────────────────────────


def _read_sidecar(skill_dir: Path) -> dict:
    """读 .agenthub.json sidecar（装时落地）。无则返空 dict。"""
    sc = skill_dir / ".agenthub.json"
    if not sc.exists():
        return {}
    try:
        return json.loads(sc.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


async def _backfill_sidecars(skills_without_sc: list[tuple[str, Path]]) -> None:
    """懒回填：library 看到没 sidecar 的，去 skillhub batch 查一次。

    单次 batch 最多支持 50 个 slug，所以数量再多也是 1 次网络往返。
    失败不影响 library 主流程（静默 fallthrough）。
    """
    if not skills_without_sc:
        return
    slugs = [slug for slug, _ in skills_without_sc]
    slug_to_dir = dict(skills_without_sc)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            bresp = await client.post(
                f"{SKILLHUB_API}/api/v1/skills/batch",
                json={"slugs": slugs},
            )
            if bresp.status_code != 200:
                return
            bdata = bresp.json()
            items_by_slug = {it.get("skill", {}).get("slug"): it for it in bdata.get("items", [])}
            for slug in slugs:
                it = items_by_slug.get(slug)
                if not it:
                    continue
                # 读 SKILL.md 拿 name（fallback 到 slug）
                sc_dir = slug_to_dir[slug]
                sc = _read_sidecar(sc_dir)
                sidecar = {
                    "slug": slug,
                    "name": sc.get("name") or it.get("skill", {}).get("displayName", slug),
                    "author": it.get("owner", {}).get("displayName", "unknown"),
                    "owner_id": it.get("owner", {}).get("handle", ""),
                    "version": it.get("latestVersion", {}).get("version", ""),
                    "source": "skillhub",
                    "installed_at": sc.get("installed_at", int(time.time())),
                }
                (sc_dir / ".agenthub.json").write_text(
                    json.dumps(sidecar, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
    except Exception:
        # 网络/上游问题不影响 library 返回——sidecar 写不进去就 unknown
        pass


@router.get("/library")
async def list_skills():
    """递归列出本地所有 skill。

    主入口文件名兼容：SKILL.md / SKILLS.md / skill.md / skills.md
    （skillhub 上游不规范，归一化之前可能混着用；library 只读不写，
    所以历史装的非 SKILL.md 也得识别）。

    每条带：
      - description：读 SKILL.md 首段（跳过 YAML frontmatter / 标题 / 代码块），200 字截断
      - author / version / installed_at：读 .agenthub.json sidecar（装时落地），
        老装无 sidecar 时 author = "unknown"（不回退 skillhub，避免阻塞）
    """
    if not SKILLS_DIR.exists():
        return []
    result = []
    needs_backfill: list[tuple[str, Path]] = []  # (slug, dir) — 后面 batch 回填
    for skill_dir in sorted(
        [p.parent for p in SKILLS_DIR.rglob("*.md") if p.name in _SKILL_ENTRY_NAMES]
    ):
        # 去重：同一目录可能多个变体都扫到（一个目录只有一个主入口，跳过重复）
        if any(r["name"] == skill_dir.name for r in result):
            continue
        name = skill_dir.name
        # 找主入口
        entry = _find_entry_file(skill_dir)
        if entry is None:
            continue
        rel = entry.relative_to(SKILLS_DIR).as_posix()
        # 读 sidecar
        sc = _read_sidecar(skill_dir)
        if not sc:
            # 没 sidecar → 加入 backfill 队列（library 返完后异步回填）
            needs_backfill.append((name, skill_dir))
        result.append(
            {
                "name": name,
                "path": f"{SKILLS_DIR.as_posix()}/{rel}",
                "rel_path": rel,
                "source": sc.get("source", "skillhub"),
                "description": _extract_description(entry),
                "author": sc.get("author", "unknown"),
                "version": sc.get("version", ""),
                "installed_at": sc.get("installed_at", 0),
            }
        )
    # 懒回填没 sidecar 的（不阻塞响应，写在 task 里）
    if needs_backfill:
        import asyncio

        asyncio.create_task(_backfill_sidecars(needs_backfill))
    return result


@router.delete("/library/{name}")
async def delete_skill(
    name: str,
    force: bool = Query(default=False, description="强制删除（即使有 Agent 引用）"),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """删除单个 skill 目录。

    安全护栏：
      - name 必须在 SKILLS_DIR 下（防 ../ 逃逸）
      - 必须是 skill 目录（存在 SKILL.md/skill.md 等主入口）
      - 如有 Agent 引用此 skill，返回 409（除非 force=true）
    """
    if not name:
        raise HTTPException(status_code=400, detail="name 必填")
    slug = _sanitize_name(name)
    target = (SKILLS_DIR / slug).resolve()
    skills_real = SKILLS_DIR.resolve()
    if not str(target).startswith(str(skills_real)):
        raise HTTPException(status_code=403, detail="越界路径")
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Skill「{slug}」不存在")
    # 校验是合法 skill 目录（有主入口）
    if _find_entry_file(target) is None:
        raise HTTPException(status_code=400, detail=f"「{slug}」不是合法 skill 目录")

    # 检查是否有 Agent 引用此 skill
    if not force:
        # JSONB @> 包含查询：skills 数组中是否含此 slug
        result = await db.execute(
            select(AgentModel.id, AgentModel.name).where(
                AgentModel.is_deleted.is_(False),
                AgentModel.skills.contains([slug]),
            )
        )
        referencing_agents = [(str(row[0]), row[1]) for row in result.fetchall()]
        if referencing_agents:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "SKILL_IN_USE",
                        "message": f"Skill「{slug}」被 {len(referencing_agents)} 个 Agent 引用，无法删除。使用 ?force=true 强制删除。",
                        "agents": [{"id": aid, "name": aname} for aid, aname in referencing_agents],
                    }
                },
            )

    import shutil

    shutil.rmtree(target)
    return {"deleted": slug}


@router.post("/library/batch-delete")
async def batch_delete_skills(body: BatchDeleteRequest) -> dict:
    """批量删除 skill。逐个尝试，单个失败不阻断其他。"""
    if not body.names:
        raise HTTPException(status_code=400, detail="names 不能为空")
    deleted: list[str] = []
    failed: list[dict] = []
    import shutil

    for raw in body.names:
        try:
            slug = _sanitize_name(raw)
            target = (SKILLS_DIR / slug).resolve()
            skills_real = SKILLS_DIR.resolve()
            if not str(target).startswith(str(skills_real)):
                failed.append({"name": raw, "reason": "越界"})
                continue
            if not target.exists() or not target.is_dir():
                failed.append({"name": raw, "reason": "不存在"})
                continue
            if _find_entry_file(target) is None:
                failed.append({"name": raw, "reason": "非合法 skill 目录"})
                continue
            shutil.rmtree(target)
            deleted.append(slug)
        except Exception as e:
            failed.append({"name": raw, "reason": str(e)[:80]})
    return {"deleted": deleted, "failed": failed}


# ── 自然语言 / 手动创建本地 skill（用户自创）─────────────────


def _render_skill_md(
    name: str, description: str, triggers: list[str], instructions: str, examples: list[str]
) -> str:
    """把字段拼成 skillhub 兼容的 SKILL.md（YAML frontmatter + 正文）。"""
    triggers_yaml = "[" + ", ".join(f'"{t}"' for t in triggers) + "]" if triggers else "[]"
    frontmatter = (
        "---\n"
        f"name: {name}\n"
        f"description: |\n"
        + "\n".join(f"  {ln}" for ln in description.splitlines() or [description])
        + "\n"
        f"version: 1.0.0\n"
        f"triggers: {triggers_yaml}\n"
        'tags: ["user-created"]\n'
        "---\n\n"
    )
    body = "# " + name + "\n\n"
    if triggers:
        body += "**触发词**: " + "、".join(f"`{t}`" for t in triggers) + "\n\n"
    if instructions:
        body += "## Instructions\n\n" + instructions + "\n\n"
    if examples:
        body += "## Examples\n\n"
        for i, ex in enumerate(examples, 1):
            body += f"### Example {i}\n\n{ex}\n\n"
    return frontmatter + body


@router.post("/library/create")
async def create_skill(body: CreateSkillRequest) -> dict:
    """把用户填/AI 生成的字段落成本地 SKILL.md + .agenthub.json。

    安全护栏：
      - name 经 _sanitize_name，目录必须在 SKILLS_DIR 下
      - 不能覆盖已有 skill
    """
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name 必填")
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="description 必填")
    slug = _sanitize_name(body.name)
    target = (SKILLS_DIR / slug).resolve()
    skills_real = SKILLS_DIR.resolve()
    if not str(target).startswith(str(skills_real)):
        raise HTTPException(status_code=403, detail="越界路径")
    if (target / "SKILL.md").exists():
        raise HTTPException(status_code=409, detail=f"Skill「{slug}」已存在")
    target.mkdir(parents=True, exist_ok=True)

    # 写 SKILL.md
    md = _render_skill_md(
        name=body.name,
        description=body.description,
        triggers=body.triggers,
        instructions=body.instructions,
        examples=body.examples,
    )
    (target / "SKILL.md").write_text(md, encoding="utf-8")

    # 写 sidecar
    author = body.author.strip() or "local"
    sidecar = {
        "slug": slug,
        "name": body.name,
        "author": author,
        "owner_id": "",
        "version": "1.0.0",
        "source": "local",
        "installed_at": int(time.time()),
    }
    (target / ".agenthub.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "name": slug,
        "path": str(target / "SKILL.md"),
        "rel_path": f"{slug}/SKILL.md",
        "source": "local",
        "author": author,
        "description": body.description,
        "version": "1.0.0",
        "installed_at": sidecar["installed_at"],
    }


@router.post("/library/generate")
async def generate_skill_fields(body: GenerateSkillRequest) -> GenerateSkillResponse:
    """AI 渐进对话：用户一段自然语言 → LLM 抽出 4 字段。

    LLM 选择：DeepSeek（settings.deepseek_api_key）— 便宜快速。
    无 key 时回退：直接基于用户输入猜，不调 LLM。
    """
    import re as _re

    user_text = body.description.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="description 必填")

    api_key = settings.deepseek_api_key
    if not api_key:
        # 离线回退：基于用户输入做基础拆分，不调 LLM
        # 截前几个 token 当 triggers，第一句话当 description
        return GenerateSkillResponse(
            name=body.name_hint or _slugify_first_line(user_text),
            description=user_text,
            triggers=body.triggers_hint or _extract_keyword_triggers(user_text),
            instructions=(
                f"你是一个 SKILL，用户的描述如下：\n\n{user_text}\n\n请根据用户输入完成对应任务。"
            ),
        )

    # LLM 调用（OpenAI SDK + DeepSeek base_url，复用 selector.py 模式）
    system_prompt = (
        "你是一个 skill 元数据生成助手。\n"
        "用户用自然语言描述一个想创建的 skill。\n"
        "你的任务：从描述里提取 4 个字段，**只返回 JSON，不要任何其他内容**。\n"
        "字段：\n"
        "  - name: 短横线分隔的小写英文 slug（kebab-case），≤ 40 字符，"
        "必须反映 skill 功能\n"
        "  - description: 精炼后的中文描述（≤ 200 字符），保留关键信息\n"
        "  - triggers: 触发关键词数组（用户说这些话时启用 skill），3-7 个，"
        "中文短词组\n"
        "  - instructions: 详细指令 markdown，描述 skill 怎么执行任务，"
        "包括步骤、约束、输出格式\n\n"
        "示例输出（用户输入「帮我做小红书爆款标题」）：\n"
        '{"name": "xhs-viral-title",'
        ' "description": "基于真实爆款规律生成小红书吸睛标题",'
        ' "triggers": ["小红书标题", "爆款标题", "xhs 标题"],'
        ' "instructions": "1. 分析用户提供的主题\\n2. ..."}'
    )
    user_prompt_parts = [user_text]
    if body.name_hint:
        user_prompt_parts.append(f"\n\n用户已选名字：{body.name_hint}（AI 必须采纳）")
    if body.triggers_hint:
        user_prompt_parts.append(
            f"\n\n用户已草拟的触发词：{', '.join(body.triggers_hint)}（AI 必须采纳并补充）"
        )
    user_prompt = "".join(user_prompt_parts)
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1500,
        )
        import json as _json

        raw = resp.choices[0].message.content or "{}"
        data = _json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败：{e}") from e

    return GenerateSkillResponse(
        name=_re.sub(r"[^a-z0-9\-]", "-", str(data.get("name", "")).lower()).strip("-")[:40]
        or _slugify_first_line(user_text),
        description=str(data.get("description", user_text))[:300],
        triggers=[str(t) for t in (data.get("triggers") or [])][:7],
        instructions=str(data.get("instructions", "")),
    )


def _slugify_first_line(text: str) -> str:
    """用户自然语言的首句 → 英文 kebab slug。"""
    import re as _re

    first = (text.splitlines() or [text])[0][:50]
    slug = _re.sub(r"[^a-z0-9]+", "-", first.lower()).strip("-")
    return slug or "user-skill"


def _extract_keyword_triggers(text: str) -> list[str]:
    """从用户输入里抽 1-3 个关键词当 trigger。中文按字符切。"""
    import re as _re

    text = text.strip()
    # 截前 24 字符，2-gram 切
    head = text[:24]
    bigrams: list[str] = []
    for i in range(0, len(head) - 1):
        bg = head[i : i + 2]
        if not _re.search(r"[a-zA-Z一-鿿]", bg):
            continue
        bigrams.append(bg)
    return bigrams[:3]


# ── Marketplace: skillhub.cn 适配 ────────────────────────────────


def _skillhub_to_market(s: dict) -> dict:
    """skillhub skill item → 统一市场 schema。

    字段映射：
      id        ← slug
      name      ← name
      author    ← ownerName
      description ← description_zh (fallback description)
      homepage  ← homepage (skillhub 内链，作为「打开 skillhub」用)
      skill_url ← `${SKILLHUB_WEB}/s/${slug}`
      stars     ← stars
      downloads ← downloads
      installs  ← installs
      category  ← category
      version   ← version
      updated_at ← updated_at (ms → s)
    """
    return {
        "id": s.get("slug", ""),
        "name": s.get("name", ""),
        "author": s.get("ownerName", ""),
        # 中文友好：优先 description_zh
        "description": s.get("description_zh") or s.get("description") or "",
        "github_url": s.get("homepage", ""),
        "skill_url": f"{SKILLHUB_WEB}/skills/{s.get('slug', '')}",
        "stars": s.get("stars", 0),
        "downloads": s.get("downloads", 0),
        "installs": s.get("installs", 0),
        "category": s.get("category", ""),
        "version": s.get("version", ""),
        # ms → s（前端按 s 解析，toLocaleDateString 友好）
        "updated_at": str(s.get("updated_at", 0) // 1000),
    }


@router.post("/marketplace/search")
async def marketplace_search(body: MarketSearchRequest):
    """搜索 skillhub.cn 技能市场（关键词 + 客户端排序）。

    上游 `/api/skills` 不接受自定义 sort= 参数（实测都返默认数据），
    所以**客户端 sort 在后端做**——分页拉够数据后按 body.sort_by 排序截断。

    上游硬约束：响应体被 CDN/反代在 ~5000 字节截断。`pageSize=5`（3689B）安全，
    超过就 JSON 不完整。**多页并发拉**避开限制：4×5=20 满足前端 limit≤18。
    """
    keyword = body.q.strip()
    page_size = 5  # 安全值（3689B < 5000B 截断线）
    pages_needed = (body.limit + page_size - 1) // page_size

    base_params: dict[str, str | int] = {"pageSize": page_size}
    if keyword:
        base_params["keyword"] = keyword

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        tasks = [
            client.get(f"{SKILLHUB_API}/api/skills", params={**base_params, "page": i + 1})
            for i in range(pages_needed)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    skills_raw: list[dict] = []
    seen: set[str] = set()
    for resp in results:
        if isinstance(resp, Exception) or resp.status_code != 200:
            continue
        try:
            data = resp.json()
        except Exception:
            continue
        if data.get("code") != 0:
            continue
        for s in data.get("data", {}).get("skills", []):
            slug = s.get("slug", "")
            if slug and slug not in seen:
                seen.add(slug)
                skills_raw.append(s)

    # 客户端 sort（上游 sort= 都不生效）
    if body.sort_by == "stars":
        skills_raw.sort(key=lambda s: s.get("stars", 0), reverse=True)
    elif body.sort_by == "downloads":
        skills_raw.sort(key=lambda s: s.get("downloads", 0), reverse=True)
    # else 'default' → 保持上游 score 排序

    return {"skills": [_skillhub_to_market(s) for s in skills_raw[: body.limit]]}


def _sanitize_name(name: str) -> str:
    """将 skill 名转为安全目录名。"""
    name = re.sub(r"[^\w\-.]", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-.") or "skill"


# skillhub 上游主入口文件名不统一：接受任意一种
_SKILL_ENTRY_NAMES = ("SKILL.md", "SKILLS.md", "skill.md", "skills.md")


def _find_entry_file(skill_dir: Path) -> Path | None:
    """在 skill 根目录找主入口 md。返回第一个匹配的文件路径。"""
    for name in _SKILL_ENTRY_NAMES:
        p = skill_dir / name
        if p.exists():
            return p
    return None


@router.post("/marketplace/install")
async def marketplace_install(body: MarketInstallRequest):
    """从 skillhub 下载 skill zip 并解压到 SKILLS_DIR/{slug}/。

    上游链路：
      POST skillhub `/api/v1/download?slug={slug}` → 302 → 腾讯云 COS zip
      zip 内容：skill.md / skill.json / examples.md / README.md / _meta.json 等

    写 sidecar `.agenthub.json`：保存 author（owner.displayName）+ 落地时间，
    供 library 端点展示用。
    """
    import time as _time

    if not body.skill_id:
        raise HTTPException(status_code=400, detail="skill_id 必填")
    slug = _sanitize_name(body.skill_id)
    install_dir = SKILLS_DIR / slug
    if install_dir.exists() and (install_dir / "SKILL.md").exists():
        raise HTTPException(status_code=409, detail=f"Skill「{slug}」已存在")
    install_dir.mkdir(parents=True, exist_ok=True)

    # 下载（follow_redirects 默认开启，自动跟 302 到 COS）
    download_url = f"{SKILLHUB_API}/api/v1/download?slug={body.skill_id}"
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(download_url)
            resp.raise_for_status()
            zip_bytes = resp.content
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502, detail=f"下载失败 {e.response.status_code}：{e.response.text[:200]}"
        ) from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=504, detail=f"下载超时/网络错误：{e}") from e

    # 解压（防 zip-slip：拒绝 ../ 路径）
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for member in zf.namelist():
                # 跳过目录条目 / 跳过绝对路径 / 跳过父目录穿越
                if not member or member.endswith("/"):
                    continue
                member_path = (install_dir / member).resolve()
                if not str(member_path).startswith(str(install_dir.resolve())):
                    raise HTTPException(status_code=400, detail=f"非法 zip 条目：{member}")
                member_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(member_path, "wb") as dst:
                    dst.write(src.read())
    except zipfile.BadZipFile as e:
        # 回滚
        import shutil

        shutil.rmtree(install_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail="下载内容不是合法 zip") from e

    # 校验主入口文件（skillhub 命名不统一：SKILL.md / SKILLS.md / skill.md / skills.md 都可能）
    entry = _find_entry_file(install_dir)
    if entry is None:
        import shutil

        shutil.rmtree(install_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail="zip 中未找到主入口文件（SKILL.md / SKILLS.md / skill.md / skills.md 任一）",
        )
    # 归一化：重命名为 SKILL.md（项目统一约定）
    normalized = install_dir / "SKILL.md"
    if entry != normalized:
        entry.rename(normalized)

    # 写 .agenthub.json sidecar：author + 安装时间
    author = "unknown"
    owner_id = ""
    version = ""
    # 优先用 batch 端点拿 owner.displayName（人类可读），降级用 _meta.json 里的 ownerId
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            bresp = await client.post(
                f"{SKILLHUB_API}/api/v1/skills/batch",
                json={"slugs": [body.skill_id]},
            )
            if bresp.status_code == 200:
                bdata = bresp.json()
                for it in bdata.get("items", []):
                    if it.get("skill", {}).get("slug") == body.skill_id:
                        author = it.get("owner", {}).get("displayName") or "unknown"
                        owner_id = it.get("owner", {}).get("handle") or ""
                        version = it.get("latestVersion", {}).get("version") or ""
                        break
    except Exception:
        pass
    sidecar = {
        "slug": body.skill_id,
        "name": body.name,
        "author": author,
        "owner_id": owner_id,
        "version": version,
        "source": "skillhub",
        "installed_at": int(_time.time()),
    }
    (install_dir / ".agenthub.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "name": slug,
        "path": str(normalized),
        "source": "skillhub",
        "action": "installed",
    }


# ── Filesystem browsing ──────────────────────────────────────────
# 为前端提供目录浏览功能，解决浏览器无法获取完整本地路径的问题

FS_ROUTER = APIRouter(prefix="/api/fs", tags=["filesystem"])


def _resolve_path(path: str) -> str:
    """解析路径：先试原生 → 再试 Docker mount。"""
    # 盘符路径（如 D: 或 D:\） → 强制转为根目录，避免 os.path.isdir 指向当前工作目录
    stripped = path.strip().rstrip("/").rstrip("\\")
    if len(stripped) == 2 and stripped[0].isalpha() and stripped[1] == ":":
        return f"{stripped}\\"
    if (
        len(stripped) == 3
        and stripped[0].isalpha()
        and stripped[1] == ":"
        and stripped[2] in ("/", "\\")
    ):
        return f"{stripped[0]}:\\"
    if os.path.isdir(path):
        return path
    m = re.match(r"^([A-Za-z]):[/\\]?(.+)", path.strip())
    if m:
        container = f"/mnt/host_{m.group(1).lower()}/" + m.group(2).replace("\\", "/")
        if os.path.isdir(container):
            return container
    return path


@FS_ROUTER.get("/browse")
async def fs_browse(path: str = "") -> dict:
    """浏览目录：path 为空返回盘符列表，否则返回该目录的子项。"""
    import os as _os

    if not path:
        if hasattr(_os, "listdrives"):
            drives = _os.listdrives()
            letters = [d.rstrip("\\").rstrip("/") for d in drives]
        else:
            letters = [f"{c}:\\" for c in "CDEFGHIJKLMNOPQRSTUVWXYZ" if _os.path.isdir(f"{c}:\\")]
        # Linux/macOS fallback：无盘符 → 浏览根目录
        if letters:
            return {
                "path": "",
                "parent": "",
                "items": [{"name": l, "path": l, "type": "drive"} for l in letters],
            }
        path = "/"
    real = _resolve_path(path)
    if not _os.path.isdir(real):
        raise HTTPException(status_code=404, detail=f"目录不存在：{real}")
    items = []
    for name in sorted(_os.listdir(real)):
        full = _os.path.join(real, name)
        try:
            is_dir = _os.path.isdir(full)
        except OSError:
            continue
        items.append({"name": name, "path": full, "type": "dir" if is_dir else "file"})
    parent = _os.path.dirname(real.rstrip("/\\")) if real else ""
    return {"path": real, "parent": parent, "items": items}


class FsReadRequest(BaseModel):
    path: str


@FS_ROUTER.post("/read")
async def fs_read(body: FsReadRequest) -> dict:
    """读文件内容（限文本类，>2MB 返 413）。"""
    import os as _os

    path = body.path
    if not path:
        raise HTTPException(status_code=400, detail="path 必填")
    real = _resolve_path(path)
    if not _os.path.isfile(real):
        raise HTTPException(status_code=404, detail=f"文件不存在：{real}")
    size = _os.path.getsize(real)
    if size > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件超过 2MB")
    try:
        with open(real, "r", encoding="utf-8") as f:
            return {"path": real, "content": f.read(), "size": size}
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="二进制文件不支持预览")


@FS_ROUTER.get("/raw")
async def fs_raw(path: str):
    """Serve raw file content with proper MIME type (for images, etc.)."""
    import os as _os
    import mimetypes

    from fastapi.responses import FileResponse

    if not path:
        raise HTTPException(status_code=400, detail="path 必填")
    real = _resolve_path(path)
    if not _os.path.isfile(real):
        raise HTTPException(status_code=404, detail=f"文件不存在：{real}")
    size = _os.path.getsize(real)
    if size > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=413, detail="文件超过 10MB")

    mime_type, _ = mimetypes.guess_type(real)
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(real, media_type=mime_type)


class FsMkdirRequest(BaseModel):
    parent: str
    name: str


@FS_ROUTER.post("/mkdir")
async def fs_mkdir(body: FsMkdirRequest) -> dict:
    parent, name = body.parent, body.name
    """在 parent 下新建文件夹 name。"""
    import os as _os

    parent_real = _resolve_path(parent)
    if not _os.path.isdir(parent_real):
        raise HTTPException(status_code=404, detail=f"父目录不存在：{parent_real}")
    new_path = _os.path.join(parent_real, name)
    if _os.path.exists(new_path):
        raise HTTPException(status_code=409, detail=f"已存在：{new_path}")
    try:
        _os.makedirs(new_path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"创建失败：{e}") from e
    return {"path": new_path}


@FS_ROUTER.get("/search")
async def fs_search(path: str, q: str, limit: int = 100) -> dict:
    """在 path 下按文件名模糊搜索（递归），返回前 limit 条。"""
    import os as _os

    real = _resolve_path(path)
    if not _os.path.isdir(real):
        raise HTTPException(status_code=404, detail=f"目录不存在：{real}")
    q_lower = q.lower()
    out: list[dict] = []
    for root, dirs, files in _os.walk(real):
        for f in files:
            if q_lower in f.lower():
                out.append({"name": f, "path": _os.path.join(root, f), "type": "file"})
                if len(out) >= limit:
                    return {"items": out, "truncated": True}
    return {"items": out, "truncated": False}


class RevealRequest(BaseModel):
    path: str
    """目标路径：文件 = explorer /select 高亮；目录 = 直接打开"""


@FS_ROUTER.post("/reveal")
async def fs_reveal(body: RevealRequest) -> dict:
    """在 OS 文件资源管理器中打开 path。

    Windows: `explorer <dir>` 或 `explorer /select,<file>`（高亮）
    macOS:   `open <path>`
    Linux:   `xdg-open <path>`

    **安全限定**：path 必须解析到 SKILLS_DIR 下（防任意执行 explorer）。
    """
    if not body.path:
        raise HTTPException(status_code=400, detail="path 必填")
    real = Path(_resolve_path(body.path)).resolve()
    if not real.exists():
        raise HTTPException(status_code=404, detail=f"路径不存在：{real}")

    # 安全护栏：只允许打开 SKILLS_DIR 子路径
    skills_real = SKILLS_DIR.resolve()
    if not str(real).startswith(str(skills_real)):
        raise HTTPException(status_code=403, detail="只允许打开 SKILLS_DIR 内的路径")

    is_file = real.is_file()
    try:
        if sys.platform == "win32":
            if is_file:
                # /select,<file> 在资源管理器中打开父目录并高亮文件
                subprocess.Popen(["explorer", f"/select,{real}"])
            else:
                subprocess.Popen(["explorer", str(real)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(real)])
        else:
            subprocess.Popen(["xdg-open", str(real)])
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"系统命令不可用：{e}") from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"启动资源管理器失败：{e}") from e

    return {"ok": True, "path": str(real), "kind": "file" if is_file else "folder"}
