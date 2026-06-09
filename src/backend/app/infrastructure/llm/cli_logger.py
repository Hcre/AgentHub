"""CLI 日志：将每个 session 的 CLI 原始 stdout 实时写入日志文件。
前端可通过 API 获取路径，用原生终端 tail 查看。
agent 启动时自动打开终端窗口，后续可通过按钮重新打开。
"""

from __future__ import annotations

import asyncio
import logging
import platform
import shlex
import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path

logger = logging.getLogger(__name__)

CLI_LOG_DIR = Path.home() / ".agenthub" / "cli-logs"
PROMPT_DIR = CLI_LOG_DIR / "prompts"


# ---------------------------------------------------------------------------
# public helpers
# ---------------------------------------------------------------------------


def get_log_path(session_id: str) -> Path:
    """Return the log file path for *session_id*.

    Creates the parent directory tree if it does not already exist.
    """
    CLI_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return CLI_LOG_DIR / f"{session_id}.log"


def log_exists(session_id: str) -> bool:
    """Return True when a log file for *session_id* already exists."""
    return get_log_path(session_id).exists()


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


def _shell_join(args: str | list[str]) -> str:
    """Normalise a command to a single string safe for embedding in a shell."""
    if isinstance(args, list):
        return shlex.join(args)
    return args


def _escape_ps_single_quoted(s: str) -> str:
    """Escape a string for use inside a PowerShell single-quoted string.

    In PowerShell, single quotes inside a single-quoted string are escaped
    by doubling them: ' -> ''.
    """
    return s.replace("'", "''")


def _build_prefix(
    cwd: str | None,
    env: dict[str, str] | None,
    system: str,
) -> str:
    """Build a shell snippet that chdirs and exports environment variables."""
    parts: list[str] = []
    if cwd:
        if system == "Windows":
            # Use forward slashes (PowerShell accepts them) and escape single
            # quotes so the path is safe inside a single-quoted PS string.
            cwd_safe = _escape_ps_single_quoted(cwd.replace("\\", "/"))
            parts.append(f"Set-Location '{cwd_safe}'")
        else:
            parts.append(f"cd '{cwd}'")
    if env:
        if system == "Windows":
            parts.extend(
                f"$env:{k}='{_escape_ps_single_quoted(v)}'"
                for k, v in env.items()
            )
        else:
            parts.extend(f"export {k}='{v}'" for k, v in env.items())
    if parts:
        return "; ".join(parts) + "; "
    return ""


# ---------------------------------------------------------------------------
# visible terminal
# ---------------------------------------------------------------------------


