"""Source factory for sync-to-local."""

from __future__ import annotations

from collections.abc import Callable

from sync_to_local.config import SyncConfig
from sync_to_local.sources.base import SourceBase
from sync_to_local.sources.nextcloud import NextcloudSource

_SOURCE_MAP: dict[str, Callable[[SyncConfig], SourceBase]] = {
    "nextcloud": NextcloudSource,
}


def create_source(config: SyncConfig) -> SourceBase:
    """Create a source instance based on config.source_type."""
    source_cls = _SOURCE_MAP.get(config.source_type)
    if source_cls is None:
        raise ValueError(f"Unknown source type: {config.source_type!r}")
    return source_cls(config)
