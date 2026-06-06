"""CLI 本地配置读取器 — 读用户机器上 4 个主流 Agent CLI 的实际配置文件。

设计原则：
- 不兑底硬编码：读不到就返 None，让前端知道"本地确实没配置"
- 多路径 fallback：每个 CLI 有 2-3 个常见配置位置，第一个存在的赢
- 字段名兼容：CLI 间用 `model` / `baseUrl` / `apiKey` / `provider` 4 个统一字段，
  内部按各 CLI 真实 schema 做映射（camelCase / snake_case / nested）
- 异常隔离：读 / 解析失败都吞掉，返 None + source 标注
"""

from __future__ import annotations

import json
import logging
import os
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

# 统一返回的字段（缺失/未找到 = None）
_FIELDS = ("model", "base_url", "api_key", "provider")


def _home() -> Path:
    """跨平台 home（Windows: USERPROFILE / Unix: HOME）"""
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _read_json(path: Path) -> dict | None:
    """读 JSON 文件；不存在 / 解析失败 / 不是 dict 都返 None。"""
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("读 %s 失败: %s", path, e)
        return None


def _read_toml(path: Path) -> dict | None:
    """读 TOML 文件；不存在 / 解析失败都返 None。"""
    try:
        if not path.is_file():
            return None
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.debug("读 %s 失败: %s", path, e)
        return None


def _pick_first(paths: list[Path], reader=_read_json) -> tuple[Path | None, dict | None]:
    """返回第一个存在且能解析的 (path, data) 二元组。"""
    for p in paths:
        data = reader(p)
        if data is not None:
            return p, data
    return None, None


def _empty() -> dict:
    return {f: None for f in _FIELDS}


# ── Claude Code ───────────────────────────────────────────────────────
# 候选: ~/.claude/settings.json (项目级), ~/.claude.json (用户级)
# schema: { "model": "...", "apiKey": "...", "baseURL": "...", "provider": "..." }


def read_claude_code() -> tuple[str | None, dict]:
    home = _home()
    paths = [
        home / ".claude" / "settings.json",
        home / ".claude.json",
    ]
    found, data = _pick_first(paths)
    if not data:
        return None, _empty()
    return (
        str(found) if found else None,
        {
            "model": data.get("model"),
            "base_url": data.get("baseURL") or data.get("base_url"),
            "api_key": data.get("apiKey") or data.get("api_key"),
            "provider": data.get("provider"),
        },
    )


# ── OpenAI Codex CLI ──────────────────────────────────────────────────
# 实际位置（v0.x+）：~/.codex/config.toml + ~/.codex/auth.json
# 旧版 fallback: ~/.codex/config.json, ~/.config/codex/config.json
#
# config.toml schema (顶层)：
#   model = "gpt-5.5"
#   model_reasoning_effort = "high"
#   [marketplaces...]   ← 不放 API key
#
# auth.json:
#   { "auth_mode": "chatgpt", "OPENAI_API_KEY": null, "tokens": { "id_token": ... } }
# → 登录态用 ChatGPT OAuth，没有可导出的 API key；apiKey 标 "(chatgpt-login)"


def read_codex() -> tuple[str | None, dict]:
    home = _home()
    # 1) 先读 config.toml（新版）
    toml_paths = [home / ".codex" / "config.toml"]
    cfg_path, cfg = _pick_first(toml_paths, reader=_read_toml)
    if not cfg:
        # 2) 旧版 JSON 兼容
        json_paths = [
            home / ".codex" / "config.json",
            home / ".config" / "codex" / "config.json",
        ]
        cfg_path, cfg = _pick_first(json_paths)
        if not cfg:
            return None, _empty()
    else:
        cfg = dict(cfg)  # toml 是 MappingProxy，转一下方便后续修改

    # 3) auth.json 判登录方式
    auth = _read_json(home / ".codex" / "auth.json")
    auth_mode = auth.get("auth_mode") if isinstance(auth, dict) else None
    api_key = None
    if auth_mode == "chatgpt":
        api_key = "(chatgpt-login)"
    elif isinstance(auth, dict):
        api_key = auth.get("OPENAI_API_KEY") or auth.get("apiKey")

    # 4) 旧版 config 嵌套结构兼容
    if not api_key and isinstance(cfg.get("providers"), dict):
        for v in cfg["providers"].values():
            if isinstance(v, dict) and (v.get("apiKey") or v.get("api_key")):
                api_key = v.get("apiKey") or v.get("api_key")
                break

    return (
        str(cfg_path) if cfg_path else None,
        {
            "model": cfg.get("model"),
            "base_url": cfg.get("baseUrl") or cfg.get("base_url"),
            "api_key": api_key,
            "provider": auth_mode,  # "chatgpt" / "api_key" / None
        },
    )


