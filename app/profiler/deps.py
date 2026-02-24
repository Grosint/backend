"""Profiler dependencies - auth, org resolution, clearance."""

from __future__ import annotations

import logging

from bson import ObjectId

from app.core.exceptions import AuthorizationException
from app.models.organization import Organization
from app.models.user import User, UserType

logger = logging.getLogger(__name__)

# Use require_feature("PROFILER") for profiler endpoints - gates on PROFILER feature


async def resolve_org_id(
    user: User, requested_org_id: str | ObjectId | None
) -> ObjectId:
    """
    Resolve org_id for profiler operations.
    Users without an organization use user.id as personal scope.
    - admin: use requested_org_id or user.id (personal)
    - org_admin: use org.id or user.id if no org (personal fallback)
    - user with org: use user.organizationId
    - user without org: use user.id (personal scope)
    """
    if user.userType == UserType.ADMIN:
        if requested_org_id is not None:
            return ObjectId(str(requested_org_id))
        return user.id
    if user.userType == UserType.ORG_ADMIN:
        org = await Organization.find_one(Organization.orgAdminId == user.id)
        if org:
            if requested_org_id is not None and str(org.id) != str(requested_org_id):
                raise AuthorizationException("org_id does not match your organization")
            return org.id
        return user.id
    if user.organizationId:
        if requested_org_id is not None and str(user.organizationId) != str(
            requested_org_id
        ):
            raise AuthorizationException("org_id does not match your organization")
        return user.organizationId
    return user.id


async def check_profiler_clearance(user: User, case_org_id: ObjectId) -> bool:
    """
    Verify user has access to case's org.
    Users without organization can access cases where org_id == user.id.
    """
    if user.userType == UserType.ADMIN:
        return True
    if user.userType == UserType.ORG_ADMIN:
        org = await Organization.find_one(Organization.orgAdminId == user.id)
        if org and case_org_id == org.id:
            return True
        return case_org_id == user.id
    if user.organizationId and case_org_id == user.organizationId:
        return True
    return case_org_id == user.id
