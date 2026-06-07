"""Template Pydantic schemas (L4)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    system_prompt: str = ""
    model_tier: str = "inherit"
    recommended_skills: list[str] = Field(default_factory=list)
    display_name_zh: str | None = None
    description_zh: str | None = None
    compatible_agent_systems: list[str] = Field(default_factory=list)
    compatible_providers: list[str] = Field(default_factory=list)
    is_favorite: bool = False
    favorite_name: str | None = None
    favorite_description: str | None = None


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_tier: str | None = None
    recommended_skills: list[str] | None = None
    display_name_zh: str | None = None
    description_zh: str | None = None
    compatible_agent_systems: list[str] | None = None
    compatible_providers: list[str] | None = None
    is_enabled: bool | None = None


class FavoriteUpdateRequest(BaseModel):
    is_favorite: bool
    favorite_name: str | None = None
    favorite_description: str | None = None
    favorite_order: int | None = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    source_path: str
    name: str
    description: str
    model_tier: str
    tools: list[str]
    color: str | None
    display_name_zh: str | None
    description_zh: str | None
    recommended_skills: list[str]
    compatible_agent_systems: list[str]
    compatible_providers: list[str]
    is_enabled: bool
    is_favorite: bool
    favorite_name: str | None
    favorite_description: str | None
    favorite_order: int
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, template) -> TemplateOut:
        return cls(
            id=template.id,
            source=template.source,
            source_path=template.source_path,
            name=template.name,
            description=template.description,
            model_tier=template.model_tier,
            tools=template.tools,
            color=template.color,
            display_name_zh=template.display_name_zh,
            description_zh=template.description_zh,
            recommended_skills=template.recommended_skills,
            compatible_agent_systems=template.compatible_agent_systems,
            compatible_providers=template.compatible_providers,
            is_enabled=template.is_enabled,
            is_favorite=template.is_favorite,
            favorite_name=template.favorite_name,
            favorite_description=template.favorite_description,
            favorite_order=template.favorite_order,
            created_at=template.created_at.isoformat()
            if hasattr(template.created_at, "isoformat")
            else str(template.created_at),
            updated_at=template.updated_at.isoformat()
            if hasattr(template.updated_at, "isoformat")
            else str(template.updated_at),
        )


class TemplateDetailOut(TemplateOut):
    system_prompt: str = ""


class TemplateListOut(BaseModel):
    items: list[TemplateOut]
    total: int
    page: int
    page_size: int


class TemplateSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    url: str
    branch: str
    description_zh: str | None
    enabled: bool
    template_count: int
    last_synced: str | None
    created_at: str


class SyncResultOut(BaseModel):
    source_id: str
    added: int
    updated: int
    deleted: int
    total: int
    error: str | None = None
