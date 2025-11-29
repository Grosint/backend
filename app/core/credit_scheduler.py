"""Credit expiration scheduler using APScheduler."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.database import db
from app.services.credit_service import CreditService

logger = logging.getLogger(__name__)


class CreditScheduler:
    """Scheduler for credit expiration tasks."""

    def __init__(self):
        self.scheduler: AsyncIOScheduler | None = None
        self.credit_service: CreditService | None = None

    def start(self):
        """Start the scheduler."""
        if not settings.CREDIT_EXPIRY_SCHEDULER_ENABLED:
            logger.info("Credit expiry scheduler is disabled")
            return

        try:
            self.scheduler = AsyncIOScheduler()
            self.credit_service = CreditService(db.database)

            # Add credit expiration job
            self.scheduler.add_job(
                func=self.expire_credits_task,
                trigger=CronTrigger(
                    hour=settings.CREDIT_EXPIRY_SCHEDULE_HOUR,
                    minute=settings.CREDIT_EXPIRY_SCHEDULE_MINUTE,
                    timezone="UTC",
                ),
                id="expire_credits_daily",
                name="Expire credits daily",
                replace_existing=True,
            )

            self.scheduler.start()
            logger.info(
                "Credit expiry scheduler started",
                extra={
                    "schedule_hour": settings.CREDIT_EXPIRY_SCHEDULE_HOUR,
                    "schedule_minute": settings.CREDIT_EXPIRY_SCHEDULE_MINUTE,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to start credit expiry scheduler",
                extra={"error": str(e)},
                exc_info=True,
            )

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler:
            try:
                self.scheduler.shutdown()
                logger.info("Credit expiry scheduler shut down")
            except Exception as e:
                logger.error(
                    "Error shutting down credit expiry scheduler",
                    extra={"error": str(e)},
                    exc_info=True,
                )

    async def expire_credits_task(self):
        """
        Task to expire credits that have passed their expiry date.
        Updates credit status and creates transaction records for expired credits.
        """
        try:
            logger.info("Starting credit expiration task")

            if not self.credit_service:
                self.credit_service = CreditService(db.database)

            result = await self.credit_service.expire_credits()

            if result.get("success"):
                logger.info(
                    "Credit expiration task completed",
                    extra={
                        "expired_count": result.get("expired_count", 0),
                        "total_expired_amount": result.get("total_expired_amount", 0),
                    },
                )
            else:
                logger.error(
                    "Credit expiration task failed",
                    extra={"error": result.get("error")},
                )

        except Exception as e:
            logger.error(
                "Error in credit expiration task",
                extra={"error": str(e)},
                exc_info=True,
            )


# Global scheduler instance
credit_scheduler = CreditScheduler()
