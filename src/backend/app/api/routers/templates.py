"""Template API router: list, detail, CRUD, sync, export."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.api.deps import get_template_service
from app.application.services.template_service import TemplateService
from app.core.exceptions import DomainError, NotFoundError, SyncError
from app.schemas.template import (
    FavoriteUpdateRequest,
    SyncResultOut,
    TemplateCreateRequest,
    TemplateDetailOut,
    TemplateListOut,
    TemplateOut,
    TemplateSourceOut,
    TemplateUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])


# ── GET / — list templates ────────────────────────────────────────


@router.get("/", response_model=TemplateListOut)
async def list_templates(
    q: str | None = Query(None, description="Search query (name, description, zh name)"),
    model_tier: str | None = Query(None, description="Filter by model tier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: TemplateService = Depends(get_template_service),
):
    """List all templates with optional search and pagination."""
    items, total = await svc.list_templates(
        q=q, model_tier=model_tier, page=page, page_size=page_size
    )
    return TemplateListOut(
        items=[TemplateOut.from_domain(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /favorites — list favorited templates ────────────────────────


@router.get("/favorites", response_model=list[TemplateOut])
async def list_favorites(
    svc: TemplateService = Depends(get_template_service),
):
    """List all favorited templates, ordered by favorite_order."""
    items = await svc.list_favorites()
    return [TemplateOut.from_domain(t) for t in items]


# ── GET /{template_id} — detail with body ──────────────────────────


@router.get("/{template_id}", response_model=TemplateDetailOut)
async def get_template(
    template_id: UUID,
    svc: TemplateService = Depends(get_template_service),
):
    """Get a template with full details including body (system_prompt)."""
    result = await svc.get_with_body(template_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Template not found")
    template, body = result
    out = TemplateDetailOut.from_domain(template)
    out.system_prompt = body
    return out


# ── POST / — create local template ─────────────────────────────────


@router.post("/", response_model=TemplateOut, status_code=201)
async def create_template(
    body: TemplateCreateRequest,
    svc: TemplateService = Depends(get_template_service),
):
    """Create a new local template."""
    try:
        template = await svc.create(body)
        return TemplateOut.from_domain(template)
    except DomainError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


# ── PATCH /{template_id} — update local template ───────────────────


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: UUID,
    body: TemplateUpdateRequest,
    svc: TemplateService = Depends(get_template_service),
):
    """Update a local template. Only local templates can be updated."""
    try:
        template = await svc.update(template_id, body)
        return TemplateOut.from_domain(template)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except DomainError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


# ── PATCH /{template_id}/favorite — toggle favorite ──────────────────


@router.patch("/{template_id}/favorite", response_model=TemplateOut)
async def set_favorite(
    template_id: UUID,
    body: FavoriteUpdateRequest,
    svc: TemplateService = Depends(get_template_service),
):
    """Set or unset a template as favorite with optional custom name/description/order."""
    try:
        template = await svc.set_favorite(template_id, body)
        return TemplateOut.from_domain(template)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ── DELETE /{template_id} — 204 ────────────────────────────────────


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    svc: TemplateService = Depends(get_template_service),
):
    """Soft-delete a local template."""
    try:
        await svc.delete(template_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except DomainError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


# ── POST /sync — sync from GitHub ──────────────────────────────────


@router.post("/sync", response_model=SyncResultOut)
async def sync_templates(
    svc: TemplateService = Depends(get_template_service),
):
    """Sync templates from the default GitHub source (wshobson/agents)."""
    try:
        result = await svc.sync_source()
        return SyncResultOut(**result)
    except SyncError as e:
        logger.exception("Template sync failed")
        raise HTTPException(status_code=502, detail=str(e)) from e


# ── GET /source/status — source info ───────────────────────────────


@router.get("/source/status", response_model=TemplateSourceOut | None)
async def get_source_status(
    svc: TemplateService = Depends(get_template_service),
):
    """Get template source status (last sync, count, etc.)."""
    source = await svc.get_source_status()
    if source is None:
        return None
    return TemplateSourceOut(
        id=source.id,
        url=source.url,
        branch=source.branch,
        description_zh=source.description_zh,
        enabled=source.enabled,
        template_count=source.template_count,
        last_synced=source.last_synced.isoformat() if source.last_synced else None,
        created_at=source.created_at.isoformat()
        if hasattr(source.created_at, "isoformat")
        else str(source.created_at),
    )


# ── GET /{template_id}/export — StreamingResponse .md download ─────


@router.get("/{template_id}/export")
async def export_template(
    template_id: UUID,
    svc: TemplateService = Depends(get_template_service),
):
    """Export a template as a downloadable .md file."""
    md_content = await svc.export_markdown(template_id)
    if md_content is None:
        raise HTTPException(status_code=404, detail="Template not found")

    template = await svc.get(template_id)
    filename = "%s.md" % (template.name if template else "template")

    return StreamingResponse(
        iter([md_content]),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
