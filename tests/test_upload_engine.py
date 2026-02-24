"""Tests for upload engine."""

from pathlib import Path
from unittest.mock import MagicMock

from sync_to_local.config import UploadConfig
from sync_to_local.manifest import Manifest
from sync_to_local.upload_engine import UploadEngine, _compute_sha256


def _make_config(tmp_dir: Path, **kwargs: object) -> UploadConfig:
    defaults: dict[str, object] = {
        "source_dir": tmp_dir / "source",
        "target_url": "https://share.example.com/s/TOKEN",
        "target_subdir": "/data",
    }
    defaults.update(kwargs)
    return UploadConfig(**defaults)  # type: ignore[arg-type]


def _create_file(path: Path, content: str = "hello") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class TestComputeSha256:
    def test_consistent_hash(self, tmp_dir: Path) -> None:
        f = _create_file(tmp_dir / "test.txt", "hello world")
        h1 = _compute_sha256(f)
        h2 = _compute_sha256(f)
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex digest length

    def test_different_content_different_hash(self, tmp_dir: Path) -> None:
        f1 = _create_file(tmp_dir / "a.txt", "hello")
        f2 = _create_file(tmp_dir / "b.txt", "world")
        assert _compute_sha256(f1) != _compute_sha256(f2)


class TestUploadEngineNormalMode:
    def test_uploads_new_files(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "file1.txt", "content1")
        _create_file(source_dir / "file2.txt", "content2")

        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        assert target.upload_file.call_count == 2

        # Manifest should be saved
        m = Manifest.load(manifest_path)
        assert "/file1.txt" in m.entries
        assert "/file2.txt" in m.entries

    def test_skips_already_uploaded_files(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        f1 = _create_file(source_dir / "file1.txt", "content1")
        _create_file(source_dir / "file2.txt", "content2")

        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        # Pre-populate manifest for file1
        m = Manifest(manifest_path)
        m.record_upload("/file1.txt", _compute_sha256(f1), f1.stat().st_size)
        m.save()

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        # Only file2 should be uploaded
        assert target.upload_file.call_count == 1
        call_args = target.upload_file.call_args[0]
        assert call_args[0].name == "file2.txt"

    def test_uploads_changed_file(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "file1.txt", "new_content")

        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        # Pre-populate with old hash
        m = Manifest(manifest_path)
        m.record_upload("/file1.txt", "old_hash", 100)
        m.save()

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        assert target.upload_file.call_count == 1

    def test_remote_path_includes_target_subdir(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "sub" / "file.txt", "data")

        config = _make_config(tmp_dir, target_subdir="/upload_target")
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        engine.run()

        call_args = target.upload_file.call_args[0]
        remote_path: str = call_args[1]
        assert remote_path == "/upload_target/sub/file.txt"

    def test_upload_failure_continues(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "file1.txt", "content1")
        _create_file(source_dir / "file2.txt", "content2")

        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        target.upload_file.side_effect = [Exception("fail"), None]

        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 1  # partial failure
        assert target.upload_file.call_count == 2

        # Only file2 should be in manifest (file1 failed)
        m = Manifest.load(manifest_path)
        assert "/file1.txt" not in m.entries
        assert "/file2.txt" in m.entries

    def test_no_new_files(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        f = _create_file(source_dir / "file1.txt", "content")

        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        m = Manifest(manifest_path)
        m.record_upload("/file1.txt", _compute_sha256(f), f.stat().st_size)
        m.save()

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        target.upload_file.assert_not_called()

    def test_empty_source_dir(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        source_dir.mkdir(parents=True)

        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        target.upload_file.assert_not_called()

    def test_nonexistent_source_dir(self, tmp_dir: Path) -> None:
        config = _make_config(tmp_dir, source_dir=tmp_dir / "nonexistent")
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        target.upload_file.assert_not_called()


class TestUploadEngineIndexOnly:
    def test_index_only_records_without_uploading(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "file1.txt", "content1")
        _create_file(source_dir / "file2.txt", "content2")

        config = _make_config(tmp_dir, index_only=True)
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        target.upload_file.assert_not_called()

        m = Manifest.load(manifest_path)
        assert len(m.entries) == 2
        assert "/file1.txt" in m.entries
        assert "/file2.txt" in m.entries
        # Check that content_hash is recorded
        assert m.entries["/file1.txt"].content_hash != ""


class TestFileFilter:
    def test_filter_includes_matching_files(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "app.apk", "apk_content")
        _create_file(source_dir / "readme.txt", "text_content")
        _create_file(source_dir / "sub" / "other.apk", "apk2")

        config = _make_config(tmp_dir, file_filter=r"\.apk$")
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        assert target.upload_file.call_count == 2
        uploaded = {call[0][0].name for call in target.upload_file.call_args_list}
        assert uploaded == {"app.apk", "other.apk"}

    def test_filter_excludes_non_matching_files(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "readme.txt", "text")
        _create_file(source_dir / "notes.md", "markdown")

        config = _make_config(tmp_dir, file_filter=r"\.apk$")
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        target.upload_file.assert_not_called()

    def test_empty_filter_includes_all_files(self, tmp_dir: Path) -> None:
        source_dir = tmp_dir / "source"
        _create_file(source_dir / "app.apk", "apk")
        _create_file(source_dir / "readme.txt", "text")

        config = _make_config(tmp_dir, file_filter="")
        manifest_path = tmp_dir / "manifest.json"

        target = MagicMock()
        engine = UploadEngine(config, target, manifest_path)
        result = engine.run()

        assert result == 0
        assert target.upload_file.call_count == 2
