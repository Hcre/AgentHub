"""Template markdown parser: extract metadata from YAML frontmatter + body."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class TemplateParser:
    """Parse .md template files into structured dicts."""

    _FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    def parse_template_batch(
        self,
        repo_dir: Path,
        md_paths: list[Path],
    ) -> list[dict]:
        """Batch-parse .md files, returning structured dicts.

        Each dict contains:
          source_path, name, description, system_prompt, model_tier,
          color, display_name_zh, description_zh, recommended_skills,
          compatible_agent_systems, compatible_providers, tools
        """
        results: list[dict] = []
        for rel_path in md_paths:
            full_path = repo_dir / rel_path
            try:
                parsed = self._parse_one(full_path, rel_path)
                if parsed:
                    results.append(parsed)
            except Exception:
                logger.warning("Failed to parse template: %s", rel_path, exc_info=True)
        return results

    def _parse_one(self, file_path: Path, rel_path: Path) -> dict | None:
        try:
            raw = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        fm_match = self._FRONTMATTER_RE.match(raw)
        if fm_match:
            fm_raw = fm_match.group(1)
            body = raw[fm_match.end() :].strip()
            frontmatter = self._parse_yaml_simple(fm_raw)
        else:
            frontmatter = {}
            body = raw.strip()

        source_path = rel_path.as_posix()
        name = frontmatter.get("name") or file_path.stem

        return {
            "source_path": source_path,
            "name": str(name)[:128],
            "description": str(frontmatter.get("description", ""))[:2000],
            "system_prompt": body[:10000],
            "model_tier": str(frontmatter.get("model_tier", "inherit"))[:16],
            "color": frontmatter.get("color"),
            "display_name_zh": frontmatter.get("display_name_zh"),
            "description_zh": frontmatter.get("description_zh"),
            "recommended_skills": self._as_str_list(frontmatter.get("recommended_skills", [])),
            "compatible_agent_systems": self._as_str_list(
                frontmatter.get("compatible_agent_systems", [])
            ),
            "compatible_providers": self._as_str_list(frontmatter.get("compatible_providers", [])),
            "tools": self._as_str_list(frontmatter.get("tools", [])),
        }

    @staticmethod
    def _parse_yaml_simple(raw: str) -> dict:
        """Minimal YAML parser: top-level scalars + string lists only.

        Avoids PyYAML dependency for security and simplicity.
        Supports:
          key: value
          key: "value"
          key:
            - item1
            - item2
          key: [item1, item2]
        """
        result: dict = {}
        lines = raw.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip() or line.strip().startswith("#"):
                i += 1
                continue

            m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)", line)
            if not m:
                i += 1
                continue

            key = m.group(1)
            value_part = m.group(2).strip()

            # Flow-style list: key: [item1, item2]
            list_flow = re.match(r"^\[(.*)\]$", value_part)
            if list_flow:
                items_str = list_flow.group(1)
                items = [s.strip().strip("'").strip('"') for s in items_str.split(",") if s.strip()]
                result[key] = items
                i += 1
                continue

            # Block scalar or list indicator
            if value_part == "" or value_part == "|":
                items: list[str] = []
                j = i + 1
                while j < len(lines):
                    item_match = re.match(r"^\s*-\s+(.*)", lines[j])
                    if item_match:
                        items.append(item_match.group(1).strip().strip("'").strip('"'))
                        j += 1
                    else:
                        break
                if items:
                    result[key] = items
                    i = j
                    continue
                elif value_part == "|":
                    j = i + 1
                    text_lines: list[str] = []
                    base_indent = None
                    while j < len(lines):
                        stripped = lines[j]
                        if not stripped.strip():
                            j += 1
                            continue
                        indent = len(stripped) - len(stripped.lstrip())
                        if base_indent is None:
                            base_indent = indent
                        if indent < (base_indent or 0) and stripped.strip():
                            break
                        text_lines.append(stripped[base_indent:] if base_indent else stripped)
                        j += 1
                    result[key] = "\n".join(text_lines)
                    i = j
                    continue

            # Simple scalar (strip quotes)
            if (value_part.startswith('"') and value_part.endswith('"')) or (
                value_part.startswith("'") and value_part.endswith("'")
            ):
                value_part = value_part[1:-1]
            result[key] = value_part
            i += 1

        return result

    @staticmethod
    def _as_str_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, str):
            return [value] if value else []
        return []
