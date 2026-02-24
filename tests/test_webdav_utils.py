"""Tests for shared WebDAV utilities."""

import pytest

from sync_to_local.webdav_utils import parse_share_url


class TestParseShareUrl:
    def test_standard_url(self) -> None:
        base, token = parse_share_url("https://share.example.com/s/PcLf3SWw2sWLBzk")
        assert base == "https://share.example.com"
        assert token == "PcLf3SWw2sWLBzk"

    def test_url_with_trailing_slash(self) -> None:
        base, token = parse_share_url("https://share.example.com/s/ABC123/")
        assert base == "https://share.example.com"
        assert token == "ABC123"

    def test_url_with_query_params(self) -> None:
        base, token = parse_share_url(
            "https://share.example.com/s/XYZ789?dir=/_folder"
        )
        assert base == "https://share.example.com"
        assert token == "XYZ789"

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract share token"):
            parse_share_url("https://example.com/no-token-here")

    def test_http_url(self) -> None:
        base, token = parse_share_url("http://localhost/s/TOKEN1")
        assert base == "http://localhost"
        assert token == "TOKEN1"
