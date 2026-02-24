"""Manifest tracking for downloaded files."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sync_to_local.constants import MANIFEST_VERSION


@dataclass
class ManifestEntry:
    """A single tracked file in the manifest."""

    path: str
    etag: str
    size: int


class Manifest:
    """Tracks which remote files have been downloaded and their etags."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: dict[str, ManifestEntry] = {}

    def is_new_or_changed(self, remote_path: str, etag: str) -> bool:
        """Check if a remote file is new or has a different etag."""
        entry = self.entries.get(remote_path)
        if entry is None:
            return True
        return entry.etag != etag

    def record(self, remote_path: str, etag: str, size: int) -> None:
        """Record a file as downloaded."""
        self.entries[remote_path] = ManifestEntry(path=remote_path, etag=etag, size=size)

    def save(self) -> None:
        """Save manifest to disk using atomic write (write to temp, then rename)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = {
            "version": MANIFEST_VERSION,
            "files": {
                path: {"etag": entry.etag, "size": entry.size}
                for path, entry in self.entries.items()
            },
        }

        # Atomic write: write to temp file in same directory, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".manifest_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            # On Windows, need to remove target first if it exists
            if self.path.exists():
                self.path.unlink()
            os.rename(tmp_path, self.path)
        except BaseException:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    @classmethod
    def load(cls, path: Path) -> Manifest:
        """Load a manifest from disk. Returns empty manifest if file doesn't exist."""
        m = cls(path)
        if not path.exists():
            return m

        with open(path) as f:
            data: dict[str, Any] = json.load(f)

        files = data.get("files", {})
        for file_path, file_data in files.items():
            m.entries[file_path] = ManifestEntry(
                path=file_path,
                etag=file_data["etag"],
                size=file_data["size"],
            )

        return m
