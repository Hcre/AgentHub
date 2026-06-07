"""TemplateService (L3): template CRUD, GitHub sync, markdown export."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from app.core.exceptions import DomainError, NotFoundError, SyncError
from app.domain.entities.template import Template, TemplateSource
from app.domain.repositories import TemplateRepository
from app.infrastructure.git.git_manager import GitManager
from app.infrastructure.git.template_parser import TemplateParser

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_ID = "wshobson-agents"
DEFAULT_SOURCE_URL = "https://github.com/wshobson/agents.git"
DEFAULT_SOURCE_BRANCH = "main"
LOCAL_SOURCE = "local"
MY_TEMPLATES_DIR = "my-templates"


class TemplateService:
    """Template management: create/update/delete, sync from GitHub, export."""

    def __init__(
        self,
        template_repo: TemplateRepository,
        git_manager: GitManager,
        templates_dir: Path,
        skills_dir: Path | None = None,
    ) -> None:
        self._repo = template_repo
        self._git = git_manager
        self._dir = templates_dir
        self._skills_dir = skills_dir or (templates_dir.parent / "skills")
        self._parser = TemplateParser()

    # ------------------------------------------------------------------
    # Sync from GitHub
    # ------------------------------------------------------------------

    async def sync_source(self) -> dict:
        """Sync templates from the default GitHub source.

        Steps:
          1. Ensure source record in DB
          2. Clone or pull the git repo
          3. Scan for .md files
          4. Parse each file for metadata
          5. Convert to Template entities and bulk_upsert
          6. Update source record
          7. Return sync result {source_id, added, updated, deleted, total, error}
        """
        source_id = DEFAULT_SOURCE_ID
        url = DEFAULT_SOURCE_URL
        branch = DEFAULT_SOURCE_BRANCH

        try:
            # 1. Ensure source record
            source = await self._repo.get_source(source_id)
            if source is None:
                source = TemplateSource(
                    id=source_id,
                    url=url,
                    branch=branch,
                    description_zh="wshobson/agents: community agent templates",
                    enabled=True,
                )
                await self._repo.save_source(source)
                logger.info("Created template source: %s", source_id)

            # 2. Clone or pull
            repo_dir = self._dir / "sources" / source_id
            if not repo_dir.exists() or not (repo_dir / ".git").exists():
                await self._git.clone(url, branch)
            else:
                await self._git.pull(branch)

            # 3. Scan for .md files
            md_paths = await self._git.scan_agents()
            if not md_paths:
                return {
                    "source_id": source_id,
                    "added": 0,
                    "updated": 0,
                    "deleted": 0,
                    "total": 0,
                    "error": None,
                }

            # 4. Parse each file
            parsed = self._parser.parse_template_batch(repo_dir, md_paths)
            logger.info("Parsed %d templates from %s", len(parsed), source_id)

            # 5. Convert to Template entities, discover sibling skills
            templates: list[Template] = []
            for item in parsed:
                src_path = item[
                    "source_path"
                ]  # e.g. plugins/cicd-automation/agents/deployment-engineer.md
                plugin_skills = _discover_plugin_skills(repo_dir, src_path)

                t = Template(
                    source=source_id,
                    source_path=src_path,
                    name=item["name"],
                    description=item.get("description", ""),
                    model_tier=item.get("model_tier", "inherit"),
                    tools=item.get("tools", []),
                    color=item.get("color"),
                    display_name_zh=item.get("display_name_zh"),
                    description_zh=item.get("description_zh"),
                    recommended_skills=plugin_skills or item.get("recommended_skills", []),
                    compatible_agent_systems=item.get("compatible_agent_systems", []),
                    compatible_providers=item.get("compatible_providers", []),
                )
                templates.append(t)

            # 6. Symlink plugin skills into SKILLS_DIR so runtime can find them
            _symlink_plugin_skills(repo_dir, self._skills_dir)
            logger.info("Plugin skills symlinked to %s", self._skills_dir)

            # 7. Bulk upsert
            result = await self._repo.bulk_upsert(templates)

            # 8. Update source record
            await self._repo.mark_source_synced(
                source_id, template_count=len(templates), deleted_paths=[]
            )

            total = result["added"] + result["updated"]
            logger.info(
                "Sync complete: +%d ~%d -%d (total %d)",
                result["added"],
                result["updated"],
                result["deleted"],
                total,
            )

            return {
                "source_id": source_id,
                "added": result["added"],
                "updated": result["updated"],
                "deleted": result["deleted"],
                "total": total,
                "error": None,
            }

        except SyncError:
            raise
        except Exception as e:
            logger.exception("Sync failed for %s", source_id)
            raise SyncError(f"Sync failed: {e!s}") from e

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(self, cmd) -> Template:
        """Create a local template, writing metadata to my-templates directory."""
        import re as _re

        local_dir = self._dir / MY_TEMPLATES_DIR
        local_dir.mkdir(parents=True, exist_ok=True)

        slug = _re.sub(r"[^\w\-.]", "-", cmd.name.lower())
        slug = _re.sub(r"-{2,}", "-", slug).strip("-.") or "template"
        tmpl_dir = local_dir / slug
        if tmpl_dir.exists():
            raise DomainError(f"Template name already exists: {cmd.name}")

        tmpl_dir.mkdir(parents=True, exist_ok=True)
        md_content = _render_markdown(
            name=cmd.name,
            description=cmd.description,
            system_prompt=cmd.system_prompt,
            model_tier=cmd.model_tier,
            recommended_skills=cmd.recommended_skills,
            display_name_zh=cmd.display_name_zh,
            description_zh=cmd.description_zh,
            compatible_agent_systems=cmd.compatible_agent_systems,
            compatible_providers=cmd.compatible_providers,
        )
        (tmpl_dir / "SKILL.md").write_text(md_content, encoding="utf-8")

        source_path = f"{MY_TEMPLATES_DIR}/{slug}/SKILL.md"
        template = Template(
            source=LOCAL_SOURCE,
            source_path=source_path,
            name=cmd.name,
            description=cmd.description,
            model_tier=cmd.model_tier,
            color="#6366f1",
            display_name_zh=cmd.display_name_zh,
            description_zh=cmd.description_zh,
            recommended_skills=cmd.recommended_skills,
            compatible_agent_systems=cmd.compatible_agent_systems,
            compatible_providers=cmd.compatible_providers,
        )
        await self._repo.save(template)
        return template

    async def update(self, template_id: UUID, cmd) -> Template:
        """Update a local template only."""
        template = await self._repo.get_by_id(template_id)
        if template is None:
            raise NotFoundError(f"Template not found: {template_id}")
        if template.source != LOCAL_SOURCE:
            raise DomainError("Only local templates can be updated")

        changes: dict[str, object] = {}
        for field in (
            "name",
            "description",
            "system_prompt",
            "model_tier",
            "recommended_skills",
            "display_name_zh",
            "description_zh",
            "compatible_agent_systems",
            "compatible_providers",
            "is_enabled",
        ):
            val = getattr(cmd, field, None)
            if val is not None:
                changes[field] = val

        changed = template.update(**changes)
        if changed:
            await self._repo.save(template)
            if any(
                f in changed
                for f in (
                    "name",
                    "description",
                    "system_prompt",
                    "model_tier",
                    "recommended_skills",
                    "display_name_zh",
                    "description_zh",
                    "compatible_agent_systems",
                    "compatible_providers",
                )
            ):
                file_path = self._dir / template.source_path
                if file_path.exists():
                    body = _read_body_from_file(file_path)
                    new_body = getattr(cmd, "system_prompt", None) or body
                    md_content = _render_markdown(
                        name=template.name,
                        description=template.description,
                        system_prompt=new_body,
                        model_tier=template.model_tier,
                        recommended_skills=template.recommended_skills,
                        display_name_zh=template.display_name_zh,
                        description_zh=template.description_zh,
                        compatible_agent_systems=template.compatible_agent_systems,
                        compatible_providers=template.compatible_providers,
                    )
                    file_path.write_text(md_content, encoding="utf-8")
        return template

    async def delete(self, template_id: UUID) -> None:
        """Soft-delete a local template."""
        template = await self._repo.get_by_id(template_id)
        if template is None:
            raise NotFoundError(f"Template not found: {template_id}")
        if template.source != LOCAL_SOURCE:
            raise DomainError("Only local templates can be deleted")
        await self._repo.soft_delete(template_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get(self, template_id: UUID) -> Template | None:
        return await self._repo.get_by_id(template_id)

    async def get_with_body(self, template_id: UUID) -> tuple[Template, str] | None:
        """Return template + body text from the source markdown file."""
        template = await self._repo.get_by_id(template_id)
        if template is None:
            return None
        body = self._read_body(template)
        return template, body

    async def set_favorite(self, template_id: UUID, cmd) -> Template:
        """Set or update favorite status on a template."""
        template = await self._repo.get_by_id(template_id)
        if template is None:
            raise NotFoundError(f"Template not found: {template_id}")
        data = {
            "is_favorite": cmd.is_favorite,
            "favorite_name": cmd.favorite_name
            if cmd.favorite_name is not None
            else template.favorite_name,
            "favorite_description": cmd.favorite_description
            if cmd.favorite_description is not None
            else template.favorite_description,
            "favorite_order": cmd.favorite_order
            if cmd.favorite_order is not None
            else template.favorite_order,
        }
        updated = await self._repo.set_favorite(template_id, data)
        if updated is None:
            raise NotFoundError(f"Template not found: {template_id}")
        return updated

    async def list_favorites(self) -> list[Template]:
        """List all favorited templates, lazily curating defaults if none exist."""
        await self._ensure_default_favorites()
        return await self._repo.list_favorites()

    _local_seeded: bool = False  # reset on module reload
    _default_favorites_seeded: bool = False

    # -- 8 个默认常用模板 （从 wshobson/agents 仓库精选，source_path 精确匹配）--
    _DEFAULT_FAVORITES: list[dict[str, object]] = [
        {
            "source_path": "plugins/python-development/agents/python-pro.md",
            "favorite_name": "Python 开发专家",
            "favorite_description": "精通 Python 3.12+ 全栈开发，现代工具链与测试",
        },
        {
            "source_path": "plugins/frontend-mobile-development/agents/frontend-developer.md",
            "favorite_name": "前端开发专家",
            "favorite_description": "React/TypeScript 前端开发，组件设计与状态管理",
        },
        {
            "source_path": "plugins/cicd-automation/agents/deployment-engineer.md",
            "favorite_name": "DevOps 工程师",
            "favorite_description": "CI/CD 流水线、容器化部署与基础设施即代码",
        },
        {
            "source_path": "plugins/security-compliance/agents/security-auditor.md",
            "favorite_name": "安全审计专家",
            "favorite_description": "代码安全审查、漏洞检测与合规检查",
        },
        {
            "source_path": "plugins/database-design/agents/database-architect.md",
            "favorite_name": "数据库架构师",
            "favorite_description": "SQL/NoSQL 建模、查询优化与数据架构设计",
        },
        {
            "source_path": "plugins/api-scaffolding/agents/backend-architect.md",
            "favorite_name": "API 设计师",
            "favorite_description": "RESTful/GraphQL API 设计与接口规范",
        },
        {
            "source_path": "plugins/unit-testing/agents/test-automator.md",
            "favorite_name": "测试工程师",
            "favorite_description": "单元/集成/E2E 测试编写，覆盖率优化",
        },
        {
            "source_path": "plugins/documentation-generation/agents/docs-architect.md",
            "favorite_name": "文档工程师",
            "favorite_description": "技术文档、API 文档与知识库编写",
        },
    ]

    async def _ensure_default_favorites(self) -> None:
        """Lazy-init: sync wshobson/agents repo and curate 8 default favorites.

        Idempotent — sets a class-level flag after first successful curation.
        If favorites already exist in DB (e.g. from previous lifecycle), skip.
        """
        if TemplateService._default_favorites_seeded:
            return

        # Check if any favorites already exist — avoid re-syncing
        existing = await self._repo.list_favorites()
        if existing:
            TemplateService._default_favorites_seeded = True
            return

        # No favorites yet — sync from GitHub
        try:
            sync_result = await self.sync_source()
        except SyncError as e:
            logger.warning("Could not sync wshobson/agents for favorites: %s", e)
            TemplateService._default_favorites_seeded = True  # don't retry forever
            return

        total = sync_result.get("total", 0) if isinstance(sync_result, dict) else 0
        if total == 0:
            logger.warning("Sync returned 0 templates; cannot curate favorites")
            TemplateService._default_favorites_seeded = True
            return

        # Gather all synced templates, build source_path lookup
        synced, _ = await self._repo.list(source=DEFAULT_SOURCE_ID, page_size=500)
        by_path: dict[str, Template] = {t.source_path: t for t in synced}

        curated = 0
        for order, fav in enumerate(TemplateService._DEFAULT_FAVORITES, start=1):
            sp = str(fav["source_path"])
            template = by_path.get(sp)
            if template is None:
                logger.warning("Favorite template not found in DB: %s", sp)
                continue
            data = {
                "is_favorite": True,
                "favorite_name": str(fav["favorite_name"]),
                "favorite_description": str(fav["favorite_description"]),
                "favorite_order": order,
            }
            await self._repo.set_favorite(template.id, data)
            curated += 1

        logger.info("Curated %d/8 default favorites", curated)
        TemplateService._default_favorites_seeded = True

    async def list_templates(
        self,
        *,
        q: str | None = None,
        model_tier: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Template], int]:
        await self._ensure_local_templates()
        await self._ensure_skill_creator_skill()
        return await self._repo.list(q=q, model_tier=model_tier, page=page, page_size=page_size)

    async def _ensure_skill_creator_skill(self) -> None:
        """Seed the skill-creator runtime skill into .agenthub/skills/ if missing."""
        skills_dir = self._skills_dir / "skill-creator"
        md_path = skills_dir / "SKILL.md"
        if md_path.exists():
            return
        skills_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_SKILL_CREATOR_MD, encoding="utf-8")
        logger.info("Seeded skill-creator skill at %s", md_path)

    async def _ensure_local_templates(self) -> None:
        """Lazy-init: write 9 local templates to my-templates/ + index into DB."""
        if TemplateService._local_seeded:
            return
        TemplateService._local_seeded = True

        local_dir = self._dir / MY_TEMPLATES_DIR
        local_dir.mkdir(parents=True, exist_ok=True)

        for slug, frontmatter, body in _LOCAL_TEMPLATES:
            tmpl_dir = local_dir / slug
            md_path = tmpl_dir / "SKILL.md"
            if md_path.exists():
                continue
            tmpl_dir.mkdir(parents=True, exist_ok=True)
            md_path.write_text(frontmatter.strip() + "\n\n" + body.strip() + "\n", encoding="utf-8")
            source_path = f"{MY_TEMPLATES_DIR}/{slug}/SKILL.md"
            # Parse frontmatter: skip leading/trailing --- lines
            fm_lines = frontmatter.strip().split("\n")
            fm_dict: dict[str, str] = {}
            for line in fm_lines:
                if line.strip() == "---":
                    continue
                if ":" in line:
                    key, _, val = line.partition(":")
                    fm_dict[key.strip()] = val.strip()
            display_name = fm_dict.get("name", slug)
            t = Template(
                source=LOCAL_SOURCE,
                source_path=source_path,
                name=display_name,
                description=fm_dict.get("description", ""),
                model_tier=fm_dict.get("model", "sonnet"),
                display_name_zh=display_name,
            )

            existing = await self._repo.get_by_source_path(LOCAL_SOURCE, source_path)
            if existing is None:
                await self._repo.save(t)
                logger.info("Seeded local template: %s", slug)

    # ------------------------------------------------------------------
    # Source
    # ------------------------------------------------------------------

    async def get_source_status(self) -> TemplateSource | None:
        return await self._repo.get_source(DEFAULT_SOURCE_ID)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def export_markdown(self, template_id: UUID) -> str | None:
        """Generate a markdown file for download."""
        template = await self._repo.get_by_id(template_id)
        if template is None:
            return None
        body = self._read_body(template)
        return _render_markdown(
            name=template.name,
            description=template.description,
            system_prompt=body,
            model_tier=template.model_tier,
            recommended_skills=template.recommended_skills,
            display_name_zh=template.display_name_zh,
            description_zh=template.description_zh,
            compatible_agent_systems=template.compatible_agent_systems,
            compatible_providers=template.compatible_providers,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_body(self, template: Template) -> str:
        """Read the body (system_prompt) from a template source file."""
        if not template.source_path:
            return ""
        file_path = self._dir / template.source_path
        if not file_path.exists() and template.source != LOCAL_SOURCE:
            file_path = self._dir / "sources" / template.source / template.source_path
        return _read_body_from_file(file_path)


def _read_body_from_file(file_path: Path) -> str:
    """Read markdown body (after frontmatter) from a file."""
    if not file_path.exists():
        return ""
    try:
        raw = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    import re as _re

    fm_re = _re.compile(r"^---\s*\n(.*?)\n---\s*\n", _re.DOTALL)
    fm_match = fm_re.match(raw)
    if fm_match:
        return raw[fm_match.end() :].strip()
    return raw.strip()


def _render_markdown(
    name: str,
    description: str = "",
    system_prompt: str = "",
    model_tier: str = "inherit",
    recommended_skills: list[str] | None = None,
    display_name_zh: str | None = None,
    description_zh: str | None = None,
    compatible_agent_systems: list[str] | None = None,
    compatible_providers: list[str] | None = None,
) -> str:
    """Generate a SKILL.md file with YAML frontmatter."""
    lines: list[str] = ["---"]
    lines.append(f"name: {name}")
    if display_name_zh:
        lines.append(f"display_name_zh: {display_name_zh}")
    lines.append("description: |")
    for ln in (description or "").splitlines() or [description or ""]:
        lines.append(f"  {ln}")
    if description_zh:
        lines.append(f"description_zh: {description_zh}")
    lines.append(f"model_tier: {model_tier}")

    skills = recommended_skills or []
    if skills:
        lines.append("recommended_skills:")
        for s in skills:
            lines.append(f"  - {s}")

    agent_systems = compatible_agent_systems or []
    if agent_systems:
        lines.append("compatible_agent_systems:")
        for a in agent_systems:
            lines.append(f"  - {a}")

    providers = compatible_providers or []
    if providers:
        lines.append("compatible_providers:")
        for p in providers:
            lines.append(f"  - {p}")

    lines.append("---")
    lines.append("")
    if system_prompt:
        lines.append(system_prompt)
    else:
        lines.append(f"# {name}")
        lines.append("")
        if description:
            lines.append(description)
    return "\n".join(lines) + "\n"


def _discover_plugin_skills(repo_dir: Path, source_path: str) -> list[str]:
    """Find skill slugs in the same plugin directory as an agent .md file.

    source_path: e.g. plugins/cicd-automation/agents/deployment-engineer.md
    Returns: ['deployment-pipeline-design', 'github-actions-templates', ...]
    """
    agent_path = Path(source_path)
    plugin_dir = (
        agent_path.parent.parent if agent_path.parent.name == "agents" else agent_path.parent
    )
    skills_dir = repo_dir / plugin_dir / "skills"
    if not skills_dir.is_dir():
        return []
    slugs: list[str] = []
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            slugs.append(child.name)
    return slugs


def _symlink_plugin_skills(repo_dir: Path, skills_dir: Path) -> None:
    """Symlink all plugin skills from the cloned repo into the local skill library.

    Scans plugins/*/skills/*/SKILL.md and creates symlinks:
      skills_dir/{skill-slug} → repo_dir/plugins/{plugin}/skills/{skill-slug}

    Existing symlinks or directories are skipped (no overwrite).
    """
    plugins_dir = repo_dir / "plugins"
    if not plugins_dir.is_dir():
        return
    skills_dir.mkdir(parents=True, exist_ok=True)
    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue
        plugin_skills = plugin_dir / "skills"
        if not plugin_skills.is_dir():
            continue
        for skill_dir in plugin_skills.iterdir():
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
                continue
            slug = skill_dir.name
            target = skills_dir / slug
            if target.exists():
                continue  # already has a local copy or symlink
            try:
                target.symlink_to(skill_dir.resolve(), target_is_directory=True)
                logger.info("Symlinked plugin skill: %s → %s", slug, skill_dir)
            except OSError as e:
                logger.warning("Failed to symlink skill %s: %s", slug, e)


# -- 9 个本地模板定义 (slug, YAML frontmatter, markdown body) --
_LOCAL_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "tech-lead",
        "---\nname: 技术负责人\ndescription: 拆任务、排顺序、盯风险，协调工程师、评审和测试交付结果\nmodel: sonnet\ncolor: indigo\n---",
        "# 技术负责人\n\n你是资深技术负责人（Tech Lead），负责将模糊需求转化为可执行的技术任务。\n\n## Purpose\n接收产品需求后拆解为清晰、可验证的技术子任务，排序优先级，识别风险点，给出分步执行计划。\n\n## Capabilities\n- 需求→结构化任务分解（WBS）\n- 依赖关系分析与拓扑排序\n- 风险矩阵（可能性×影响程度）\n- 工时估算与时间线建议\n- 技术方案对比（≥2选项）\n\n## Behavioral Traits\n- 严谨：拒绝猜测，给边界条件\n- 务实：优先 MVP，再迭代增强\n\n## Constraints\n- 不写代码，只给技术方向\n- 单一任务≤4h，超出继续拆\n- 不引入 spec 没列的额外功能",
    ),
    (
        "engineer",
        "---\nname: 工程师\ndescription: 接需求、写代码、上线。修 bug 比写代码还熟\nmodel: sonnet\ncolor: blue\n---",
        "# 工程师\n\n你是全栈工程师，接收明确的技术任务规格后交付高质量代码实现。\n\n## Purpose\n基于任务描述、技术栈约束和验收标准，编写可运行、可测试、符合项目规范的生产级代码。\n\n## Capabilities\n- 前端 React/TypeScript + 后端 FastAPI/Python\n- 数据库 SQLAlchemy ORM + Alembic\n- 单元/集成测试 pytest\n- 错误处理与边界条件全覆盖\n\n## Constraints\n- 禁止裸 print/console.log/any\n- 禁止同步阻塞 FastAPI (CR-12)\n- 组件>200行必须拆分 (CR-07)\n- 改数据库走 Alembic (CR-03)",
    ),
    (
        "code-reviewer",
        "---\nname: 代码评审\ndescription: 审 diff、提风险、走查测试、把合并前最后一道关\nmodel: sonnet\ncolor: amber\n---",
        "# 代码评审\n\n你是代码评审专家，审查 diff 的正确性、可维护性和安全性。\n\n## Purpose\n对代码 diff 全面审查，识别 bug、性能问题、安全漏洞和规范违反，给出可操作的修改建议。\n\n## Behavioral Traits\n- 每指出一个问题必给具体修复方案\n- 分优先级：Critical→Major→Minor→Nit\n- 引用代码行号和规范编号\n\n## Constraints\n- 不审查注释风格/格式\n- 不修改代码，只审查",
    ),
    (
        "tester",
        "---\nname: 测试\ndescription: 复现问题、跑验收、做回归，把用户路径测到真的能用\nmodel: sonnet\ncolor: emerald\n---",
        "# 测试\n\n你是测试工程师，负责设计测试用例、复现缺陷、验证修复和执行回归测试。\n\n## Purpose\n基于功能规格和代码变更编写测试计划，确保软件质量符合验收标准。\n\n## Capabilities\n- 测试用例设计（等价类、边界值、场景法）\n- pytest 单元/集成/E2E 测试\n- Bug 复现步骤最小化\n- 测试覆盖率分析\n\n## Constraints\n- 测试必须独立 (T-01)\n- Mock 外部依赖边界 (T-02)\n- 不写 flaky test (T-04)\n- Adapter & FSM 必测 (T-05)",
    ),
    (
        "product-manager",
        "---\nname: 产品经理\ndescription: 定方向、拆需求、写 PRD、推进交付\nmodel: sonnet\ncolor: violet\n---",
        "# 产品经理\n\n你是产品经理，负责理解用户问题和市场机会，将其转化为清晰的 PRD。\n\n## Purpose\n从用户反馈和业务目标出发，定义产品功能范围、优先级和验收标准。\n\n## Capabilities\n- 用户故事编写（As a / I want / So that）\n- 功能优先级排序（MoSCoW 或 RICE）\n- 验收标准定义（Given / When / Then）\n\n## Constraints\n- 不写技术实现\n- PRD ≤ 5 页核心内容",
    ),
    (
        "copywriter",
        "---\nname: 文案\ndescription: 写公众号、邮件、品牌稿。卖点和故事都能写\nmodel: haiku\ncolor: rose\n---",
        "# 文案\n\n你是专业文案，擅长用精准语言传达品牌价值，覆盖公众号、邮件、社交媒体和品牌故事。\n\n## Capabilities\n- 公众号长文（结构清晰、有金句、可扫读）\n- 营销邮件（标题吸引、CTA 明确）\n- 社交媒体短文案\n\n## Constraints\n- 不写虚假宣传或夸大文案\n- 政治、医疗、法律领域拒绝",
    ),
    (
        "editor",
        "---\nname: 编辑\ndescription: 调语气、改结构、控篇幅，把稿子打磨到能发\nmodel: haiku\ncolor: teal\n---",
        "# 编辑\n\n你是内容编辑，负责修改润色已有文字，提升可读性、逻辑性和感染力。\n\n## Capabilities\n- 结构调整（段落重组、信息层次优化）\n- 语气调整（正式/亲切/幽默自由切换）\n- 去冗余（删废话、缩长句）\n\n## Constraints\n- 尊重原作独特声音\n- 学术引用/数据不擅改",
    ),
    (
        "outreach-copywriter",
        "---\nname: 外联文案\ndescription: 陌拜信、跟进序列、销售话术都他写。盯回复率反复优化\nmodel: haiku\ncolor: orange\n---",
        "# 外联文案\n\n你是外联文案专家，专注商务拓展场景的文字策略。\n\n## Purpose\n为 BD/Sales 团队提供高效的外联文字方案，最大化回复率和转化率。\n\n## Capabilities\n- 冷启动邮件/私信\n- 跟进序列设计（Day 1/3/7/14 节奏）\n- 异议处理话术\n\n## Constraints\n- 不教人 spam\n- 每封邮件 ≤ 150 字（冷启动场景）",
    ),
    (
        "skill-creator",
        "---\nname: Skill 设计师\ndescription: 设计 Claude Code Skills — 多轮对话式创建全流程\nmodel: sonnet\ncolor: purple\n---",
        "# Skill 设计师\n\n你是 Skill 设计师，通过多轮对话帮用户创建高质量、可复用的 Skills。\n\n## Purpose\n引导用户完成 Skill 创建：需求梳理→元数据→指令→范例→打磨→发布。\n\n## Response Approach\n### Phase 1 — 探索\n逐一提问：核心功能、触发场景、执行步骤、使用示例、特殊约束。\n\n### Phase 2 — 草稿生成\n生成完整 SKILL.md，询问是否满足需求。\n\n### Phase 3 — 修改循环（≤3 轮）\n\n### Phase 4 — 最终确认\n确认后保存到 {SKILLS_DIR}/{slug}/SKILL.md\n\n## Constraints\n- name 必须 kebab-case ≤40 字符\n- description 用中文 ≤200 字符\n- triggers 中文短词 3-7 个\n- 一次只创建一个 skill\n- SKILL.md 必须用 ```markdown 代码块包裹",
    ),
]

_SKILL_CREATOR_MD = """\
---
name: skill-creator
description: 通过多轮对话帮你创建新的 Claude Code Skill，4 阶段引导式交互
version: 1.0.0
triggers:
  - "创建skill"
  - "新建skill"
  - "帮我做一个skill"
  - "create skill"
  - "写一个skill"
