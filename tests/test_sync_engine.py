"""Tests for sync engine."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from sync_to_local.config import PipelineConfig, SyncConfig
from sync_to_local.manifest import Manifest
from sync_to_local.sources.base import RemoteFile
from sync_to_local.sync_engine import SyncEngine


def _make_config(tmp_dir: Path, **kwargs: object) -> SyncConfig:
    defaults: dict[str, object] = {
        "source_url": "https://share.example.com/s/TOKEN",
        "target_dir": tmp_dir / "output",
        "source_subdir": "/data",
    }
    defaults.update(kwargs)
    return SyncConfig(**defaults)  # type: ignore[arg-type]


def _make_remote_file(path: str, etag: str = '"e1"', size: int = 100) -> RemoteFile:
    return RemoteFile(path=path, size=size, etag=etag, last_modified="")


class TestSyncEngineNormalMode:
    def test_downloads_new_files(self, tmp_dir: Path) -> None:
        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        source = MagicMock()
        source.list_files.return_value = [
            _make_remote_file("/data/file1.txt"),
            _make_remote_file("/data/file2.txt"),
        ]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 0
        assert source.download_file.call_count == 2

        # Manifest should be saved
        m = Manifest.load(manifest_path)
        assert "/data/file1.txt" in m.entries
        assert "/data/file2.txt" in m.entries

    def test_skips_already_downloaded_files(self, tmp_dir: Path) -> None:
        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        # Pre-populate manifest
        m = Manifest(manifest_path)
        m.record("/data/file1.txt", '"e1"', 100)
        m.save()

        source = MagicMock()
        source.list_files.return_value = [
            _make_remote_file("/data/file1.txt", etag='"e1"'),
            _make_remote_file("/data/file2.txt", etag='"e2"'),
        ]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 0
        # Only file2 should be downloaded
        assert source.download_file.call_count == 1
        call_args = source.download_file.call_args[0]
        assert call_args[0].path == "/data/file2.txt"

    def test_downloads_changed_etag(self, tmp_dir: Path) -> None:
        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        m = Manifest(manifest_path)
        m.record("/data/file1.txt", '"old_etag"', 100)
        m.save()

        source = MagicMock()
        source.list_files.return_value = [
            _make_remote_file("/data/file1.txt", etag='"new_etag"'),
        ]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 0
        assert source.download_file.call_count == 1

    @patch("sync_to_local.sync_engine.PipelineRunner")
    def test_runs_pipeline_after_download(self, mock_runner_cls: MagicMock, tmp_dir: Path) -> None:
        pipes = [PipelineConfig(pattern=r"\.txt$", commands=["echo {file}"])]
        config = _make_config(tmp_dir, pipelines=pipes)
        manifest_path = tmp_dir / "manifest.json"

        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner_cls.return_value = mock_runner

        source = MagicMock()
        source.list_files.return_value = [_make_remote_file("/data/file1.txt")]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 0
        mock_runner.run.assert_called_once()

    @patch("sync_to_local.sync_engine.PipelineRunner")
    def test_pipeline_failure_continues_sync(
        self, mock_runner_cls: MagicMock, tmp_dir: Path
    ) -> None:
        pipes = [PipelineConfig(pattern=r"\.txt$", commands=["fail"])]
        config = _make_config(tmp_dir, pipelines=pipes)
        manifest_path = tmp_dir / "manifest.json"

        mock_runner = MagicMock()
        mock_runner.run.return_value = False  # pipeline fails
        mock_runner_cls.return_value = mock_runner

        source = MagicMock()
        source.list_files.return_value = [
            _make_remote_file("/data/file1.txt"),
            _make_remote_file("/data/file2.txt"),
        ]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        # Returns 1 for partial failure
        assert result == 1
        # Both files should still be downloaded
        assert source.download_file.call_count == 2
        # Manifest should still track both files
        m = Manifest.load(manifest_path)
        assert "/data/file1.txt" in m.entries
        assert "/data/file2.txt" in m.entries

    def test_preserves_directory_structure(self, tmp_dir: Path) -> None:
        config = _make_config(tmp_dir)
        manifest_path = tmp_dir / "manifest.json"

        source = MagicMock()
        source.list_files.return_value = [
            _make_remote_file("/data/sub/deep/file.txt"),
        ]

        engine = SyncEngine(config, source, manifest_path)
        engine.run()

        # Verify download was called with correct local path
        call_args = source.download_file.call_args[0]
        local_path: Path = call_args[1]
        expected = tmp_dir / "output" / "data" / "sub" / "deep" / "file.txt"
        assert local_path == expected


class TestSyncEngineIndexOnly:
    def test_index_only_records_without_downloading(self, tmp_dir: Path) -> None:
        config = _make_config(tmp_dir, index_only=True)
        manifest_path = tmp_dir / "manifest.json"

        source = MagicMock()
        source.list_files.return_value = [
            _make_remote_file("/data/file1.txt", etag='"e1"'),
            _make_remote_file("/data/file2.txt", etag='"e2"'),
        ]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 0
        # No downloads
        source.download_file.assert_not_called()
        # But manifest is populated
        m = Manifest.load(manifest_path)
        assert len(m.entries) == 2
        assert "/data/file1.txt" in m.entries
        assert "/data/file2.txt" in m.entries

    @patch("sync_to_local.sync_engine.PipelineRunner")
    def test_index_only_skips_pipelines(
        self, mock_runner_cls: MagicMock, tmp_dir: Path
    ) -> None:
        pipes = [PipelineConfig(pattern=r"\.txt$", commands=["echo {file}"])]
        config = _make_config(tmp_dir, index_only=True, pipelines=pipes)
        manifest_path = tmp_dir / "manifest.json"

        source = MagicMock()
        source.list_files.return_value = [_make_remote_file("/data/file1.txt")]

        engine = SyncEngine(config, source, manifest_path)
        engine.run()

        mock_runner_cls.return_value.run.assert_not_called()
        mock_runner_cls.return_value.run_post_sync.assert_not_called()


class TestSyncEnginePostSync:
    @patch("sync_to_local.sync_engine.PipelineRunner")
    def test_post_sync_runs_after_downloads(
        self, mock_runner_cls: MagicMock, tmp_dir: Path
    ) -> None:
        config = _make_config(tmp_dir, post_sync=["echo done"])
        manifest_path = tmp_dir / "manifest.json"

        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner.run_post_sync.return_value = True
        mock_runner_cls.return_value = mock_runner

        source = MagicMock()
        source.list_files.return_value = [_make_remote_file("/data/file1.txt")]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 0
        mock_runner.run_post_sync.assert_called_once_with(
            ["echo done"], config.target_dir
        )

    @patch("sync_to_local.sync_engine.PipelineRunner")
    def test_post_sync_skipped_when_no_new_files(
        self, mock_runner_cls: MagicMock, tmp_dir: Path
    ) -> None:
        config = _make_config(tmp_dir, post_sync=["echo done"])
        manifest_path = tmp_dir / "manifest.json"

        # Pre-populate manifest so nothing is new
        m = Manifest(manifest_path)
        m.record("/data/file1.txt", '"e1"', 100)
        m.save()

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        source = MagicMock()
        source.list_files.return_value = [
            _make_remote_file("/data/file1.txt", etag='"e1"'),
        ]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 0
        mock_runner.run_post_sync.assert_not_called()

    @patch("sync_to_local.sync_engine.PipelineRunner")
    def test_post_sync_failure_returns_exit_1(
        self, mock_runner_cls: MagicMock, tmp_dir: Path
    ) -> None:
        config = _make_config(tmp_dir, post_sync=["fail"])
        manifest_path = tmp_dir / "manifest.json"

        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner.run_post_sync.return_value = False
        mock_runner_cls.return_value = mock_runner

        source = MagicMock()
        source.list_files.return_value = [_make_remote_file("/data/file1.txt")]

        engine = SyncEngine(config, source, manifest_path)
        result = engine.run()

        assert result == 1

    @patch("sync_to_local.sync_engine.PipelineRunner")
    def test_post_sync_skipped_in_index_only(
        self, mock_runner_cls: MagicMock, tmp_dir: Path
    ) -> None:
        config = _make_config(tmp_dir, index_only=True, post_sync=["echo done"])
        manifest_path = tmp_dir / "manifest.json"

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        source = MagicMock()
        source.list_files.return_value = [_make_remote_file("/data/file1.txt")]

        engine = SyncEngine(config, source, manifest_path)
        engine.run()

        mock_runner.run_post_sync.assert_not_called()
