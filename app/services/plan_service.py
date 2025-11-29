from __future__ import annotations

import logging
from datetime import UTC, datetime

from bson import ObjectId

from app.core.exceptions import NotFoundException
from app.models.plan import Plan
from app.schemas.plan import PlanCreate, PlanUpdate
from app.services.integrations.payment.cashfree_service import CashfreeService

logger = logging.getLogger(__name__)


class PlanService:
    """Service for plan management."""

    def __init__(self, db):
        self.db = db
        self.cashfree_service = CashfreeService()

    async def create_plan(self, plan_data: PlanCreate) -> Plan:
        """Create a new plan and sync with Cashfree."""
        try:
            logger.info("Creating plan", extra={"plan_name": plan_data.name})

            # Create plan in database
            plan = Plan(
                name=plan_data.name,
                price=plan_data.price,
                credits=plan_data.credits,
                durationInDays=plan_data.durationInDays,
                isPrepaid=plan_data.isPrepaid,
                isActive=plan_data.isActive,
                discount=plan_data.discount,
            )
            await plan.insert()

            # Create Cashfree plan if not prepaid (subscription plans need Cashfree plan)
            if not plan_data.isPrepaid:
                try:
                    cashfree_plan_id = f"plan_{plan.name.lower().replace(' ', '_')}"
                    cashfree_response = (
                        await self.cashfree_service.create_cashfree_plan(
                            plan_id=cashfree_plan_id,
                            plan_name=plan.name,
                            plan_type="PERIODIC",
                            plan_amount=plan.price / 100.0,  # Convert paise to rupees
                            plan_note=f"{plan.name} plan with {plan.credits} credits",
                        )
                    )

                    if "plan_id" in cashfree_response:
                        plan.cashfreePlanId = cashfree_response["plan_id"]
                        await plan.save()

                        logger.info(
                            "Cashfree plan created and synced",
                            extra={
                                "plan_id": str(plan.id),
                                "cf_plan_id": plan.cashfreePlanId,
                            },
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to create Cashfree plan, continuing without it",
                        extra={"plan_id": str(plan.id), "error": str(e)},
                    )

            logger.info(
                "Plan created", extra={"plan_id": str(plan.id), "plan_name": plan.name}
            )
            return plan

        except Exception as e:
            logger.error(
                "Error creating plan",
                extra={"plan_name": plan_data.name, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_plan_by_id(self, plan_id: str) -> Plan | None:
        """Get plan by ID."""
        try:
            plan = await Plan.find_one(Plan.id == ObjectId(plan_id))
            return plan
        except Exception as e:
            logger.error(
                "Error getting plan by ID",
                extra={"plan_id": plan_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def update_plan(self, plan_id: str, plan_update: PlanUpdate) -> Plan:
        """Update a plan."""
        try:
            plan = await Plan.find_one(Plan.id == ObjectId(plan_id))
            if not plan:
                raise NotFoundException(resource="Plan", resource_id=plan_id)

            update_data = plan_update.model_dump(exclude_unset=True)
            if not update_data:
                return plan

            # Update plan fields
            for field, value in update_data.items():
                if hasattr(plan, field):
                    setattr(plan, field, value)

            plan.updatedAt = datetime.now(UTC)
            await plan.save()

            logger.info("Plan updated", extra={"plan_id": plan_id})
            return plan

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                "Error updating plan",
                extra={"plan_id": plan_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def list_plans(self, active_only: bool = True) -> list[Plan]:
        """List all plans."""
        try:
            if active_only:
                plans = await Plan.find(Plan.isActive).to_list()
            else:
                plans = await Plan.find().to_list()

            logger.info(
                "Plans listed",
                extra={"count": len(plans), "active_only": active_only},
            )
            return plans

        except Exception as e:
            logger.error("Error listing plans", extra={"error": str(e)}, exc_info=True)
            raise
