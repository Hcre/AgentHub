"""技能库路由：本地 library、市场搜索、安装。"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/skills", tags=["skills"])

SKILLS_DIR = Path("/skills")
MARKETPLACE_URL = "https://skillsmp.com/api/v1/skills/search"
HTTPX_TIMEOUT = 15.0


# ── Pydantic models ──────────────────────────────────────────────


class MarketSearchRequest(BaseModel):
    q: str = ""
    page: int = 1
    limit: int = 20
    sort_by: str = "stars"


class MarketInstallRequest(BaseModel):
    skill_id: str
    github_url: str
    name: str


# ── Library ──────────────────────────────────────────────────────


@router.get("/library")
async def list_skills():
    """递归列出本地所有 skill（子目录名/SKILL.md）。"""
    if not SKILLS_DIR.exists():
        return []
    result = []
    for p in sorted(SKILLS_DIR.rglob("SKILL.md")):
        name = p.parent.name
        if name == "skills":
            continue
        result.append(
            {
                "name": name,
                "path": f"/skills/{p.relative_to(SKILLS_DIR)}",
                "source": "local",
            }
        )
    return result


# ── Marketplace ──────────────────────────────────────────────────


@router.post("/marketplace/search")
async def marketplace_search(body: MarketSearchRequest):
    """代理请求 skillsmp.com 搜索技能市场。"""
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await client.get(
            MARKETPLACE_URL,
            params={"q": body.q, "page": body.page, "limit": body.limit, "sortBy": body.sort_by},
        )
        resp.raise_for_status()
        data = resp.json()
    if not data.get("success"):
        raise HTTPException(status_code=502, detail="上游市场返回异常")
    skills = data["data"]["skills"]
    pagination = data["data"]["pagination"]
    return {
        "skills": [
            {
                "id": s["id"],
                "name": s["name"],
                "author": s["author"],
                "description": s["description"],
                "github_url": s["githubUrl"],
                "skill_url": s["skillUrl"],
                "stars": s["stars"],
                "updated_at": s["updatedAt"],
            }
            for s in skills
        ],
        "pagination": {
            "page": pagination["page"],
            "limit": pagination["limit"],
            "total": pagination["total"],
            "total_pages": pagination["totalPages"],
            "has_next": pagination["hasNext"],
        },
    }


def _sanitize_name(name: str) -> str:
    """将 skill 名转为安全目录名。"""
    name = re.sub(r"[^\w\-.]", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-.") or "skill"


GITHUB_API = "https://api.github.com"


@router.post("/marketplace/install")
async def marketplace_install(body: MarketInstallRequest):
    """从 GitHub 递归拉取整个 skill 目录（含 scripts/templates 等）。"""
    name = _sanitize_name(body.name)
    install_dir = SKILLS_DIR / name
    if install_dir.exists():
        raise HTTPException(status_code=409, detail=f"Skill「{name}」已存在")

    parts = _parse_github_url(body.github_url)
    if not parts:
        raise HTTPException(status_code=400, detail="仅支持 GitHub 仓库安装")
    owner, repo, branch, path = parts

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await _fetch_dir(client, owner, repo, branch, path, install_dir)
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="下载超时，请检查网络") from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502, detail=f"GitHub 下载失败: {e.response.status_code}"
        ) from e

    # 确保至少有 SKILL.md
    if not (install_dir / "SKILL.md").exists():
        raise HTTPException(status_code=400, detail="未在目录中找到 SKILL.md")

    return {"name": name, "path": f"/skills/{name}/SKILL.md", "source": "marketplace"}


async def _fetch_dir(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
    path: str,
    dest: Path,
) -> None:
    """递归拉取 GitHub 目录内容到本地。"""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    resp = await client.get(url)
    resp.raise_for_status()
    items = resp.json()
    # API 可能返回单个文件而不是数组
    if not isinstance(items, list):
        items = [items]

    for item in items:
        item_name = item["name"]
        item_type = item["type"]
        if item_type == "dir":
            sub_dest = dest / item_name
            sub_dest.mkdir(parents=True, exist_ok=True)
            await _fetch_dir(client, owner, repo, branch, item["path"], sub_dest)
        else:
            dest.mkdir(parents=True, exist_ok=True)
            dl = await client.get(item["download_url"])
            dl.raise_for_status()
            (dest / item_name).write_bytes(dl.content)


def _parse_github_url(github_url: str) -> tuple[str, str, str, str] | None:
    """解析 GitHub tree URL → (owner, repo, branch, path)。

    https://github.com/owner/repo/tree/branch/dir/sub  →  (owner, repo, branch, dir/sub)
    """
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)", github_url)
    if not m:
        return None
    owner, repo, branch, path = m.group(1), m.group(2), m.group(3), m.group(4)
    repo = re.sub(r"\.git$", "", repo)
    return owner, repo, branch, path
