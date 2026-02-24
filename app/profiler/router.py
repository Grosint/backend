"""Profiler API router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.core.auth_dependencies import require_feature
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.profiler.deps import check_profiler_clearance, resolve_org_id
from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.case import ProfilerCase
from app.profiler.models.job import ProfilerJob
from app.profiler.models.target import ProfilerTarget
from app.profiler.schemas.artifact import ArtifactResponse
from app.profiler.schemas.case import CaseCreate, CaseResponse
from app.profiler.schemas.inference import InferenceRequest
from app.profiler.schemas.job import JobResponse
from app.profiler.schemas.target import TargetCreate, TargetResponse
from app.profiler.services.job_service import JobService
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/profiler", tags=["profiler"])
logger = logging.getLogger(__name__)


def _require_profiler_enabled() -> None:
    if not settings.PROFILER_ENABLED:
        raise NotFoundException("Profiler", "Profiler is disabled")


# ---------- Cases ----------


@router.post("/cases", response_model=SuccessResponse[CaseResponse])
async def create_case(
    body: CaseCreate,
    current_user: User = Depends(require_feature("PROFILER")),
):
    _require_profiler_enabled()
    org_id = await resolve_org_id(current_user, body.org_id)
    case = ProfilerCase(
        org_id=org_id,
        name=body.name,
        description=body.description,
        created_by=current_user.id,
    )
    await case.insert()
    return SuccessResponse(
        message="Case created",
        data=CaseResponse(
            id=str(case.id),
            org_id=str(case.org_id),
            name=case.name,
            description=case.description,
            created_by=str(case.created_by),
            created_at=case.created_at,
            updated_at=case.updated_at,
        ),
    )


@router.get("/cases", response_model=SuccessResponse[list[CaseResponse]])
async def list_cases(
    current_user: User = Depends(require_feature("PROFILER")),
):
    _require_profiler_enabled()
    org_id = await resolve_org_id(current_user, None)
    cursor = ProfilerCase.find(ProfilerCase.org_id == org_id)
    cases = await cursor.sort(-ProfilerCase.created_at).to_list()
    return SuccessResponse(
        message="Cases retrieved",
        data=[
            CaseResponse(
                id=str(c.id),
                org_id=str(c.org_id),
                name=c.name,
                description=c.description,
                created_by=str(c.created_by),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in cases
        ],
    )


@router.get("/cases/{case_id}", response_model=SuccessResponse[CaseResponse])
async def get_case(
    case_id: str,
    current_user: User = Depends(require_feature("PROFILER")),
):
    _require_profiler_enabled()
    case = await ProfilerCase.get(case_id)
    if not case:
        raise NotFoundException("Case", case_id)
    if not await check_profiler_clearance(current_user, case.org_id):
        from app.core.exceptions import AuthorizationException

        raise AuthorizationException("Access denied to this case")
    return SuccessResponse(
        message="Case retrieved",
        data=CaseResponse(
            id=str(case.id),
            org_id=str(case.org_id),
            name=case.name,
            description=case.description,
            created_by=str(case.created_by),
            created_at=case.created_at,
            updated_at=case.updated_at,
        ),
    )


# ---------- Targets ----------


@router.post("/cases/{case_id}/targets", response_model=SuccessResponse[TargetResponse])
async def create_target(
    case_id: str,
    body: TargetCreate,
    current_user: User = Depends(require_feature("PROFILER")),
):
    _require_profiler_enabled()
    case = await ProfilerCase.get(case_id)
    if not case:
        raise NotFoundException("Case", case_id)
    if not await check_profiler_clearance(current_user, case.org_id):
        from app.core.exceptions import AuthorizationException

        raise AuthorizationException("Access denied")
    from app.profiler.utils.url_detect import (
        detect_source_by_hostname,
        normalize_canonical_url,
    )

    if body.target_type == "url":
        canonical_url = normalize_canonical_url(body.input_value)
        detected_source = detect_source_by_hostname(body.input_value)
    else:
        from app.profiler.services.connectors import (
            BlogPublicConnector,
            FacebookPublicConnector,
            InstagramPublicConnector,
            LinkedInPublicConnector,
            RedditPublicConnector,
            XPublicConnector,
        )

        iv = body.input_value.lower()
        if "instagram" in iv or "insta" in iv:
            result = InstagramPublicConnector().resolve(body.input_value, "username")
        elif "facebook" in iv or "fb." in iv or "fb.com" in iv:
            result = FacebookPublicConnector().resolve(body.input_value, "username")
        elif "linkedin" in iv or "linked.in" in iv:
            result = LinkedInPublicConnector().resolve(body.input_value, "username")
        elif "reddit" in iv or "redd.it" in iv:
            result = RedditPublicConnector().resolve(body.input_value, "username")
        elif any(p in iv for p in ("medium", "substack", "blog")):
            result = BlogPublicConnector().resolve(body.input_value, "username")
        else:
            result = XPublicConnector().resolve(body.input_value, "username")
        detected_source = result.detected_source
        canonical_url = result.canonical_url

    target = ProfilerTarget(
        case_id=case.id,
        org_id=case.org_id,
        created_by=current_user.id,
        target_type=body.target_type,
        input_value=body.input_value,
        detected_source=detected_source,
        canonical_url=canonical_url,
    )
    await target.insert()
    return SuccessResponse(
        message="Target created",
        data=TargetResponse(
            id=str(target.id),
            case_id=str(target.case_id),
            org_id=str(target.org_id),
            created_by=str(target.created_by),
            target_type=target.target_type,
            input_value=target.input_value,
            detected_source=target.detected_source,
            canonical_url=target.canonical_url,
            created_at=target.created_at,
        ),
    )


@router.get(
    "/cases/{case_id}/targets", response_model=SuccessResponse[list[TargetResponse]]
)
async def list_targets(
    case_id: str,
    current_user: User = Depends(require_feature("PROFILER")),
):
    _require_profiler_enabled()
    case = await ProfilerCase.get(case_id)
    if not case:
        raise NotFoundException("Case", case_id)
    if not await check_profiler_clearance(current_user, case.org_id):
        from app.core.exceptions import AuthorizationException

        raise AuthorizationException("Access denied")
    cursor = ProfilerTarget.find(ProfilerTarget.case_id == case.id)
    targets = await cursor.sort(-ProfilerTarget.created_at).to_list()
    return SuccessResponse(
        message="Targets retrieved",
        data=[
            TargetResponse(
                id=str(t.id),
                case_id=str(t.case_id),
                org_id=str(t.org_id),
                created_by=str(t.created_by),
                target_type=t.target_type,
                input_value=t.input_value,
                detected_source=t.detected_source,
                canonical_url=t.canonical_url,
                created_at=t.created_at,
            )
            for t in targets
        ],
    )


@router.post(
    "/cases/{case_id}/targets/{target_id}/collect",
    response_model=SuccessResponse[JobResponse],
)
async def collect_target(
    case_id: str,
    target_id: str,
    current_user: User = Depends(require_feature("PROFILER")),
):
    """Enqueue public_capture job."""
    _require_profiler_enabled()
    case = await ProfilerCase.get(case_id)
    if not case:
        raise NotFoundException("Case", case_id)
    target = await ProfilerTarget.get(target_id)
    if not target or str(target.case_id) != str(case_id):
        raise NotFoundException("Target", target_id)
    if not await check_profiler_clearance(current_user, case.org_id):
        from app.core.exceptions import AuthorizationException

        raise AuthorizationException("Access denied")
    job_svc = JobService()
    job = await job_svc.enqueue_public_capture(
        case_id=case_id,
        target_id=target_id,
        org_id=str(case.org_id),
        created_by=str(current_user.id),
    )
    return SuccessResponse(
        message="Collect job enqueued",
        data=JobResponse(
            id=str(job.id),
            case_id=str(job.case_id),
            target_id=str(job.target_id),
            org_id=str(job.org_id),
            created_by=str(job.created_by),
            job_type=job.job_type,
            status=job.status,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error=job.error,
            metrics=job.metrics or {},
        ),
    )


@router.get("/jobs/{job_id}", response_model=SuccessResponse[JobResponse])
async def get_job(
    job_id: str,
    current_user: User = Depends(require_feature("PROFILER")),
):
    _require_profiler_enabled()
    job = await ProfilerJob.get(job_id)
    if not job:
        raise NotFoundException("Job", job_id)
    if not await check_profiler_clearance(current_user, job.org_id):
        from app.core.exceptions import AuthorizationException

        raise AuthorizationException("Access denied")
    return SuccessResponse(
        message="Job retrieved",
        data=JobResponse(
            id=str(job.id),
            case_id=str(job.case_id),
            target_id=str(job.target_id),
            org_id=str(job.org_id),
            created_by=str(job.created_by),
            job_type=job.job_type,
            status=job.status,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error=job.error,
            metrics=job.metrics or {},
        ),
    )


@router.get(
    "/cases/{case_id}/targets/{target_id}/artifacts",
    response_model=SuccessResponse[list[ArtifactResponse]],
)
async def list_artifacts(
    case_id: str,
    target_id: str,
    current_user: User = Depends(require_feature("PROFILER")),
):
    _require_profiler_enabled()
    case = await ProfilerCase.get(case_id)
    if not case:
        raise NotFoundException("Case", case_id)
    target = await ProfilerTarget.get(target_id)
    if not target or str(target.case_id) != str(case_id):
        raise NotFoundException("Target", target_id)
    if not await check_profiler_clearance(current_user, case.org_id):
        from app.core.exceptions import AuthorizationException

        raise AuthorizationException("Access denied")
    cursor = ProfilerArtifact.find(
        ProfilerArtifact.case_id == case.id,
        ProfilerArtifact.target_id == target.id,
    )
    artifacts = await cursor.sort(-ProfilerArtifact.created_at).to_list()
    return SuccessResponse(
        message="Artifacts retrieved",
        data=[
            ArtifactResponse(
                id=str(a.id),
                org_id=str(a.org_id),
                case_id=str(a.case_id),
                target_id=str(a.target_id),
                job_id=str(a.job_id),
                artifact_type=a.artifact_type,
                version=a.version,
                payload=a.payload,
                evidence_ids=a.evidence_ids,
                created_at=a.created_at,
            )
            for a in artifacts
        ],
    )


@router.post(
    "/cases/{case_id}/targets/{target_id}/infer",
    response_model=SuccessResponse[JobResponse],
)
async def infer_target(
    case_id: str,
    target_id: str,
    body: InferenceRequest,
    current_user: User = Depends(require_feature("PROFILER")),
):
    """Enqueue inference job."""
    _require_profiler_enabled()
    case = await ProfilerCase.get(case_id)
    if not case:
        raise NotFoundException("Case", case_id)
    target = await ProfilerTarget.get(target_id)
    if not target or str(target.case_id) != str(case_id):
        raise NotFoundException("Target", target_id)
    if not await check_profiler_clearance(current_user, case.org_id):
        from app.core.exceptions import AuthorizationException

        raise AuthorizationException("Access denied")
    # Override context from path/auth
    payload = body.model_dump()
    payload["context"] = {
        **payload.get("context", {}),
        "org_id": str(case.org_id),
        "case_id": str(case.id),
        "target_id": str(target.id),
    }
    job_svc = JobService()
    job = await job_svc.enqueue_inference(
        case_id=case_id,
        target_id=target_id,
        org_id=str(case.org_id),
        created_by=str(current_user.id),
        payload=payload,
    )
    return SuccessResponse(
        message="Inference job enqueued",
        data=JobResponse(
            id=str(job.id),
            case_id=str(job.case_id),
            target_id=str(job.target_id),
            org_id=str(job.org_id),
            created_by=str(job.created_by),
            job_type=job.job_type,
            status=job.status,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error=job.error,
            metrics=job.metrics or {},
        ),
    )
