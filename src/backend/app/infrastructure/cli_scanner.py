"""CLI PATH 扫描器（P1-3 / spec 04-commands §6.7 B-5.4-P1-3）。"""

from __future__ import annotations

import dataclasses
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_BINS: tuple[str, ...] = ("claude", "codex", "opencode", "pi", "trae")
_VERSION_FLAGS: tuple[str, ...] = ("--version", "-v", "version")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(s: str) -> str:
    return _ANSI.sub("", s)


@dataclass(frozen=True)
class CliScanResult:
    name: str
    path: str | None
    version: str | None
    available: bool
    error: str | None = None
    last_scan_at: float = 0.0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _probe_version(bin_path: str, timeout: float = 3.0) -> str | None:
    for flag in _VERSION_FLAGS:
        try:
            proc = subprocess.run(
                [bin_path, flag],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            output = (proc.stdout or "").strip() or (proc.stderr or "").strip()
            if output:
                first_line = output.splitlines()[0].strip()
                first_line = _strip_ansi(first_line)
                if first_line:
                    return first_line[:200]
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("version probe failed for %s %s: %s", bin_path, flag, exc)
            continue
    return None


def scan_one(name: str, *, timeout: float = 3.0) -> CliScanResult:
    ts = time.time()
    path = shutil.which(name)
    if path is None:
        return CliScanResult(
            name=name, path=None, version=None, available=False,
            error=f"{name!r} not in PATH", last_scan_at=ts,
        )
    version = _probe_version(path, timeout=timeout)
    return CliScanResult(
        name=name, path=path, version=version, available=True, last_scan_at=ts,
    )


def scan_all(
    names: tuple[str, ...] | list[str] = DEFAULT_BINS, *, timeout: float = 3.0
) -> list[CliScanResult]:
    return [scan_one(n, timeout=timeout) for n in names]
