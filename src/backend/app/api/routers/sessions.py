"""Session and message routes."""

from __future__ import annotations

import asyncio
import logging
import platform
import shlex
import subprocess
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, get_session_service
from app.application.commands import (
    CreateSessionCommand,
    PinMessageCommand,
    UnpinMessageCommand,
    UpdateSessionCommand,
)
from app.application.services import SessionService
from app.infrastructure.llm.cli_logger import get_log_path, log_exists
from app.infrastructure.llm.process_registry import get_spawn_info, kill_session
from app.schemas.session import MessageOut, SessionCreateRequest, SessionOut

router = APIRouter(prefix="/api", tags=["sessions"])

ServiceDep = Annotated[SessionService, Depends(get_session_service)]


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreateRequest, svc: ServiceDep) -> SessionOut:
    resp = await svc.create(
        CreateSessionCommand(
            type=str(body.type),
            group_id=body.group_id,
            agent_id=body.agent_id,
            title=body.title,
            workspace_path=body.workspace_path or "",
        )
    )
    return SessionOut(**resp.__dict__)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    svc: ServiceDep, type: str | None = None, q: str | None = None
) -> list[SessionOut]:
    items = await svc.list(type=type, query=q)
    return [SessionOut(**i.__dict__) for i in items]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session_detail(session_id: UUID, svc: ServiceDep) -> SessionOut:
    return SessionOut(**(await svc.get(session_id)).__dict__)


@router.get("/sessions/{session_id}/cli-log-path")
async def get_cli_log_path(session_id: UUID, svc: ServiceDep) -> dict:
    await svc.get(session_id)
    path = get_log_path(str(session_id))
    response: dict = {"path": str(path)}
    if not log_exists(str(session_id)):
        response["note"] = "Log file will be created when the agent starts processing"
    return response


@router.post("/sessions/{session_id}/open-terminal")
async def open_cli_terminal(session_id: UUID, svc: ServiceDep) -> dict:
    """Open the real CLI process in a visible terminal window.

    CLI uses its own default config (no AgentHub injection).
    Output is tee'd to the log file so chat streaming continues to work.
    """
    session = await svc.get(session_id)
    sid = str(session_id)
    log_path = get_log_path(sid)
    log_path_str = str(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _logger = logging.getLogger(__name__)

    spawn_info = get_spawn_info(sid)
    if spawn_info is None:
        raise HTTPException(status_code=404, detail="Send a message first - no CLI spawn info yet.")

    cmd_list = list(spawn_info["cmd"])
    env = spawn_info.get("env", {})
    cwd = spawn_info.get("cwd")
    cli_cmd = shlex.join(cmd_list)

    prefix = ""
    if cwd:
        prefix += f"cd '{cwd}'; "
    for k, v in env.items():
        if platform.system() == "Windows":
            prefix += f"$env:{k}='{v}'; "
        else:
            prefix += f"export {k}='{v}'; "

    # Kill background PIPE process, let CLI take over in the visible terminal
    # (CLI uses --session/--resume to restore conversation context)
    await kill_session(sid)

    system = platform.system()
    try:
        if system == "Windows":
            ps_cmd = (
                f"$host.UI.RawUI.WindowTitle='AH-{sid[:8]}'; "
                f"Write-Host '=== {cli_cmd[:80]}... ==='; "
                f"{prefix}{cli_cmd} 2>&1 | Tee-Object -FilePath '{log_path_str}'"
            )
            cmd_line = f'start "AH-{sid[:8]}" powershell -NoExit -Command "{ps_cmd}"'
            await asyncio.to_thread(subprocess.Popen, cmd_line, shell=True)
        elif system == "Darwin":
            bash_cmd = f"echo '=== {cli_cmd[:80]}... ==='; {prefix}{cli_cmd} 2>&1 | tee '{log_path_str}'"
            script = f'tell application "Terminal" to do script "{bash_cmd}"'
            await asyncio.to_thread(subprocess.Popen, ["osascript", "-e", script])
        else:
            terminal = await asyncio.to_thread(_find_linux_terminal)
            if terminal is None:
                raise RuntimeError("No terminal emulator found")
            bash_cmd = f"echo '=== {cli_cmd[:80]}... ==='; {prefix}{cli_cmd} 2>&1 | tee '{log_path_str}'"
            await asyncio.to_thread(subprocess.Popen, [terminal, "-e", f"bash -c '{bash_cmd}'"])

        _logger.info("CLI terminal opened for session %s", session_id)
        return {"ok": True, "path": log_path_str}
    except Exception as exc:
        _logger.error("Failed to open CLI terminal for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _find_linux_terminal() -> str | None:
    for candidate in ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "lxterminal", "terminator", "alacritty", "kitty"]:
        if subprocess.run(["which", candidate], capture_output=True).returncode == 0:
            return candidate
    return None


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: UUID,
    svc: ServiceDep,
    before: UUID | None = None,
    limit: int = Query(default=50, le=200),
) -> list[MessageOut]:
    items = await svc.list_messages(session_id, before=before, limit=limit)
    return [MessageOut(**i.__dict__) for i in items]


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(session_id: UUID, body: dict, svc: ServiceDep) -> SessionOut:
    resp = await svc.update(
        UpdateSessionCommand(
            session_id=session_id,
            title=body.get("title"),
            workspace_path=body.get("workspace_path"),
            pinned=body.get("pinned"),
        )
    )
    return SessionOut(**resp.__dict__)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: UUID, svc: ServiceDep) -> Response:
    await svc.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: UUID, svc: ServiceDep) -> Response:
    await svc.delete_message(message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/messages/{message_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def pin_message(
    message_id: UUID,
    session_id: UUID,
    svc: ServiceDep,
    current_user: CurrentUser,
) -> Response:
    """P0-4 Pin message - requires login."""
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail="E_AUTH_REQUIRED: pin operation requires login",
        )
    await svc.pin_message(
        PinMessageCommand(session_id=session_id, message_id=message_id),
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/messages/{message_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def unpin_message(
    message_id: UUID,
    session_id: UUID,
    svc: ServiceDep,
) -> Response:
    await svc.unpin_message(
        UnpinMessageCommand(session_id=session_id, message_id=message_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
