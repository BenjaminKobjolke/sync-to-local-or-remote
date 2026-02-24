"""Base classes for remote upload targets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TargetBase(ABC):
    """Abstract base class for remote upload targets."""

    @abstractmethod
    def ensure_directory(self, remote_path: str) -> None:
        """Ensure a remote directory exists, creating it if necessary."""
        ...

    @abstractmethod
    def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file to the given remote path."""
        ...
