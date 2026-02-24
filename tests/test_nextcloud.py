"""Tests for Nextcloud WebDAV source."""

from pathlib import Path

import httpx
import pytest
import respx

from sync_to_local.config import SyncConfig
from sync_to_local.sources.nextcloud import NextcloudSource, _parse_share_url

PROPFIND_RESPONSE_ROOT = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>/public.php/dav/files/TOKEN123/subdir/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/dav/files/TOKEN123/subdir/file1.txt</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype/>
        <d:getcontentlength>100</d:getcontentlength>
        <d:getetag>"etag1"</d:getetag>
        <d:getlastmodified>Mon, 01 Jan 2024 00:00:00 GMT</d:getlastmodified>
      </d:prop>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/dav/files/TOKEN123/subdir/child/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>"""

PROPFIND_RESPONSE_CHILD = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>/public.php/dav/files/TOKEN123/subdir/child/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/dav/files/TOKEN123/subdir/child/file2.txt</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype/>
        <d:getcontentlength>200</d:getcontentlength>
        <d:getetag>"etag2"</d:getetag>
        <d:getlastmodified>Tue, 02 Jan 2024 00:00:00 GMT</d:getlastmodified>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>"""


class TestParseShareUrl:
    def test_standard_url(self) -> None:
        base, token = _parse_share_url("https://share.example.com/s/PcLf3SWw2sWLBzk")
        assert base == "https://share.example.com"
        assert token == "PcLf3SWw2sWLBzk"

    def test_url_with_trailing_slash(self) -> None:
        base, token = _parse_share_url("https://share.example.com/s/ABC123/")
        assert token == "ABC123"

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract share token"):
            _parse_share_url("https://example.com/no-token-here")


class TestNextcloudSource:
    def _make_config(self, tmp_dir: Path, **kwargs: object) -> SyncConfig:
        defaults = {
            "source_url": "https://share.example.com/s/TOKEN123",
            "target_dir": tmp_dir / "output",
            "source_subdir": "/subdir",
        }
        defaults.update(kwargs)  # type: ignore[arg-type]
        return SyncConfig(**defaults)  # type: ignore[arg-type]

    @respx.mock
    def test_list_files_recursive(self, tmp_dir: Path) -> None:
        config = self._make_config(tmp_dir)
        source = NextcloudSource(config)

        # Mock PROPFIND for root subdir
        respx.request(
            "PROPFIND",
            "https://share.example.com/public.php/dav/files/TOKEN123/subdir",
        ).mock(
            return_value=httpx.Response(207, text=PROPFIND_RESPONSE_ROOT)
        )

        # Mock PROPFIND for child subdir
        respx.request(
            "PROPFIND",
            "https://share.example.com/public.php/dav/files/TOKEN123/subdir/child/",
        ).mock(
            return_value=httpx.Response(207, text=PROPFIND_RESPONSE_CHILD)
        )

        files = source.list_files()

        assert len(files) == 2
        paths = {f.path for f in files}
        assert "/subdir/file1.txt" in paths
        assert "/subdir/child/file2.txt" in paths

        file1 = next(f for f in files if f.path == "/subdir/file1.txt")
        assert file1.etag == '"etag1"'
        assert file1.size == 100

        file2 = next(f for f in files if f.path == "/subdir/child/file2.txt")
        assert file2.etag == '"etag2"'
        assert file2.size == 200

    @respx.mock
    def test_download_file(self, tmp_dir: Path) -> None:
        config = self._make_config(tmp_dir)
        source = NextcloudSource(config)

        from sync_to_local.sources.base import RemoteFile

        remote = RemoteFile(
            path="/subdir/file1.txt",
            size=13,
            etag='"etag1"',
            last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
        )

        respx.get(
            "https://share.example.com/public.php/dav/files/TOKEN123/subdir/file1.txt"
        ).mock(
            return_value=httpx.Response(200, content=b"Hello, world!")
        )

        local_path = tmp_dir / "output" / "subdir" / "file1.txt"
        source.download_file(remote, local_path)

        assert local_path.exists()
        assert local_path.read_bytes() == b"Hello, world!"

    @respx.mock
    def test_download_creates_parent_dirs(self, tmp_dir: Path) -> None:
        config = self._make_config(tmp_dir)
        source = NextcloudSource(config)

        from sync_to_local.sources.base import RemoteFile

        remote = RemoteFile(
            path="/subdir/deep/nested/file.txt",
            size=5,
            etag='"e"',
            last_modified="",
        )

        respx.get(
            "https://share.example.com/public.php/dav/files/TOKEN123/subdir/deep/nested/file.txt"
        ).mock(
            return_value=httpx.Response(200, content=b"data!")
        )

        local_path = tmp_dir / "output" / "subdir" / "deep" / "nested" / "file.txt"
        source.download_file(remote, local_path)

        assert local_path.exists()
        assert local_path.read_bytes() == b"data!"

    def test_token_extracted(self, tmp_dir: Path) -> None:
        config = self._make_config(tmp_dir)
        source = NextcloudSource(config)
        assert source._token == "TOKEN123"
        assert source._dav_base == "https://share.example.com/public.php/dav/files/TOKEN123"

    def test_password_stored(self, tmp_dir: Path) -> None:
        config = self._make_config(tmp_dir, password="secret")
        source = NextcloudSource(config)
        assert source._config.password == "secret"
