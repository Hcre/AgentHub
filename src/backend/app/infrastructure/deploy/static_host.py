"""Static host for deployment (M4 ①.1).

提供最小闭环的真实静态托管：
- 落盘：files dict → _assets/deploy/{id}/ 目录
- 真 URL：返回 http://<host>/preview/{id}/index.html （由 main.py 挂 StaticFiles）
- 真 zip：shutil.make_archive 真打 zip（package 类型）
- 路径校验：拒绝 `..` 和越权路径（防路径穿越）

事件总线通知通过 deploy_service 显式调用，本模块不直接耦合。
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)

# 项目根目录下的部署落盘区（与现有 _assets/ 一致，gitignored）
_DEPLOY_ROOT = Path("_assets/deploy")


def _safe_id(deployment_id: UUID | str) -> str:
    """UUID 已是 hex + dash，校验通过即可；防御性转换。"""
    s = str(deployment_id)
    if not all(c.isalnum() or c == "-" for c in s):
        raise ValueError(f"非法 deployment id：{s!r}")
    return s


def _deploy_dir(deployment_id: UUID) -> Path:
    """单次部署的落盘目录。"""
    return _DEPLOY_ROOT / _safe_id(deployment_id)


def write_files(deployment_id: UUID, files: dict[str, str]) -> Path:
    """落盘 files dict → _assets/deploy/{id}/ 目录。

    路径校验：拒绝绝对路径、.. 越权、空键。
    返回落盘根目录（绝对路径）。
    """
    base = _deploy_dir(deployment_id).resolve()
    base.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files.items():
        if not rel_path or rel_path.startswith("/") or ".." in Path(rel_path).parts:
            raise ValueError(f"非法文件路径：{rel_path!r}（禁止绝对路径或 .. 越权）")
        dest = (base / rel_path).resolve()
        # 防御性：再次校验解析后仍在 base 下
        if not str(dest).startswith(str(base)):
            raise ValueError(f"路径穿越拦截：{rel_path!r}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    logger.info("落盘 %d 个文件到 %s", len(files), base)
    return base


def build_preview_url(deployment_id: UUID, host: str = "http://127.0.0.1:8000") -> str:
    """返回真 URL（前端可访问的 FastAPI 静态路径）。

    host 通过 deploy_service 注入（默认本机开发地址），生产可由 env 覆盖。
    """
    sid = _safe_id(deployment_id)
    return f"{host}/preview/{sid}/"


def make_zip(deployment_id: UUID, files: dict[str, str]) -> Path:
    """package 类型：用标准库 shutil.make_archive 真打 zip。

    返回 zip 绝对路径。
    """
    import tempfile

    base = write_files(deployment_id, files)
    sid = _safe_id(deployment_id)
    with tempfile.TemporaryDirectory() as tmp:
        archive_base = os.path.join(tmp, f"deploy-{sid}")
        archive_path = shutil.make_archive(archive_base, "zip", root_dir=base)
        # 移到 _assets/deploy/{id}/deploy-{id}.zip
        final = _DEPLOY_ROOT / sid / f"deploy-{sid}.zip"
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(archive_path, final)
        logger.info("打 zip 完成：%s", final)
        return final.resolve()


def remove(deployment_id: UUID) -> None:
    """清理落盘（删除阶段使用）。"""
    p = _deploy_dir(deployment_id)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)