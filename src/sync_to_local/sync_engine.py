"""Sync engine orchestrator."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from sync_to_local.config import SyncConfig
from sync_to_local.manifest import Manifest
from sync_to_local.pipeline import PipelineRunner
from sync_to_local.sources.base import SourceBase

logger = logging.getLogger(__name__)


class SyncEngine:
    """Orchestrates listing, diffing, downloading, and running pipelines."""

    def __init__(
        self,
        config: SyncConfig,
        source: SourceBase,
        manifest_path: Path,
    ) -> None:
        self._config = config
        self._source = source
        self._manifest = Manifest.load(manifest_path)
        self._pipeline_runner = PipelineRunner()

    def run(self) -> int:
        """Run a sync cycle. Returns 0 on success, 1 on partial failure."""
        logger.info("Listing remote files...")
        remote_files = self._source.list_files()
        logger.info("Found %d remote files", len(remote_files))

        if self._config.index_only:
            return self._run_index_only(remote_files)
        return self._run_normal(remote_files)

    def _run_index_only(self, remote_files: list) -> int:  # type: ignore[type-arg]
        """Record all remote files into manifest without downloading."""
        for rf in remote_files:
            self._manifest.record(rf.path, rf.etag, rf.size)
        self._manifest.save()
        logger.info("Index-only: recorded %d files in manifest", len(remote_files))
        return 0

    def _run_normal(self, remote_files: list) -> int:  # type: ignore[type-arg]
        """Download new/changed files and run pipelines."""
        new_files = [
            rf for rf in remote_files if self._manifest.is_new_or_changed(rf.path, rf.etag)
        ]

        if not new_files:
            logger.info("No new or changed files to download")
            return 0

        logger.info("%d new/changed files to download", len(new_files))
        had_failure = False

        for rf in new_files:
            # Build local path: target_dir + remote path
            local_path = self._config.target_dir / rf.path.lstrip("/")
            logger.info("Downloading: %s", rf.path)

            try:
                self._source.download_file(rf, local_path)
            except Exception:
                logger.exception("Failed to download %s", rf.path)
                had_failure = True
                continue

            # Run pipeline
            if self._config.pipelines:
                success = self._pipeline_runner.run(local_path, self._config.pipelines)
                if not success:
                    logger.warning("Pipeline failed for %s", rf.path)
                    had_failure = True

            # Record in manifest and save (crash-safe: save after each file)
            self._manifest.record(rf.path, rf.etag, rf.size)
            self._manifest.save()

        # Route files to target directories by pattern
        if self._config.routes:
            self._run_routes()

        # Run post-sync commands if any files were downloaded
        if self._config.post_sync:
            logger.info("Running post-sync commands...")
            success = self._pipeline_runner.run_post_sync(
                self._config.post_sync, self._config.target_dir
            )
            if not success:
                had_failure = True

        return 1 if had_failure else 0

    def _run_routes(self) -> None:
        """Move files from target_dir to route destinations based on pattern matching."""
        manifest_name = self._manifest.path.name
        for file_path in sorted(self._config.target_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name == manifest_name:
                continue
            for route in self._config.routes:
                if re.search(route.pattern, file_path.name):
                    dest_dir = route.target_dir
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / file_path.name
                    logger.info("Route: %s -> %s", file_path, dest)
                    shutil.move(str(file_path), str(dest))
                    break
