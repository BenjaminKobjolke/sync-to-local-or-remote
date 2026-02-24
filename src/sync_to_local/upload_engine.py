"""Upload engine orchestrator for sync-to-remote."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from sync_to_local.config import UploadConfig
from sync_to_local.manifest import Manifest
from sync_to_local.targets.base import TargetBase

logger = logging.getLogger(__name__)


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    with open(file_path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


class UploadEngine:
    """Orchestrates scanning, hashing, and uploading local files to a remote target."""

    def __init__(
        self,
        config: UploadConfig,
        target: TargetBase,
        manifest_path: Path,
    ) -> None:
        self._config = config
        self._target = target
        self._manifest = Manifest.load(manifest_path)

    def run(self) -> int:
        """Run an upload cycle. Returns 0 on success, 1 on partial failure."""
        logger.info("Scanning local files in %s ...", self._config.source_dir)
        local_files = self._scan_local_files()
        logger.info("Found %d local files", len(local_files))

        if self._config.index_only:
            return self._run_index_only(local_files)
        return self._run_normal(local_files)

    def _scan_local_files(self) -> list[Path]:
        """Recursively scan the source directory for all files."""
        source_dir = self._config.source_dir
        if not source_dir.is_dir():
            logger.error("Source directory does not exist: %s", source_dir)
            return []
        manifest_path = self._manifest.path.resolve()
        files = sorted(
            p
            for p in source_dir.rglob("*")
            if p.is_file() and p.resolve() != manifest_path
        )

        if self._config.file_filter:
            pattern = re.compile(self._config.file_filter)
            files = [
                p
                for p in files
                if pattern.search(p.relative_to(source_dir).as_posix())
            ]

        return files

    def _run_index_only(self, local_files: list[Path]) -> int:
        """Record all local files into manifest without uploading."""
        for file_path in local_files:
            relative = self._relative_path(file_path)
            content_hash = _compute_sha256(file_path)
            size = file_path.stat().st_size
            self._manifest.record_upload(relative, content_hash, size)
        self._manifest.save()
        logger.info("Index-only: recorded %d files in manifest", len(local_files))
        return 0

    def _run_normal(self, local_files: list[Path]) -> int:
        """Hash, diff, and upload new/changed files."""
        new_files: list[tuple[Path, str, int]] = []
        for file_path in local_files:
            relative = self._relative_path(file_path)
            content_hash = _compute_sha256(file_path)
            if self._manifest.is_new_or_changed_by_hash(relative, content_hash):
                size = file_path.stat().st_size
                new_files.append((file_path, content_hash, size))

        if not new_files:
            logger.info("No new or changed files to upload")
            return 0

        logger.info("%d new/changed files to upload", len(new_files))
        had_failure = False

        for file_path, content_hash, size in new_files:
            relative = self._relative_path(file_path)
            remote_path = self._remote_path(relative)
            logger.info("Uploading: %s", relative)

            try:
                self._target.upload_file(file_path, remote_path)
            except Exception:
                logger.exception("Failed to upload %s", relative)
                had_failure = True
                continue

            self._manifest.record_upload(relative, content_hash, size)
            self._manifest.save()

        return 1 if had_failure else 0

    def _relative_path(self, file_path: Path) -> str:
        """Get the path relative to source_dir, with forward slashes and leading slash."""
        rel = file_path.relative_to(self._config.source_dir)
        return "/" + rel.as_posix()

    def _remote_path(self, relative: str) -> str:
        """Build the full remote path from target_subdir + relative path."""
        subdir = self._config.target_subdir.rstrip("/")
        return subdir + relative
