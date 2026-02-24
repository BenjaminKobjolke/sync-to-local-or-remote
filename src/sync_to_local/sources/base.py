"""Base classes for remote file sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RemoteFile:
    """A file discovered on a remote source."""

    path: str
    size: int
    etag: str
    last_modified: str


class SourceBase(ABC):
    """Abstract base class for remote file sources."""

    @abstractmethod
    def list_files(self) -> list[RemoteFile]:
        """List all files available on the remote source (recursive)."""
        ...

    @abstractmethod
    def download_file(self, remote_file: RemoteFile, local_path: Path) -> None:
        """Download a remote file to the given local path."""
        ...
