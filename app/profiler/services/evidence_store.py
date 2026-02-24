"""Azure Blob Storage evidence store."""

from __future__ import annotations

import contextlib
import json
import logging

from azure.core.credentials import AzureNamedKeyCredential
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from app.core.config import settings
from app.profiler.utils.now import format_timestamp_iso, utc_now

logger = logging.getLogger(__name__)

# Path template: profiler/{org_id}/{case_id}/{target_id}/{job_id}/{timestamp}_{sha256}.html
PATH_TEMPLATE = (
    "profiler/{org_id}/{case_id}/{target_id}/{job_id}/{timestamp}_{sha256}.html"
)


class AzureBlobEvidenceStore:
    """Azure Blob Storage for profiler evidence (raw HTML, bytes)."""

    def __init__(
        self,
        *,
        connection_string: str | None = None,
        container_name: str | None = None,
    ) -> None:
        self._conn_str = connection_string or settings.AZURE_BLOB_CONNECTION_STRING
        self._container_name = container_name or settings.AZURE_BLOB_CONTAINER_EVIDENCE
        self._client: BlobServiceClient | None = None

    def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            if self._conn_str:
                self._client = BlobServiceClient.from_connection_string(self._conn_str)
            elif (
                settings.AZURE_STORAGE_ACCOUNT_NAME
                and settings.AZURE_STORAGE_ACCOUNT_KEY
            ):
                account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
                credential = AzureNamedKeyCredential(
                    settings.AZURE_STORAGE_ACCOUNT_NAME,
                    settings.AZURE_STORAGE_ACCOUNT_KEY,
                )
                self._client = BlobServiceClient(
                    account_url=account_url,
                    credential=credential,
                )
            else:
                raise ValueError(
                    "Azure Blob credentials required. Set either "
                    "AZURE_BLOB_CONNECTION_STRING or (AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY)."
                )
        return self._client

    def _build_path(
        self,
        org_id: str,
        case_id: str,
        target_id: str,
        job_id: str,
        sha256: str,
        timestamp: str | None = None,
        ext: str = "html",
    ) -> str:
        ts = timestamp or format_timestamp_iso(utc_now())
        return PATH_TEMPLATE.format(
            org_id=org_id,
            case_id=case_id,
            target_id=target_id,
            job_id=job_id,
            timestamp=ts,
            sha256=sha256,
        ).replace(".html", f".{ext}")

    async def _ensure_container_exists(self) -> None:
        """Create container if it does not exist. Uses create_container (no exist_ok)
        to avoid aiohttp transport bug."""
        client = self._get_client()
        with contextlib.suppress(ResourceExistsError):
            await client.create_container(self._container_name)

    async def put_bytes(
        self,
        path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw bytes to blob. Returns blob path.
        Creates container if it does not exist.
        """
        client = self._get_client()
        container = client.get_container_client(self._container_name)
        blob = container.get_blob_client(path)

        try:
            await blob.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
            return path
        except ResourceNotFoundError:
            await self._ensure_container_exists()
            await blob.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
            return path
        except Exception as e:
            logger.error(
                "Evidence store put_bytes failed",
                extra={"path": path[:80], "error": str(e)},
                exc_info=True,
            )
            raise

    async def put_text(self, path: str, text: str) -> str:
        """Upload text (HTML) to blob. Returns blob path."""
        data = text.encode("utf-8")
        return await self.put_bytes(path, data, content_type="text/html; charset=utf-8")

    async def get_bytes(self, path: str) -> bytes:
        """Download raw bytes from blob."""
        try:
            client = self._get_client()
            container = client.get_container_client(self._container_name)
            blob = container.get_blob_client(path)
            stream = await blob.download_blob()
            return await stream.readall()
        except Exception as e:
            logger.error(
                "Evidence store get_bytes failed",
                extra={"path": path[:80], "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_text(self, path: str) -> str:
        """Download text (HTML) from blob."""
        data = await self.get_bytes(path)
        return data.decode("utf-8")

    async def put_evidence(
        self,
        org_id: str,
        case_id: str,
        target_id: str,
        job_id: str,
        sha256: str,
        html: str | bytes,
    ) -> str:
        """
        Store evidence with deterministic path.
        Returns blob_path for ProfilerSourceDocument.
        """
        data = html.encode("utf-8") if isinstance(html, str) else html
        path = self._build_path(
            str(org_id), str(case_id), str(target_id), str(job_id), sha256
        )
        await self.put_bytes(path, data, content_type="text/html; charset=utf-8")
        return path

    async def put_json_evidence(
        self,
        org_id: str,
        case_id: str,
        target_id: str,
        job_id: str,
        sha256: str,
        data: dict | str,
    ) -> str:
        """
        Store extracted JSON evidence. Single source of truth for scraped profiles.
        Returns blob_path for ProfilerSourceDocument.
        """
        if isinstance(data, dict):
            payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        else:
            payload = data
        raw = payload.encode("utf-8")
        path = self._build_path(
            str(org_id), str(case_id), str(target_id), str(job_id), sha256, ext="json"
        )
        await self.put_bytes(path, raw, content_type="application/json; charset=utf-8")
        return path

    async def get_json(self, path: str) -> dict:
        """Download and parse JSON from blob."""
        data = await self.get_bytes(path)
        return json.loads(data.decode("utf-8"))