---

# Skill Creator

你是一个 Skill 创建助手，通过多轮对话引导用户创建高质量、可复用的 Claude Code Skills。

## 核心理念

好的 Skill 是一次性的"培训投入"，让 Claude 在未来所有相关任务中都能按你的标准执行。Skill 不是简单的 prompt，而是包含触发条件、执行协议、边界约束和输出格式的完整说明书。

## 四个阶段

### Phase 1 — 探索

逐一确认以下信息（每次最多问 2-3 个问题）：

1. **核心功能**：这个 Skill 要解决什么问题？用户完成什么任务？
2. **触发场景**：什么情况下应该调用这个 Skill？（用中文列 3-7 个触发短语）
3. **执行步骤**：Claude 接到任务后应该按什么顺序执行？（分步描述）
4. **输入/输出**：需要什么输入信息？输出什么格式？
5. **边界约束**：什么情况下不应该用这个 Skill？有什么绝对不能做的事？

### Phase 2 — 草稿

根据 Phase 1 收集的信息，生成完整的 SKILL.md 草稿。草稿必须包含 YAML frontmatter 和完整的 Markdown 内容。展示草稿并询问："这个 Skill 满足你的需求吗？有没有需要调整的地方？"

### Phase 3 — 修改循环（≤3 轮）

根据用户反馈修改 SKILL.md。每次修改后再次确认。超过 3 轮仍未满意，建议用户先手动调整核心部分再继续。

### Phase 4 — 保存

确认用户满意后：

1. 确定 slug（从 name 派生，kebab-case）
2. 创建目录 {SKILLS_DIR}/{slug}/
3. 将 SKILL.md 写入该目录
4. 告知用户保存路径，提示可立即使用

## 约束规则

- name 必须 kebab-case，≤40 字符
- description 用中文，≤200 字符
- triggers 用中文短词，3-7 个
- 一次只创建一个 Skill
- SKILL.md 用 YAML frontmatter + Markdown 格式
- 保存到 SKILLS_DIR 环境变量指定的目录，默认 .agenthub/skills
- 如果目标目录已存在同名 Skill，先询问是否覆盖
- 绝不代替用户做实质性决策，每个关键选择都需用户确认

## 质量标准

一个好的 SKILL.md 应该：
- 触发条件精确：不会在不相关场景误触发
- 步骤可执行：每一步 Claude 都能独立完成
- 输出格式化：有清晰的模板，不是自由文本
- 边界明确：清楚说明什么不做、什么不能做
- 示例驱动：包含至少 1 个使用示例
"""