# ── OpenCode (sst/opencode) ───────────────────────────────────────────
# 候选: ~/.config/opencode/opencode.json, ~/.opencode/config.json
# schema: { "provider": { "<name>": { "model": "...", "options": { ... } } } }


def read_opencode() -> tuple[str | None, dict]:
    home = _home()
    paths = [
        home / ".config" / "opencode" / "opencode.json",
        home / ".opencode" / "config.json",
    ]
    found, data = _pick_first(paths)
    if not data:
        return None, _empty()
    # 嵌套结构：data.provider.<name>.model + data.provider.<name>.options
    model = data.get("model")
    base_url = data.get("baseURL") or data.get("base_url")
    api_key = data.get("apiKey") or data.get("api_key")
    provider_name = None
    provider_obj = data.get("provider")
    if isinstance(provider_obj, dict) and provider_obj:
        provider_name, prov_cfg = next(iter(provider_obj.items()))
        if isinstance(prov_cfg, dict):
            model = prov_cfg.get("model", model)
            options = prov_cfg.get("options") or {}
            if isinstance(options, dict):
                base_url = options.get("baseURL") or options.get("base_url") or base_url
                api_key = options.get("apiKey") or options.get("api_key") or api_key
    return (
        str(found) if found else None,
        {
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "provider": provider_name,
        },
    )


# ── Pi Agent ─────────────────────────────────────────────────────────
# 实际位置：~/.pi/agent/  (子目录不是 ~/.pi/ 顶层)
#   - auth.json:    { "<provider>": { "type": "api_key", "key": "sk-..." } }
#   - models.json:  { "providers": {} }              ← 不放默认配置
#   - settings.json:{ "defaultProvider": "deepseek", "defaultModel": "deepseek-v4-flash" }
# 兼容：~/.pi/settings.json（旧版）


def read_pi_agent() -> tuple[str | None, dict]:
    home = _home()
    # 1) auth.json（先找 agent/ 子目录的，没有再找顶层）
    auth_paths = [
        home / ".pi" / "agent" / "auth.json",
        home / ".pi" / "auth.json",
    ]
    auth_path, auth = _pick_first(auth_paths)
    # 2) settings.json
    settings_paths = [
        home / ".pi" / "agent" / "settings.json",
        home / ".pi" / "settings.json",
        home / ".config" / "pi" / "settings.json",
    ]
    settings_path, settings = _pick_first(settings_paths)

    if not auth and not settings:
        return None, _empty()

    # Pi 的结构：defaultProvider 在 settings.json；apiKey 在 auth.json[<provider>]
    default_provider = settings.get("defaultProvider") if isinstance(settings, dict) else None
    default_model = settings.get("defaultModel") if isinstance(settings, dict) else None

    api_key = None
    if isinstance(auth, dict) and default_provider:
        entry = auth.get(default_provider)
        if isinstance(entry, dict):
            api_key = entry.get("key") or entry.get("apiKey") or entry.get("api_key")

    # 报告 source：实际读到的文件（auth + settings 拼接路径）
    sources = [str(p) for p in (auth_path, settings_path) if p is not None]
    return (
        " + ".join(sources) if sources else None,
        {
            "model": default_model,
            "base_url": None,  # Pi 不在 settings 里存 base_url
            "api_key": api_key,
            "provider": default_provider,
        },
    )


# ── 路由表 ───────────────────────────────────────────────────────────

_READERS = {
    "claude_code": read_claude_code,
    "codex": read_codex,
    "opencode": read_opencode,
    "pi_agent": read_pi_agent,
}


def read_default_config(agent_system: str) -> tuple[str | None, dict]:
    """公共入口：返回 (source_path_or_None, fields_dict)。

    未知 agent_system / mock / 读不到 → fields 全 None，source None。
    """
    reader = _READERS.get(agent_system)
    if not reader:
        return None, _empty()
    try:
        return reader()
    except Exception as e:  # noqa: BLE001 — 读配置失败必须兜底，不能影响 endpoint
        logger.warning("读 %s 配置异常: %s", agent_system, e)
        return None, _empty()
