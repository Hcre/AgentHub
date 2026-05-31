"""技能库路由：本地 library、市场搜索、安装。"""

from __future__ import annotations

import os
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


# ── Filesystem browsing ──────────────────────────────────────────
# 为前端提供目录浏览功能，解决浏览器无法获取完整本地路径的问题

FS_ROUTER = APIRouter(prefix="/api/fs", tags=["filesystem"])


def _resolve_path(path: str) -> str:
    """解析路径：先试原生 → 再试 Docker mount。"""
    if os.path.isdir(path):
        return path
    m = re.match(r"^([A-Za-z]):[/\\]?(.*)", path.strip())
    if m:
        container = f"/mnt/host_{m.group(1).lower()}/" + m.group(2).replace("\\", "/")
        if os.path.isdir(container):
            return container
    return path


def _to_win_path(path: str) -> str:
    """任意路径 → Windows 格式。"""
    m = re.match(r"^/mnt/host_([a-z])/(.*)", path)
    if m:
        return f"{m.group(1).upper()}:\\" + m.group(2).replace("/", "\\")
    # 已经是 Windows 路径或 Unix 路径，原样返回
    return path


@FS_ROUTER.get("/drives")
async def list_drives():
    """列出可用的盘符。"""
    drives = []
    for d in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        win = f"{d}:/"
        container = f"/mnt/host_{d.lower()}"
        if os.path.isdir(win) or os.path.isdir(container):
            drives.append({"letter": f"{d}:", "path": win, "label": f"本地磁盘 ({d}:)"})
    return drives


@FS_ROUTER.get("/browse")
async def browse_dir(path: str = ""):
    """浏览指定目录，返回子目录列表。"""
    if not path:
        return await list_drives()
    real = _resolve_path(path)
    if not os.path.isdir(real):
        return {"error": f"目录不存在: {path}", "items": []}
    items = []
    try:
        for name in sorted(os.listdir(real)):
            full = os.path.join(real, name)
            if os.path.isdir(full) and not name.startswith("."):
                win = _to_win_path(full)
                items.append({"name": name, "path": win, "type": "dir"})
    except PermissionError:
        pass
    parent = str(Path(real).parent)
    parent_win = _to_win_path(parent) if parent != real else ""
    return {"path": path, "parent": parent_win, "items": items}
