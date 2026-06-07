"""TemplateRepository abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.template import Template, TemplateSource


class TemplateRepository(ABC):
    @abstractmethod
    async def save(self, template: Template) -> None: ...

    @abstractmethod
    async def bulk_upsert(self, templates: list[Template]) -> dict[str, int]: ...

    @abstractmethod
    async def get_by_id(self, template_id: UUID) -> Template | None: ...

    @abstractmethod
    async def get_by_source_path(self, source: str, source_path: str) -> Template | None: ...

    @abstractmethod
    async def list(
        self,
        *,
        q: str | None = None,
        model_tier: str | None = None,
        source: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Template], int]: ...

    @abstractmethod
    async def soft_delete(self, template_id: UUID) -> None: ...

    @abstractmethod
    async def get_source(self, source_id: str) -> TemplateSource | None: ...

    @abstractmethod
    async def save_source(self, source: TemplateSource) -> None: ...

    @abstractmethod
    async def mark_source_synced(
        self, source_id: str, template_count: int, deleted_paths: list[str]
    ) -> None: ...

    @abstractmethod
    async def set_favorite(self, template_id: UUID, data: dict) -> Template | None: ...

    @abstractmethod
    async def list_favorites(self) -> list[Template]: ...