def spawn_visible_terminal(
    cmd: str | list[str],
    env: dict[str, str] | None = None,
    cwd: str | Path | None = None,
    session_id: str = "",
    prompt_text: str = "",
) -> bool:
    """Write *prompt_text* to a temp file, then open a **visible** terminal.

    The terminal pipes the prompt file into *cmd* and tees *cmd*'s stdout
    (and stderr) into ``get_log_path(session_id)``.

    The window is opened via ``subprocess.Popen(shell=True)`` and the handle
    is **not** awaited (fire-and-forget).

    Returns ``True`` when the subprocess was launched without an immediate
    exception; ``False`` otherwise.
    """
    # ---- write prompt file ------------------------------------------------
    log_path = get_log_path(session_id)
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    prompt_file = PROMPT_DIR / f"{session_id}.txt"
    try:
        prompt_file.write_text(prompt_text, encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Failed to write prompt file for session=%s at %s: %s",
            session_id, prompt_file, exc,
        )
        return False

    # ---- prepare ----------------------------------------------------------
    cli_cmd = _shell_join(cmd)
    system = platform.system()
    cwd_str = str(cwd) if cwd else None
    prefix = _build_prefix(cwd_str, env, system)
    title = session_id[:8] if session_id else "cli"

    # Normalise paths to forward slashes.  PowerShell on Windows accepts
    # both / and \, but forward slashes avoid escaping issues when paths
    # are embedded inside quoted command strings.
    prompt_path_ps = prompt_file.as_posix()
    log_path_ps = log_path.as_posix()

    try:
        if system == "Windows":
            # Build the PowerShell command using single-quoted path literals
            # (PowerShell does not interpret backslashes or variables inside
            # single-quoted strings).
            ps_cmd = (
                f"{prefix}"
                f"Get-Content -Path "
                f"'{_escape_ps_single_quoted(prompt_path_ps)}' | "
                f"{cli_cmd} 2>&1 | "
                f"Tee-Object -FilePath "
                f"'{_escape_ps_single_quoted(log_path_ps)}'"
            )
            # Escape any double quotes inside ps_cmd so they do not break
            # the outer -Command "..." quoting.  PowerShell interprets ""
            # inside a double-quoted string as a literal ".
            ps_cmd_escaped = ps_cmd.replace('"', '""')
            cmd_line = (
                f'start "AgentHub-{title}" '
                f'powershell -NoExit -Command "{ps_cmd_escaped}"'
            )
            logger.debug(
                "Launching Windows terminal for session=%s title=%s "
                "log=%s",
                session_id, title, log_path_ps,
            )
            subprocess.Popen(cmd_line, shell=True)

        elif system == "Darwin":
            # osascript -> Terminal.app
            bash_cmd = (
                f"{prefix}"
                f"cat '{prompt_file}' | {cli_cmd} 2>&1 | "
                f"tee '{log_path}'; echo '--- Done ---'"
            )
            script = (
                'tell application "Terminal" to do script '
                f'"{bash_cmd}"'
            )
            cmd_line = f"osascript -e '{script}'"
            subprocess.Popen(cmd_line, shell=True)

        else:  # Linux / other Unix
            bash_cmd = (
                f"{prefix}"
                f"cat '{prompt_file}' | {cli_cmd} 2>&1 | "
                f"tee '{log_path}'; echo '--- Done ---'"
            )
            # Prefer x-terminal-emulator; fall back through common emulators.
            for term in (
                "x-terminal-emulator",
                "gnome-terminal",
                "konsole",
                "xfce4-terminal",
                "xterm",
            ):
                which = subprocess.run(
                    ["which", term], capture_output=True, text=True
                )
                if which.returncode == 0:
                    cmd_line = f'{term} -e bash -c "{bash_cmd}"'
                    subprocess.Popen(cmd_line, shell=True)
                    break
            else:
                logger.error(
                    "No terminal emulator found on Linux (checked: "
                    "x-terminal-emulator, gnome-terminal, konsole, "
                    "xfce4-terminal, xterm)"
                )
                return False

        logger.info(
            "Opened visible terminal for session=%s prompt=%s log=%s",
            session_id, prompt_file, log_path,
        )
        return True

    except Exception:
        logger.exception(
            "Failed to open visible terminal for session=%s "
            "(cwd=%s, env_keys=%s)",
            session_id, cwd_str,
            list(env.keys()) if env else [],
        )
        return False


# ---------------------------------------------------------------------------
# async log reader
# ---------------------------------------------------------------------------


async def read_log_stream(
    session_id: str,
    idle_timeout: float = 30.0,
) -> AsyncGenerator[str, None]:
    """Poll the CLI log file for new lines and yield them as they appear.

    * Waits up to **5 s** for the log file to be created.
    * If the file still does not exist after the wait, creates an empty
      log file so that front-end readers do not fail with "file not found".
    * Once the file exists, reads it line by line, yielding decoded text
      (trailing newlines stripped).
    * Stops when *idle_timeout* seconds elapse with no new content.

    Typical usage::

        async for line in read_log_stream(sid, idle_timeout=60):
            print(line)
    """
    log_path = get_log_path(session_id)

    # -- wait for file to appear (max 5 s) ----------------------------------
    t0 = asyncio.get_event_loop().time()
    while not log_path.exists():
        if (asyncio.get_event_loop().time() - t0) > 5.0:
            logger.warning(
                "Log file did not appear within 5 s: %s (session=%s). "
                "Creating empty log file to prevent downstream read errors.",
                log_path, session_id,
            )
            try:
                log_path.write_text("", encoding="utf-8")
            except OSError as exc:
                logger.error(
                    "Failed to create empty log file at %s (session=%s): %s",
                    log_path, session_id, exc,
                )
                return
            break
        await asyncio.sleep(0.1)

    # -- read until timeout -------------------------------------------------
    deadline = asyncio.get_event_loop().time() + idle_timeout

    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break

                line = fh.readline()
                if line:
                    yield line.rstrip("\n")
                    await asyncio.sleep(0)       # let other coroutines run
                else:
                    await asyncio.sleep(0.1)     # no data yet — short nap
    except FileNotFoundError:
        logger.error(
            "Log file disappeared while reading: %s (session=%s)",
            log_path, session_id,
        )
    except OSError as exc:
        logger.error(
            "Error reading log file %s (session=%s): %s",
            log_path, session_id, exc,
        )
