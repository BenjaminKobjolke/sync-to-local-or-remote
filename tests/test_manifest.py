"""Tests for manifest module."""

import json
from pathlib import Path

from sync_to_local.manifest import Manifest, ManifestEntry


class TestManifestEntry:
    def test_create(self) -> None:
        entry = ManifestEntry(path="/docs/file.txt", etag='"abc123"', size=1024)
        assert entry.path == "/docs/file.txt"
        assert entry.etag == '"abc123"'
        assert entry.size == 1024


class TestManifest:
    def test_empty_manifest(self, tmp_dir: Path) -> None:
        m = Manifest(tmp_dir / "manifest.json")
        assert m.entries == {}

    def test_is_new_or_changed_new_file(self, tmp_dir: Path) -> None:
        m = Manifest(tmp_dir / "manifest.json")
        assert m.is_new_or_changed("/file.txt", '"etag1"') is True

    def test_is_new_or_changed_same_etag(self, tmp_dir: Path) -> None:
        m = Manifest(tmp_dir / "manifest.json")
        m.record("/file.txt", '"etag1"', 100)
        assert m.is_new_or_changed("/file.txt", '"etag1"') is False

    def test_is_new_or_changed_different_etag(self, tmp_dir: Path) -> None:
        m = Manifest(tmp_dir / "manifest.json")
        m.record("/file.txt", '"etag1"', 100)
        assert m.is_new_or_changed("/file.txt", '"etag2"') is True

    def test_record_and_retrieve(self, tmp_dir: Path) -> None:
        m = Manifest(tmp_dir / "manifest.json")
        m.record("/a/b.txt", '"e1"', 50)
        assert "/a/b.txt" in m.entries
        assert m.entries["/a/b.txt"].etag == '"e1"'
        assert m.entries["/a/b.txt"].size == 50

    def test_save_and_load(self, tmp_dir: Path) -> None:
        path = tmp_dir / "manifest.json"
        m = Manifest(path)
        m.record("/file1.txt", '"e1"', 100)
        m.record("/dir/file2.txt", '"e2"', 200)
        m.save()

        # Load into a new Manifest instance
        m2 = Manifest.load(path)
        assert len(m2.entries) == 2
        assert m2.entries["/file1.txt"].etag == '"e1"'
        assert m2.entries["/dir/file2.txt"].size == 200

    def test_load_nonexistent_returns_empty(self, tmp_dir: Path) -> None:
        m = Manifest.load(tmp_dir / "nonexistent.json")
        assert m.entries == {}

    def test_save_creates_parent_dirs(self, tmp_dir: Path) -> None:
        path = tmp_dir / "sub" / "dir" / "manifest.json"
        m = Manifest(path)
        m.record("/file.txt", '"e1"', 100)
        m.save()
        assert path.exists()

    def test_crash_safe_save(self, tmp_dir: Path) -> None:
        """Save should write to a temp file first, then rename."""
        path = tmp_dir / "manifest.json"
        m = Manifest(path)
        m.record("/file.txt", '"e1"', 100)
        m.save()

        # File should exist and be valid JSON
        data = json.loads(path.read_text())
        assert data["version"] == 1
        assert "/file.txt" in data["files"]

    def test_manifest_json_format(self, tmp_dir: Path) -> None:
        path = tmp_dir / "manifest.json"
        m = Manifest(path)
        m.record("/file.txt", '"e1"', 100)
        m.save()

        data = json.loads(path.read_text())
        assert "version" in data
        assert "files" in data
        file_entry = data["files"]["/file.txt"]
        assert file_entry["etag"] == '"e1"'
        assert file_entry["size"] == 100
