"""Shared WebDAV utilities for Nextcloud sources and targets."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def parse_share_url(source_url: str) -> tuple[str, str]:
    """Extract base URL and share token from a Nextcloud public share URL.

    Example: https://share.example.com/s/PcLf3SWw2sWLBzk
    Returns: ("https://share.example.com", "PcLf3SWw2sWLBzk")
    """
    parsed = urlparse(source_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    # Token is the last path segment after /s/
    match = re.search(r"/s/([^/?]+)", parsed.path)
    if not match:
        raise ValueError(f"Cannot extract share token from URL: {source_url}")
    token = match.group(1)
    return base_url, token
