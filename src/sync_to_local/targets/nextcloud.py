"""Nextcloud WebDAV target implementation for uploading files."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from sync_to_local.config import UploadConfig
from sync_to_local.targets.base import TargetBase
from sync_to_local.webdav_utils import parse_share_url

logger = logging.getLogger(__name__)


class NextcloudTarget(TargetBase):
    """Nextcloud public share target using WebDAV PUT/MKCOL."""

    def __init__(self, config: UploadConfig) -> None:
        self._config = config
        self._base_url, self._token = parse_share_url(config.target_url)
        self._dav_base = f"{self._base_url}/public.php/dav/files/{self._token}"
        self._auth = httpx.BasicAuth(
            username=self._token,
            password=config.password,
        )
        self._client = httpx.Client(
            auth=self._auth,
            timeout=config.timeout,
            follow_redirects=True,
        )
        self._created_dirs: set[str] = set()

    def ensure_directory(self, remote_path: str) -> None:
        """Create a remote directory via WebDAV MKCOL (recursive)."""
        # Normalize: ensure leading slash, no trailing slash
        remote_path = remote_path.rstrip("/")
        if not remote_path:
            return

        if remote_path in self._created_dirs:
            return

        # Ensure parent exists first
        parent = remote_path.rsplit("/", 1)[0] if "/" in remote_path else ""
        if parent:
            self.ensure_directory(parent)

        url = self._dav_base + remote_path
        logger.debug("MKCOL %s", url)
        self._mkcol(url)
        self._created_dirs.add(remote_path)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _mkcol(self, url: str) -> None:
        """Execute a MKCOL request with retry. Ignores 405 (already exists)."""
        response = self._client.request("MKCOL", url)
        # 201 = created, 405 = already exists — both are fine
        if response.status_code not in (201, 405):
            response.raise_for_status()

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file to the Nextcloud share via WebDAV PUT."""
        # Ensure parent directory exists
        parent_dir = remote_path.rsplit("/", 1)[0] if "/" in remote_path else ""
        if parent_dir:
            self.ensure_directory(parent_dir)

        url = self._dav_base + remote_path
        logger.info("Uploading %s -> %s", local_path, remote_path)
        self._upload(url, local_path)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _upload(self, url: str, local_path: Path) -> None:
        """Streaming upload with retry."""
        with open(local_path, "rb") as f:
            response = self._client.put(url, content=f)
            response.raise_for_status()
