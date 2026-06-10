"""StaticHost（L1）：把部署文件真实落盘到 deploy_root，并生成可访问 URL。

替代 DeployService 早期的 placeholder 假 URL（`https://agenthub-deploy.com/...`）。
落盘后由 main.py 的 `StaticFiles` 挂载点 `/preview` 对外暴露，浏览器可真实打开。

目录布局：
    {deploy_root}/{deployment_id}/            ← static_site：原样文件树
    {deploy_root}/{deployment_id}/site.zip    ← package：打包产物

URL：
    preview_url  = {public_base_url}/preview/{id}/{entry_file}
    download_url = {public_base_url}/preview/{id}/site.zip

安全：files 的 key 是相对路径，必须挡住目录穿越（`..`、绝对路径、盘符），
否则可写出 deploy_root 之外。`_safe_relpath` 统一校验。

设计取舍（写在前面，per feedback-comment-as-prompt）：
- 方法保持**同步**纯 IO，DeployService 用 `asyncio.to_thread` 包裹调用（CR-12 禁同步阻塞）。
  这样 StaticHost 可被单测直接同步调用，无需 event loop。
- zip 用标准库 `zipfile`（非 shutil.make_archive）以便精确控制写入哪些 key、避免落临时目录。
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath
from uuid import UUID


class DeployStaticError(Exception):
    """落盘阶段错误（非法路径等），由 DeployService 翻成 build failed。"""


def _safe_relpath(key: str) -> PurePosixPath:
    """校验 files 的相对路径 key，挡目录穿越；返回归一化的 PurePosixPath。

    拒绝：空串、绝对路径（/ 开头）、含 `..` 段、Windows 盘符（C:）、反斜杠。
    """
    if not key or key.strip() == "":
        raise DeployStaticError("文件路径为空")
    normalized = key.replace("\\", "/")
    if normalized.startswith("/"):
        raise DeployStaticError(f"非法绝对路径：{key}")
    if ":" in normalized:  # 盘符 / scheme
        raise DeployStaticError(f"非法路径（含冒号）：{key}")
    p = PurePosixPath(normalized)
    if any(part == ".." for part in p.parts):
        raise DeployStaticError(f"非法路径（目录穿越）：{key}")
    return p


class StaticHost:
    """部署产物落盘 + URL 生成。"""

    def __init__(self, root: Path, public_base_url: str) -> None:
        self._root = root
        self._base = public_base_url.rstrip("/")

    def _site_dir(self, deployment_id: UUID) -> Path:
        return self._root / str(deployment_id)

    # --- 写入 ---

    def write_site(self, deployment_id: UUID, files: dict[str, str]) -> int:
        """把 files 原样写到 {root}/{id}/，返回写入文件数。"""
        site = self._site_dir(deployment_id)
        site.mkdir(parents=True, exist_ok=True)
        count = 0
        for key, content in files.items():
            rel = _safe_relpath(key)
            dest = site / Path(*rel.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            count += 1
        return count

    def write_zip(self, deployment_id: UUID, files: dict[str, str]) -> Path:
        """把 files 打成 {root}/{id}/site.zip，返回 zip 路径。"""
        site = self._site_dir(deployment_id)
        site.mkdir(parents=True, exist_ok=True)
        zip_path = site / "site.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for key, content in files.items():
                rel = _safe_relpath(key)
                zf.writestr(str(rel), content)
        return zip_path

    def remove(self, deployment_id: UUID) -> None:
        """删除部署产物目录（软删时清盘，best-effort，不存在则忽略）。"""
        shutil.rmtree(self._site_dir(deployment_id), ignore_errors=True)

    # --- URL ---

    def site_url(self, deployment_id: UUID, entry_file: str) -> str:
        rel = _safe_relpath(entry_file)
        return f"{self._base}/preview/{deployment_id}/{rel.as_posix()}"

    def download_url(self, deployment_id: UUID) -> str:
        return f"{self._base}/preview/{deployment_id}/site.zip"
