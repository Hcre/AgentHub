"""Provider Scanner — 借鉴 Multica config.go + Open Design PATH 扫描。

启动时自动扫描 PATH 发现可用 Agent CLI，返回结构化 Provider 列表。
只检测不安装，vendor-neutral。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProviderDef:
    """已知 CLI 的元数据 — 新增 Provider 只需加一条记录。"""

    name: str  # "opencode", "claude_code", ...
    display_name: str  # "OpenCode CLI"
    binary: str  # 可执行文件名
    adapter: str  # 适配器类型: "cli_subprocess" | "http_api" | "mock"
    version_flag: str = "--version"
    min_version: str | None = None
    description: str = ""


KNOWN_PROVIDERS: list[ProviderDef] = [
    ProviderDef(
        name="opencode",
        display_name="OpenCode CLI",
        binary="opencode",
        adapter="cli_subprocess",
        description="sst/opencode — 75+ provider, 支持 agent/mcp/acp",
    ),
    ProviderDef(
        name="claude_code",
        display_name="Claude Code",
        binary="claude",
        adapter="cli_subprocess",
        description="Anthropic 官方编码 CLI — 本地运行",
    ),
    ProviderDef(
        name="pi_agent",
        display_name="Pi Agent",
        binary="pi",
        adapter="cli_subprocess",
        description="Pi Agent CLI — 多 Provider 支持",
    ),
    ProviderDef(
        name="codex",
        display_name="OpenAI Codex CLI",
        binary="codex",
        adapter="cli_subprocess",
        description="OpenAI 编码 Agent CLI",
    ),
    ProviderDef(
        name="gemini",
        display_name="Google Gemini CLI",
        binary="gemini",
        adapter="cli_subprocess",
        description="Google Gemini 编码 CLI",
    ),
    ProviderDef(
        name="cursor_agent",
        display_name="Cursor Agent",
        binary="cursor-agent",
        adapter="cli_subprocess",
        description="Cursor 的 CLI Agent",
    ),
]

MOCK_PROVIDER = ProviderDef(
    name="mock",
    display_name="Mock · 演示假数据",
    binary="",
    adapter="mock",
    description="本地假回复，测试/演示用",
)


@dataclass
class DetectedProvider:
    name: str
    display_name: str
    binary: str
    executable_path: str
    version: str | None
    adapter: str
    description: str
    available: bool = True


async def detect_version(executable_path: str, flag: str = "--version") -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            executable_path,
            flag,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        output = (stdout + stderr).decode(errors="replace").strip()
        return output.split("\n")[0][:200] if output else None
    except Exception:
        return None


def _resolve_binary(binary: str) -> str | None:
    """查找二进制路径，包含 Windows npm 全局目录 fallback。

    与 opencode_runtime._find_binary() 逻辑保持一致，
    确保 scanner 和 runtime 对 '已安装' 的判断统一。
    """
    path = shutil.which(binary)
    if path:
        return path
    if os.name == "nt":
        for base in [
            os.path.expandvars(r"%APPDATA%\npm"),
            os.path.expandvars(r"%LOCALAPPDATA%\npm"),
            os.path.expanduser("~\\AppData\\Roaming\\npm"),
        ]:
            for ext in ("", ".cmd", ".exe", ".bat"):
                candidate = os.path.join(base, binary + ext)
                if os.path.isfile(candidate):
                    return candidate
    return None


async def scan_providers() -> list[DetectedProvider]:
    """扫描 PATH，发现所有可用的 Agent CLI。

    对应 Multica 的 exec.LookPath 探测 + Open Design 的 PATH 扫描：
    - 遍历 KNOWN_PROVIDERS，检查每个 binary 是否在 PATH 上
    - 运行 --version 获取版本号
    - 始终返回 mock 作为兜底选项
    """
    discovered: list[DetectedProvider] = []

    for defn in KNOWN_PROVIDERS:
        path = _resolve_binary(defn.binary)
        if not path:
            logger.debug("Provider '%s' 未在 PATH 找到 (%s)", defn.name, defn.binary)
            continue

        version = await detect_version(path, defn.version_flag)
        logger.info("检测到 Provider: %s at %s version=%s", defn.name, path, version)

        discovered.append(
            DetectedProvider(
                name=defn.name,
                display_name=defn.display_name,
                binary=defn.binary,
                executable_path=path,
                version=version,
                adapter=defn.adapter,
                description=defn.description,
            )
        )

    # mock 始终可用（兜底）
    discovered.append(
        DetectedProvider(
            name=MOCK_PROVIDER.name,
            display_name=MOCK_PROVIDER.display_name,
            binary=MOCK_PROVIDER.binary,
            executable_path="",
            version=None,
            adapter=MOCK_PROVIDER.adapter,
            description=MOCK_PROVIDER.description,
        )
    )

    return discovered
