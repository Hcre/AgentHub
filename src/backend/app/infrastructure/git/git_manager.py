"""Git repository manager: clone, pull, scan template source repos."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from app.core.exceptions import SyncError

logger = logging.getLogger(__name__)


def _run_git(
    *args: str, timeout: int = 120, cwd: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a git command synchronously (intended for use via asyncio.to_thread)."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as e:
        raise SyncError(f"git command timed out: {' '.join(args)}") from e
    except FileNotFoundError:
        raise SyncError("git command not available; please install git") from None


class GitManager:
    """Manage git clone/pull and file scanning for a template source repo."""

    def __init__(self, repo_dir: Path) -> None:
        self._dir = repo_dir

    async def clone(self, url: str, branch: str = "main") -> None:
        """Shallow clone a repository to the local directory."""
        self._dir.parent.mkdir(parents=True, exist_ok=True)
        if self._dir.exists():
            return
        result = await asyncio.to_thread(
            _run_git,
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            "--single-branch",
            url,
            str(self._dir),
            timeout=120,
        )
        if result.returncode != 0:
            raise SyncError(f"git clone failed ({url}): {result.stderr.strip()[:300]}")
        logger.info("Cloned %s -> %s", url, self._dir)

    async def pull(self, branch: str = "main") -> None:
        """Fetch and hard-reset to the latest remote commit."""
        if not self._dir.exists():
            raise SyncError(f"repo directory does not exist: {self._dir}")
        result = await asyncio.to_thread(
            _run_git,
            "git",
            "fetch",
            "origin",
            branch,
            timeout=120,
            cwd=str(self._dir),
        )
        if result.returncode != 0:
            raise SyncError(f"git fetch failed: {result.stderr.strip()[:300]}")
        result = await asyncio.to_thread(
            _run_git,
            "git",
            "reset",
            "--hard",
            f"origin/{branch}",
            timeout=30,
            cwd=str(self._dir),
        )
        if result.returncode != 0:
            raise SyncError(f"git reset failed: {result.stderr.strip()[:300]}")
        logger.info("Pulled %s", self._dir)

    async def scan_agents(self) -> list[Path]:
        """Scan agent .md files from wshobson/agents plugins structure.

        wshobson/agents pattern: plugins/*/agents/*.md
        Local pattern: my-templates/*/SKILL.md

        Returns paths relative to the repo root.
        """
        if not self._dir.exists():
            return []
        paths: list[Path] = []
        # wshobson/agents: plugins/{plugin}/agents/{agent}.md
        plugins_dir = self._dir / "plugins"
        if plugins_dir.exists():
            for agent_md in plugins_dir.rglob("agents/*.md"):
                if agent_md.is_file():
                    paths.append(agent_md.relative_to(self._dir))
        # Fallback: also scan my-templates/ for local templates
        local_dir = self._dir / "my-templates"
        if local_dir.exists():
            for md in local_dir.rglob("SKILL.md"):
                if md.is_file():
                    paths.append(md.relative_to(self._dir))
        return sorted(paths)
