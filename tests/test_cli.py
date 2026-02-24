"""Tests for CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sync_to_local.cli import build_parser, run


class TestBuildParser:
    def test_required_args_source_url_and_target_dir(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "--source-url", "https://example.com/s/abc", "--target-dir", "/tmp",
        ])
        assert args.source_url == "https://example.com/s/abc"
        assert args.target_dir == "/tmp"

    def test_config_file_only(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--config", "config.json"])
        assert args.config == "config.json"
        assert args.source_url is None

    def test_all_optional_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "--source-url", "https://example.com/s/abc",
            "--target-dir", "/tmp",
            "--source-type", "nextcloud",
            "--source-subdir", "/data",
            "--password", "secret",
            "--config", "c.json",
            "--manifest-path", "/tmp/m.json",
            "--retries", "5",
            "--timeout", "60",
            "--log-level", "DEBUG",
            "--index-only",
        ])
        assert args.source_type == "nextcloud"
        assert args.source_subdir == "/data"
        assert args.password == "secret"
        assert args.manifest_path == "/tmp/m.json"
        assert args.retries == 5
        assert args.timeout == 60
        assert args.log_level == "DEBUG"
        assert args.index_only is True

    def test_index_only_default_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--source-url", "https://x.com/s/a", "--target-dir", "/tmp"])
        assert args.index_only is False


class TestRun:
    @patch("sync_to_local.cli.SyncEngine")
    @patch("sync_to_local.cli.create_source")
    def test_run_with_config_file(
        self,
        mock_create_source: MagicMock,
        mock_engine_cls: MagicMock,
        tmp_dir: Path,
    ) -> None:
        import json

        config_file = tmp_dir / "config.json"
        config_file.write_text(json.dumps({
            "source_url": "https://share.example.com/s/TOKEN",
            "target_dir": str(tmp_dir / "output"),
        }))

        mock_engine = MagicMock()
        mock_engine.run.return_value = 0
        mock_engine_cls.return_value = mock_engine

        with pytest.raises(SystemExit) as exc_info:
            run(["--config", str(config_file)])

        assert exc_info.value.code == 0
        mock_engine.run.assert_called_once()

    @patch("sync_to_local.cli.SyncEngine")
    @patch("sync_to_local.cli.create_source")
    def test_run_with_cli_args(
        self,
        mock_create_source: MagicMock,
        mock_engine_cls: MagicMock,
        tmp_dir: Path,
    ) -> None:
        mock_engine = MagicMock()
        mock_engine.run.return_value = 0
        mock_engine_cls.return_value = mock_engine

        with pytest.raises(SystemExit) as exc_info:
            run([
                "--source-url", "https://share.example.com/s/TOKEN?dir=/_data",
                "--target-dir", str(tmp_dir / "output"),
            ])

        assert exc_info.value.code == 0

    def test_run_missing_required_args_exits(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            run([])  # no args at all

        assert exc_info.value.code != 0
