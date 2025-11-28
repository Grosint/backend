"""Plan management API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.core.exceptions import NotFoundException
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate
from app.schemas.response import SuccessResponse
from app.services.plan_service import PlanService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=SuccessResponse[list[PlanResponse]])
async def list_plans(
    active_only: bool = Query(True, description="Show only active plans"),
    db=Depends(get_database),
):
    """List all available plans."""
    try:
        plan_service = PlanService(db)
        plans = await plan_service.list_plans(active_only=active_only)

        plan_responses = [
            PlanResponse(
                id=str(plan.id),
                name=plan.name,
                cashfreePlanId=plan.cashfreePlanId,
                price=plan.price,
                credits=plan.credits,
                durationInDays=plan.durationInDays,
                isPrepaid=plan.isPrepaid,
                isActive=plan.isActive,
                discount=plan.discount,
                createdAt=plan.createdAt,
                updatedAt=plan.updatedAt,
            )
            for plan in plans
        ]

        logger.info(
            "Plans listed",
            extra={"count": len(plan_responses), "active_only": active_only},
        )

        return SuccessResponse(
            message="Plans retrieved successfully",
            data=plan_responses,
        )

    except Exception as e:
        logger.error("Error listing plans", extra={"error": str(e)}, exc_info=True)
        raise


@router.get("/{plan_id}", response_model=SuccessResponse[PlanResponse])
async def get_plan(plan_id: str, db=Depends(get_database)):
    """Get plan details by ID."""
    try:
        plan_service = PlanService(db)
        plan = await plan_service.get_plan_by_id(plan_id)

        if not plan:
            raise NotFoundException(resource="Plan", resource_id=plan_id)

        plan_response = PlanResponse(
            id=str(plan.id),
            name=plan.name,
            cashfreePlanId=plan.cashfreePlanId,
            price=plan.price,
            credits=plan.credits,
            durationInDays=plan.durationInDays,
            isPrepaid=plan.isPrepaid,
            isActive=plan.isActive,
            discount=plan.discount,
            createdAt=plan.createdAt,
            updatedAt=plan.updatedAt,
        )

        logger.info("Plan retrieved", extra={"plan_id": plan_id})

        return SuccessResponse(
            message="Plan retrieved successfully",
            data=plan_response,
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(
            "Error getting plan",
            extra={"plan_id": plan_id, "error": str(e)},
            exc_info=True,
        )
        raise


@router.post("/", response_model=SuccessResponse[PlanResponse])
async def create_plan(
    plan_data: PlanCreate,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Create a new plan (admin only - add admin check if needed)."""
    try:
        plan_service = PlanService(db)
        plan = await plan_service.create_plan(plan_data)

        plan_response = PlanResponse(
            id=str(plan.id),
            name=plan.name,
            cashfreePlanId=plan.cashfreePlanId,
            price=plan.price,
            credits=plan.credits,
            durationInDays=plan.durationInDays,
            isPrepaid=plan.isPrepaid,
            isActive=plan.isActive,
            discount=plan.discount,
            createdAt=plan.createdAt,
            updatedAt=plan.updatedAt,
        )

        logger.info(
            "Plan created",
            extra={
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "user_id": current_user.user_id,
            },
        )

        return SuccessResponse(
            message="Plan created successfully",
            data=plan_response,
        )

    except Exception as e:
        logger.error(
            "Error creating plan",
            extra={"plan_name": plan_data.name, "error": str(e)},
            exc_info=True,
        )
        raise


@router.put("/{plan_id}", response_model=SuccessResponse[PlanResponse])
async def update_plan(
    plan_id: str,
    plan_update: PlanUpdate,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Update a plan (admin only - add admin check if needed)."""
    try:
        plan_service = PlanService(db)
        plan = await plan_service.update_plan(plan_id, plan_update)

        plan_response = PlanResponse(
            id=str(plan.id),
            name=plan.name,
            cashfreePlanId=plan.cashfreePlanId,
            price=plan.price,
            credits=plan.credits,
            durationInDays=plan.durationInDays,
            isPrepaid=plan.isPrepaid,
            isActive=plan.isActive,
            discount=plan.discount,
            createdAt=plan.createdAt,
            updatedAt=plan.updatedAt,
        )

        logger.info(
            "Plan updated",
            extra={"plan_id": plan_id, "user_id": current_user.user_id},
        )

        return SuccessResponse(
            message="Plan updated successfully",
            data=plan_response,
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(
            "Error updating plan",
            extra={"plan_id": plan_id, "error": str(e)},
            exc_info=True,
        )
        raise
