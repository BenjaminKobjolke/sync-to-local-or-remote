"""Configuration loading and merging for sync-to-local."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sync_to_local.constants import (
    DEFAULT_LOG_LEVEL,
    DEFAULT_RETRIES,
    DEFAULT_SOURCE_TYPE,
    DEFAULT_TIMEOUT,
)


@dataclass(frozen=True)
class PipelineConfig:
    """A single post-download pipeline: regex pattern + ordered commands."""

    pattern: str
    commands: list[str]
    delete_original: bool = False


@dataclass(frozen=True)
class SyncConfig:
    """All configuration for a sync run."""

    source_url: str
    target_dir: Path
    source_type: str = DEFAULT_SOURCE_TYPE
    source_subdir: str = ""
    password: str = ""
    retries: int = DEFAULT_RETRIES
    timeout: int = DEFAULT_TIMEOUT
    log_level: str = DEFAULT_LOG_LEVEL
    pipelines: list[PipelineConfig] = field(default_factory=list)
    post_sync: list[str] = field(default_factory=list)
    index_only: bool = False
    manifest_path: Path | None = None


def load_config(config_path: Path) -> SyncConfig:
    """Load a SyncConfig from a JSON file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data: dict[str, Any] = json.load(f)

    return _dict_to_config(data)


def merge_cli_args(
    base: SyncConfig | None,
    cli_overrides: dict[str, Any],
) -> SyncConfig:
    """Merge CLI arguments on top of a base config (from JSON or defaults).

    CLI values that are None are treated as "not provided" and skipped.
    The ``?dir=`` query parameter in source_url is extracted as source_subdir
    unless an explicit source_subdir is provided.
    """
    # Start from base config or build from CLI
    merged: dict[str, Any] = _config_to_dict(base) if base is not None else {}

    # Apply non-None CLI overrides
    for key, value in cli_overrides.items():
        if value is not None:
            merged[key] = value

    # Extract ?dir= from source_url if present
    source_url = merged.get("source_url")
    if not source_url:
        raise ValueError("source_url is required")

    parsed = urlparse(source_url)
    dir_params = parse_qs(parsed.query).get("dir", [])

    if dir_params:
        # Strip query params from the URL
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        merged["source_url"] = clean_url

        # Only use extracted subdir if no explicit one was provided
        explicit_subdir = cli_overrides.get("source_subdir")
        if not explicit_subdir and not merged.get("source_subdir"):
            merged["source_subdir"] = dir_params[0]

    if not merged.get("target_dir"):
        raise ValueError("target_dir is required")

    return _dict_to_config(merged)


def _dict_to_config(data: dict[str, Any]) -> SyncConfig:
    """Convert a raw dict to a SyncConfig."""
    pipelines_raw = data.get("pipelines", [])
    pipelines = [
        PipelineConfig(
            pattern=p["pattern"],
            commands=p["commands"],
            delete_original=p.get("delete_original", False),
        )
        for p in pipelines_raw
    ]

    target_dir = data.get("target_dir", "")
    manifest_path = data.get("manifest_path")

    return SyncConfig(
        source_url=data["source_url"],
        target_dir=Path(target_dir) if isinstance(target_dir, str) else target_dir,
        source_type=data.get("source_type", DEFAULT_SOURCE_TYPE),
        source_subdir=data.get("source_subdir", ""),
        password=data.get("password", ""),
        retries=data.get("retries", DEFAULT_RETRIES),
        timeout=data.get("timeout", DEFAULT_TIMEOUT),
        log_level=data.get("log_level", DEFAULT_LOG_LEVEL),
        pipelines=pipelines,
        post_sync=data.get("post_sync", []),
        index_only=data.get("index_only", False),
        manifest_path=Path(manifest_path) if manifest_path else None,
    )


def _config_to_dict(config: SyncConfig) -> dict[str, Any]:
    """Convert a SyncConfig back to a dict for merging."""
    return {
        "source_url": config.source_url,
        "target_dir": config.target_dir,
        "source_type": config.source_type,
        "source_subdir": config.source_subdir,
        "password": config.password,
        "retries": config.retries,
        "timeout": config.timeout,
        "log_level": config.log_level,
        "pipelines": [
            {
                "pattern": p.pattern,
                "commands": p.commands,
                "delete_original": p.delete_original,
            }
            for p in config.pipelines
        ],
        "post_sync": config.post_sync,
        "index_only": config.index_only,
        "manifest_path": str(config.manifest_path) if config.manifest_path else None,
    }
