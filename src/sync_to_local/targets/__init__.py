"""Target factory for sync-to-remote."""

from __future__ import annotations

from collections.abc import Callable

from sync_to_local.config import UploadConfig
from sync_to_local.targets.base import TargetBase
from sync_to_local.targets.nextcloud import NextcloudTarget

_TARGET_MAP: dict[str, Callable[[UploadConfig], TargetBase]] = {
    "nextcloud": NextcloudTarget,
}


def create_target(config: UploadConfig) -> TargetBase:
    """Create a target instance based on config.target_type."""
    target_cls = _TARGET_MAP.get(config.target_type)
    if target_cls is None:
        raise ValueError(f"Unknown target type: {config.target_type!r}")
    return target_cls(config)
