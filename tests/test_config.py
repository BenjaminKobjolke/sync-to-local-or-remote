"""Tests for config module."""

import json
from pathlib import Path

import pytest

from sync_to_local.config import PipelineConfig, SyncConfig, load_config, merge_cli_args


class TestPipelineConfig:
    def test_create(self) -> None:
        p = PipelineConfig(pattern=r"\.mp4$", commands=["echo {file}"])
        assert p.pattern == r"\.mp4$"
        assert p.commands == ["echo {file}"]

    def test_frozen(self) -> None:
        p = PipelineConfig(pattern=r"\.mp4$", commands=["echo {file}"])
        with pytest.raises(AttributeError):
            p.pattern = "new"  # type: ignore[misc]


class TestSyncConfig:
    def test_defaults(self) -> None:
        cfg = SyncConfig(source_url="https://example.com/s/abc", target_dir=Path("/tmp/out"))
        assert cfg.source_type == "nextcloud"
        assert cfg.source_subdir == ""
        assert cfg.password == ""
        assert cfg.retries == 3
        assert cfg.timeout == 30
        assert cfg.log_level == "INFO"
        assert cfg.pipelines == []
        assert cfg.post_sync == []
        assert cfg.index_only is False
        assert cfg.manifest_path is None

    def test_frozen(self) -> None:
        cfg = SyncConfig(source_url="https://example.com/s/abc", target_dir=Path("/tmp/out"))
        with pytest.raises(AttributeError):
            cfg.source_url = "new"  # type: ignore[misc]

    def test_custom_values(self) -> None:
        pipes = [PipelineConfig(pattern=r"\.webm$", commands=["ffmpeg -i {file}"])]
        cfg = SyncConfig(
            source_url="https://example.com/s/abc",
            target_dir=Path("/data"),
            source_type="nextcloud",
            source_subdir="/sub",
            password="secret",
            retries=5,
            timeout=60,
            log_level="DEBUG",
            pipelines=pipes,
            index_only=True,
            manifest_path=Path("/tmp/manifest.json"),
        )
        assert cfg.source_subdir == "/sub"
        assert cfg.password == "secret"
        assert cfg.retries == 5
        assert cfg.timeout == 60
        assert cfg.log_level == "DEBUG"
        assert len(cfg.pipelines) == 1
        assert cfg.index_only is True
        assert cfg.manifest_path == Path("/tmp/manifest.json")


class TestLoadConfig:
    def test_load_minimal_json(self, tmp_dir: Path) -> None:
        config_file = tmp_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "source_url": "https://share.example.com/s/TOKEN123",
                    "target_dir": str(tmp_dir / "output"),
                }
            )
        )
        cfg = load_config(config_file)
        assert cfg.source_url == "https://share.example.com/s/TOKEN123"
        assert cfg.target_dir == tmp_dir / "output"
        assert cfg.source_type == "nextcloud"

    def test_load_full_json(self, tmp_dir: Path) -> None:
        config_file = tmp_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "source_url": "https://share.example.com/s/TOKEN123",
                    "source_subdir": "/_data",
                    "source_type": "nextcloud",
                    "target_dir": str(tmp_dir / "output"),
                    "password": "pw",
                    "retries": 5,
                    "timeout": 60,
                    "log_level": "DEBUG",
                    "pipelines": [
                        {
                            "pattern": r"\.webm$",
                            "commands": ["ffmpeg -i {file} {file_stem}.mp4"],
                        }
                    ],
                    "post_sync": ["echo done"],
                }
            )
        )
        cfg = load_config(config_file)
        assert cfg.source_subdir == "/_data"
        assert cfg.password == "pw"
        assert cfg.post_sync == ["echo done"]
        assert cfg.retries == 5
        assert len(cfg.pipelines) == 1
        assert cfg.pipelines[0].pattern == r"\.webm$"

    def test_load_missing_file_raises(self, tmp_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_dir / "nonexistent.json")


class TestMergeCliArgs:
    def test_cli_overrides_config(self, tmp_dir: Path) -> None:
        config_file = tmp_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "source_url": "https://share.example.com/s/TOKEN123",
                    "target_dir": str(tmp_dir / "output"),
                    "retries": 2,
                    "log_level": "DEBUG",
                }
            )
        )
        base = load_config(config_file)
        cli_overrides = {
            "source_url": "https://other.example.com/s/NEW",
            "retries": 10,
            "log_level": None,  # None means not provided on CLI
            "target_dir": None,
        }
        merged = merge_cli_args(base, cli_overrides)
        assert merged.source_url == "https://other.example.com/s/NEW"
        assert merged.retries == 10
        assert merged.log_level == "DEBUG"  # kept from config since CLI was None
        assert merged.target_dir == tmp_dir / "output"  # kept from config

    def test_cli_only_no_config_file(self, tmp_dir: Path) -> None:
        cli_overrides = {
            "source_url": "https://share.example.com/s/TOKEN123",
            "target_dir": str(tmp_dir / "output"),
        }
        merged = merge_cli_args(None, cli_overrides)
        assert merged.source_url == "https://share.example.com/s/TOKEN123"
        assert merged.target_dir == tmp_dir / "output"

    def test_url_dir_param_extracted_as_subdir(self, tmp_dir: Path) -> None:
        cli_overrides = {
            "source_url": "https://share.example.com/s/TOKEN123?dir=/_von_DYADIC",
            "target_dir": str(tmp_dir / "output"),
        }
        merged = merge_cli_args(None, cli_overrides)
        assert merged.source_url == "https://share.example.com/s/TOKEN123"
        assert merged.source_subdir == "/_von_DYADIC"

    def test_explicit_subdir_overrides_url_param(self, tmp_dir: Path) -> None:
        cli_overrides = {
            "source_url": "https://share.example.com/s/TOKEN123?dir=/_von_DYADIC",
            "target_dir": str(tmp_dir / "output"),
            "source_subdir": "/explicit",
        }
        merged = merge_cli_args(None, cli_overrides)
        assert merged.source_subdir == "/explicit"

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="source_url"):
            merge_cli_args(None, {})
