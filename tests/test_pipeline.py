"""Tests for pipeline module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from sync_to_local.config import PipelineConfig
from sync_to_local.pipeline import PipelineRunner


class TestPipelineRunner:
    def setup_method(self) -> None:
        self.runner = PipelineRunner()

    def test_no_pipelines_returns_true(self) -> None:
        result = self.runner.run(Path("/tmp/file.txt"), [])
        assert result is True

    def test_no_matching_pipeline_returns_true(self) -> None:
        pipelines = [PipelineConfig(pattern=r"\.webm$", commands=["echo {file}"])]
        result = self.runner.run(Path("/tmp/file.txt"), pipelines)
        assert result is True

    @patch("sync_to_local.pipeline.subprocess.run")
    def test_matching_pipeline_runs_command(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        pipelines = [PipelineConfig(pattern=r"\.mp4$", commands=["echo {file}"])]

        result = self.runner.run(Path("/tmp/video.mp4"), pipelines)

        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "/tmp/video.mp4" in cmd or "\\tmp\\video.mp4" in cmd

    @patch("sync_to_local.pipeline.subprocess.run")
    def test_command_failure_stops_pipeline(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        pipelines = [
            PipelineConfig(
                pattern=r"\.mp4$",
                commands=["cmd1 {file}", "cmd2 {file}"],
            )
        ]

        result = self.runner.run(Path("/tmp/video.mp4"), pipelines)

        assert result is False
        # Only first command should have been called
        assert mock_run.call_count == 1

    @patch("sync_to_local.pipeline.subprocess.run")
    def test_all_commands_run_on_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        pipelines = [
            PipelineConfig(
                pattern=r"\.mp4$",
                commands=["cmd1 {file}", "cmd2 {file}"],
            )
        ]

        result = self.runner.run(Path("/tmp/video.mp4"), pipelines)

        assert result is True
        assert mock_run.call_count == 2

    @patch("sync_to_local.pipeline.subprocess.run")
    def test_only_first_matching_pipeline_runs(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        pipelines = [
            PipelineConfig(pattern=r"\.mp4$", commands=["first {file}"]),
            PipelineConfig(pattern=r"\.mp4$", commands=["second {file}"]),
        ]

        result = self.runner.run(Path("/tmp/video.mp4"), pipelines)

        assert result is True
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "first" in cmd

    def test_placeholder_expansion_file(self) -> None:
        expanded = self.runner._expand_placeholders(
            "echo {file}", Path("/tmp/data/video.mp4")
        )
        assert "video.mp4" in expanded

    def test_placeholder_expansion_file_stem(self) -> None:
        expanded = self.runner._expand_placeholders(
            "echo {file_stem}", Path("/tmp/data/video.mp4")
        )
        path = Path(expanded.split(" ", 1)[1])
        assert path.name == "video"

    def test_placeholder_expansion_file_name(self) -> None:
        expanded = self.runner._expand_placeholders(
            "echo {file_name}", Path("/tmp/data/video.mp4")
        )
        assert "video.mp4" in expanded

    def test_placeholder_expansion_file_dir(self) -> None:
        expanded = self.runner._expand_placeholders(
            "echo {file_dir}", Path("/tmp/data/video.mp4")
        )
        assert "data" in expanded or "tmp" in expanded


class TestPostSync:
    def setup_method(self) -> None:
        self.runner = PipelineRunner()

    @patch("sync_to_local.pipeline.subprocess.run")
    def test_runs_all_commands(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = self.runner.run_post_sync(
            ["echo one", "echo two"], Path("/tmp/output")
        )
        assert result is True
        assert mock_run.call_count == 2

    @patch("sync_to_local.pipeline.subprocess.run")
    def test_stops_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = self.runner.run_post_sync(
            ["fail", "never_reached"], Path("/tmp/output")
        )
        assert result is False
        assert mock_run.call_count == 1

    @patch("sync_to_local.pipeline.subprocess.run")
    def test_expands_target_dir_placeholder(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        self.runner.run_post_sync(
            ["echo {target_dir}"], Path("/tmp/output")
        )
        cmd = mock_run.call_args[0][0]
        assert "/tmp/output" in cmd or "\\tmp\\output" in cmd

    def test_empty_commands_returns_true(self) -> None:
        result = self.runner.run_post_sync([], Path("/tmp/output"))
        assert result is True
