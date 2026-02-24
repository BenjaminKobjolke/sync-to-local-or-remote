"""Nextcloud WebDAV source implementation."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from sync_to_local.config import SyncConfig
from sync_to_local.sources.base import RemoteFile, SourceBase
from sync_to_local.webdav_utils import parse_share_url

logger = logging.getLogger(__name__)

DAV_NS = "DAV:"
OC_NS = "http://owncloud.org/ns"


class NextcloudSource(SourceBase):
    """Nextcloud public share source using WebDAV."""

    def __init__(self, config: SyncConfig) -> None:
        self._config = config
        self._base_url, self._token = parse_share_url(config.source_url)
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

    def list_files(self) -> list[RemoteFile]:
        """List all files recursively from the Nextcloud share."""
        subdir = self._config.source_subdir
        return self._list_recursive(subdir)

    def _list_recursive(self, path: str) -> list[RemoteFile]:
        """Recursively list files using PROPFIND with Depth: 1."""
        url = self._dav_base + path
        logger.debug("PROPFIND %s", url)

        response = self._propfind(url)
        root = ET.fromstring(response.text)

        files: list[RemoteFile] = []
        subdirs: list[str] = []

        for resp_elem in root.findall(f"{{{DAV_NS}}}response"):
            href_elem = resp_elem.find(f"{{{DAV_NS}}}href")
            if href_elem is None or href_elem.text is None:
                continue

            href = href_elem.text
            props = resp_elem.find(f"{{{DAV_NS}}}propstat/{{{DAV_NS}}}prop")
            if props is None:
                continue

            # Check if it's a collection (directory)
            resourcetype = props.find(f"{{{DAV_NS}}}resourcetype")
            is_dir = (
                resourcetype is not None
                and resourcetype.find(f"{{{DAV_NS}}}collection") is not None
            )

            # Extract the relative path from the href
            relative_path = self._href_to_relative(href)

            if is_dir:
                # Skip the directory itself (same as current path)
                if relative_path.rstrip("/") != path.rstrip("/"):
                    subdirs.append(relative_path)
            else:
                etag_elem = props.find(f"{{{DAV_NS}}}getetag")
                size_elem = props.find(f"{{{DAV_NS}}}getcontentlength")
                lastmod_elem = props.find(f"{{{DAV_NS}}}getlastmodified")

                etag = etag_elem.text if etag_elem is not None and etag_elem.text else ""
                size = int(size_elem.text) if size_elem is not None and size_elem.text else 0
                lastmod = (
                    lastmod_elem.text
                    if lastmod_elem is not None and lastmod_elem.text
                    else ""
                )

                files.append(
                    RemoteFile(
                        path=relative_path,
                        size=size,
                        etag=etag,
                        last_modified=lastmod,
                    )
                )

        # Recurse into subdirectories
        for subdir in subdirs:
            files.extend(self._list_recursive(subdir))

        return files

    def _href_to_relative(self, href: str) -> str:
        """Convert a WebDAV href to a path relative to the share root."""
        # Href typically looks like /public.php/dav/files/TOKEN/subdir/file.txt
        prefix = f"/public.php/dav/files/{self._token}"
        if href.startswith(prefix):
            return href[len(prefix):]
        return href

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _propfind(self, url: str) -> httpx.Response:
        """Execute a PROPFIND request with retry."""
        propfind_body = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:prop>
    <d:resourcetype/>
    <d:getcontentlength/>
    <d:getetag/>
    <d:getlastmodified/>
  </d:prop>
</d:propfind>"""

        response = self._client.request(
            "PROPFIND",
            url,
            content=propfind_body,
            headers={
                "Depth": "1",
                "Content-Type": "application/xml; charset=utf-8",
            },
        )
        response.raise_for_status()
        return response

    def download_file(self, remote_file: RemoteFile, local_path: Path) -> None:
        """Download a file from the Nextcloud share."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        url = self._dav_base + remote_file.path
        logger.info("Downloading %s -> %s", remote_file.path, local_path)
        self._download(url, local_path)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _download(self, url: str, local_path: Path) -> None:
        """Streaming download with retry."""
        with self._client.stream("GET", url) as response:
            response.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
