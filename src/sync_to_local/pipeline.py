"""Post-download pipeline runner."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from sync_to_local.config import PipelineConfig

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Matches files against pipeline patterns and runs commands sequentially."""

    def run(self, local_path: Path, pipelines: list[PipelineConfig]) -> bool:
        """Run the first matching pipeline for the given file.

        Returns True if all commands succeeded (or no pipeline matched).
        Returns False if any command failed.
        """
        for pipeline in pipelines:
            if re.search(pipeline.pattern, str(local_path)):
                for cmd_template in pipeline.commands:
                    cmd = self._expand_placeholders(cmd_template, local_path)
                    logger.info("Running pipeline command: %s", cmd)
                    result = subprocess.run(cmd, shell=True)
                    if result.returncode != 0:
                        logger.error(
                            "Pipeline command failed (exit %d): %s",
                            result.returncode,
                            cmd,
                        )
                        return False
                if pipeline.delete_original:
                    logger.info("Deleting original file: %s", local_path)
                    local_path.unlink()
                return True  # all commands in this pipeline succeeded
        return True  # no matching pipeline

    def run_post_sync(self, commands: list[str], target_dir: Path) -> bool:
        """Run post-sync commands sequentially.

        Returns True if all commands succeeded, False on first failure.
        """
        for cmd_template in commands:
            cmd = cmd_template.format(target_dir=str(target_dir))
            logger.info("Running post-sync command: %s", cmd)
            result = subprocess.run(cmd, shell=True)
            if result.returncode != 0:
                logger.error(
                    "Post-sync command failed (exit %d): %s",
                    result.returncode,
                    cmd,
                )
                return False
        return True

    def _expand_placeholders(self, template: str, local_path: Path) -> str:
        """Expand {file}, {file_stem}, {file_name}, {file_dir} placeholders."""
        return template.format(
            file=str(local_path),
            file_stem=str(local_path.with_suffix("")),
            file_name=local_path.name,
            file_dir=str(local_path.parent),
        )
