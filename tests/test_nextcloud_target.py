"""Tests for Nextcloud WebDAV target (upload)."""

from pathlib import Path

import httpx
import respx

from sync_to_local.config import UploadConfig
from sync_to_local.targets.nextcloud import NextcloudTarget


class TestNextcloudTarget:
    def _make_config(self, **kwargs: object) -> UploadConfig:
        defaults: dict[str, object] = {
            "source_dir": Path("/tmp/src"),
            "target_url": "https://share.example.com/s/TOKEN123",
            "target_subdir": "/subdir",
        }
        defaults.update(kwargs)
        return UploadConfig(**defaults)  # type: ignore[arg-type]

    @respx.mock
    def test_upload_file(self, tmp_dir: Path) -> None:
        config = self._make_config(source_dir=tmp_dir)
        target = NextcloudTarget(config)

        # Create a local file
        local_file = tmp_dir / "test.txt"
        local_file.write_text("hello world")

        # Mock MKCOL for parent dir (ensure_directory)
        respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/subdir",
        ).mock(return_value=httpx.Response(201))

        # Mock PUT
        respx.put(
            "https://share.example.com/public.php/dav/files/TOKEN123/subdir/test.txt"
        ).mock(return_value=httpx.Response(201))

        target.upload_file(local_file, "/subdir/test.txt")

    @respx.mock
    def test_ensure_directory_recursive(self) -> None:
        config = self._make_config()
        target = NextcloudTarget(config)

        respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/a",
        ).mock(return_value=httpx.Response(201))

        respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/a/b",
        ).mock(return_value=httpx.Response(201))

        respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/a/b/c",
        ).mock(return_value=httpx.Response(201))

        target.ensure_directory("/a/b/c")

    @respx.mock
    def test_ensure_directory_already_exists(self) -> None:
        config = self._make_config()
        target = NextcloudTarget(config)

        # 405 = already exists
        respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/existing",
        ).mock(return_value=httpx.Response(405))

        target.ensure_directory("/existing")

    @respx.mock
    def test_ensure_directory_caches(self) -> None:
        config = self._make_config()
        target = NextcloudTarget(config)

        route = respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/cached",
        ).mock(return_value=httpx.Response(201))

        target.ensure_directory("/cached")
        target.ensure_directory("/cached")

        # Should only call MKCOL once
        assert route.call_count == 1

    @respx.mock
    def test_upload_creates_parent_dirs(self, tmp_dir: Path) -> None:
        config = self._make_config(source_dir=tmp_dir)
        target = NextcloudTarget(config)

        local_file = tmp_dir / "test.txt"
        local_file.write_text("data")

        respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/deep",
        ).mock(return_value=httpx.Response(201))

        respx.request(
            "MKCOL",
            "https://share.example.com/public.php/dav/files/TOKEN123/deep/nested",
        ).mock(return_value=httpx.Response(201))

        respx.put(
            "https://share.example.com/public.php/dav/files/TOKEN123/deep/nested/test.txt"
        ).mock(return_value=httpx.Response(201))

        target.upload_file(local_file, "/deep/nested/test.txt")

    def test_token_extracted(self) -> None:
        config = self._make_config()
        target = NextcloudTarget(config)
        assert target._token == "TOKEN123"
        assert target._dav_base == "https://share.example.com/public.php/dav/files/TOKEN123"
