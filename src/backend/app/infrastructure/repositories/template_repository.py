"""PostgresTemplateRepository: SQLAlchemy implementation of TemplateRepository."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.template import Template, TemplateSource
from app.domain.repositories import TemplateRepository
from app.infrastructure.db.models import TemplateModel, TemplateSourceModel

logger = logging.getLogger(__name__)


def _to_domain_template(m: TemplateModel) -> Template:
    return Template(
        id=m.id,
        source=m.source,
        source_path=m.source_path,
        name=m.name,
        description=m.description,
        model_tier=m.model_tier,
        tools=list(m.tools or []),
        color=m.color,
        display_name_zh=m.display_name_zh,
        description_zh=m.description_zh,
        recommended_skills=list(m.recommended_skills or []),
        compatible_agent_systems=list(m.compatible_agent_systems or []),
        compatible_providers=list(m.compatible_providers or []),
        is_enabled=m.is_enabled,
        is_favorite=m.is_favorite,
        favorite_name=m.favorite_name,
        favorite_description=m.favorite_description,
        favorite_order=m.favorite_order,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_model_template(t: Template) -> TemplateModel:
    return TemplateModel(
        id=t.id,
        source=t.source,
        source_path=t.source_path,
        name=t.name,
        description=t.description,
        model_tier=t.model_tier,
        tools=t.tools,
        color=t.color,
        display_name_zh=t.display_name_zh,
        description_zh=t.description_zh,
        recommended_skills=t.recommended_skills,
        compatible_agent_systems=t.compatible_agent_systems,
        compatible_providers=t.compatible_providers,
        is_enabled=t.is_enabled,
        is_favorite=t.is_favorite,
        favorite_name=t.favorite_name,
        favorite_description=t.favorite_description,
        favorite_order=t.favorite_order,
    )


def _to_domain_source(m: TemplateSourceModel) -> TemplateSource:
    return TemplateSource(
        id=m.id,
        url=m.url,
        branch=m.branch,
        description_zh=m.description_zh,
        enabled=m.enabled,
        template_count=m.template_count,
        last_synced=m.last_synced,
        created_at=m.created_at,
    )


class PostgresTemplateRepository(TemplateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, template: Template) -> None:
        existing = await self._s.get(TemplateModel, template.id)
        if existing is None:
            self._s.add(_to_model_template(template))
        else:
            self._update_model(existing, template)
        await self._s.flush()

    async def bulk_upsert(self, templates):
        if not templates:
            return {"added": 0, "updated": 0, "deleted": 0}

        source = templates[0].source
        stmt = select(TemplateModel).where(
            TemplateModel.source == source,
            TemplateModel.is_deleted.is_(False),
        )
        existing_rows = (await self._s.execute(stmt)).scalars().all()
        existing_by_path = {row.source_path: row for row in existing_rows}

        added = 0
        updated = 0
        incoming_paths = set()
        for t in templates:
            incoming_paths.add(t.source_path)
            existing = existing_by_path.get(t.source_path)
            if existing is None:
                self._s.add(_to_model_template(t))
                added += 1
            else:
                self._update_model(existing, t)
                updated += 1

        deleted = 0
        for path, row in existing_by_path.items():
            if path not in incoming_paths:
                row.is_deleted = True
                deleted += 1

        await self._s.flush()
        return {"added": added, "updated": updated, "deleted": deleted}

    async def get_by_id(self, template_id):
        m = await self._s.get(TemplateModel, template_id)
        if m is None or m.is_deleted:
            return None
        return _to_domain_template(m)

    async def get_by_source_path(self, source, source_path):
        stmt = select(TemplateModel).where(
            TemplateModel.source == source,
            TemplateModel.source_path == source_path,
            TemplateModel.is_deleted.is_(False),
        )
        m = (await self._s.execute(stmt)).scalars().first()
        return _to_domain_template(m) if m else None

    async def list(self, *, q=None, model_tier=None, source=None, page=1, page_size=20):
        stmt = select(TemplateModel).where(TemplateModel.is_deleted.is_(False))

        if q:
            q_like = "%" + q + "%"
            stmt = stmt.where(
                or_(
                    TemplateModel.name.ilike(q_like),
                    TemplateModel.description.ilike(q_like),
                    TemplateModel.display_name_zh.ilike(q_like),
                )
            )
        if model_tier:
            stmt = stmt.where(TemplateModel.model_tier == model_tier)
        if source:
            stmt = stmt.where(TemplateModel.source == source)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._s.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(TemplateModel.updated_at.desc()).offset(offset).limit(page_size)
        rows = (await self._s.execute(stmt)).scalars().all()

        return [_to_domain_template(m) for m in rows], total

    async def soft_delete(self, template_id):
        m = await self._s.get(TemplateModel, template_id)
        if m is not None:
            m.is_deleted = True
            await self._s.flush()

    async def get_source(self, source_id):
        m = await self._s.get(TemplateSourceModel, source_id)
        return _to_domain_source(m) if m else None

    async def save_source(self, source):
        existing = await self._s.get(TemplateSourceModel, source.id)
        if existing is None:
            self._s.add(
                TemplateSourceModel(
                    id=source.id,
                    url=source.url,
                    branch=source.branch,
                    description_zh=source.description_zh,
                    enabled=source.enabled,
                    template_count=source.template_count,
                    last_synced=source.last_synced,
                )
            )
        else:
            existing.url = source.url
            existing.branch = source.branch
            existing.description_zh = source.description_zh
            existing.enabled = source.enabled
            existing.template_count = source.template_count
            existing.last_synced = source.last_synced
        await self._s.flush()

    async def mark_source_synced(self, source_id, template_count, deleted_paths):
        m = await self._s.get(TemplateSourceModel, source_id)
        if m is not None:
            m.template_count = template_count
            m.last_synced = datetime.now(UTC)
            await self._s.flush()

    async def set_favorite(self, template_id, data):
        """Update favorite fields on a template. Returns updated domain entity or None."""
        m = await self._s.get(TemplateModel, template_id)
        if m is None or m.is_deleted:
            return None
        changed = False
        for field in ("is_favorite", "favorite_name", "favorite_description", "favorite_order"):
            val = data.get(field)
            if val is not None:
                setattr(m, field, val)
                changed = True
        if changed:
            m.updated_at = datetime.now(UTC)
            await self._s.flush()
        return _to_domain_template(m)

    async def list_favorites(self):
        """Return all favorited templates, ordered by favorite_order then name."""
        stmt = (
            select(TemplateModel)
            .where(
                TemplateModel.is_deleted.is_(False),
                TemplateModel.is_favorite.is_(True),
            )
            .order_by(TemplateModel.favorite_order, TemplateModel.name)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain_template(m) for m in rows]

    @staticmethod
    def _update_model(m, t):
        m.name = t.name
        m.description = t.description
        m.model_tier = t.model_tier
        m.tools = t.tools
        m.color = t.color
        m.display_name_zh = t.display_name_zh
        m.description_zh = t.description_zh
        m.recommended_skills = t.recommended_skills
        m.compatible_agent_systems = t.compatible_agent_systems
        m.compatible_providers = t.compatible_providers
        m.is_enabled = t.is_enabled
        m.is_favorite = t.is_favorite
        m.favorite_name = t.favorite_name
        m.favorite_description = t.favorite_description
        m.favorite_order = t.favorite_order
