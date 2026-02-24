"""CLI argument parsing for sync-to-remote."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from sync_to_local.config import UploadConfig, load_upload_config, merge_upload_cli_args
from sync_to_local.constants import DEFAULT_UPLOAD_MANIFEST_FILENAME
from sync_to_local.targets import create_target
from sync_to_local.upload_engine import UploadEngine


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for sync-to-remote."""
    parser = argparse.ArgumentParser(
        prog="sync-to-remote",
        description="Sync files from a local folder to a remote target (Nextcloud, etc.)",
    )
    parser.add_argument("--source-dir", default=None, help="Local directory to upload from")
    parser.add_argument("--target-url", default=None, help="Remote target URL")
    parser.add_argument("--target-type", default=None, help="Target type (default: nextcloud)")
    parser.add_argument("--target-subdir", default=None, help="Subdirectory on target")
    parser.add_argument("--password", default=None, help="Share password (if any)")
    parser.add_argument("--config", default=None, help="Path to JSON config file")
    parser.add_argument("--manifest-path", default=None, help="Path to manifest file")
    parser.add_argument("--retries", type=int, default=None, help="Number of retries")
    parser.add_argument("--timeout", type=int, default=None, help="Request timeout in seconds")
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING"],
        help="Logging level",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        default=False,
        help="Scan local files and write manifest without uploading",
    )
    parser.add_argument(
        "--file-filter",
        default=None,
        help="Regex pattern to filter which files are uploaded (e.g. '\\.apk$')",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> None:
    """Parse args, build config, and run the upload engine."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load base config from file if provided
    base_config: UploadConfig | None = None
    if args.config:
        base_config = load_upload_config(Path(args.config))

    # Build CLI overrides dict
    cli_overrides: dict[str, object] = {
        "source_dir": args.source_dir,
        "target_url": args.target_url,
        "target_type": args.target_type,
        "target_subdir": args.target_subdir,
        "password": args.password,
        "retries": args.retries,
        "timeout": args.timeout,
        "log_level": args.log_level,
        "manifest_path": args.manifest_path,
        "file_filter": args.file_filter,
    }

    if args.index_only:
        cli_overrides["index_only"] = True

    # Merge config
    try:
        config = merge_upload_cli_args(base_config, cli_overrides)
    except ValueError as e:
        parser.error(str(e))

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Determine manifest path
    manifest_path = config.manifest_path
    if manifest_path is None:
        manifest_path = config.source_dir / DEFAULT_UPLOAD_MANIFEST_FILENAME

    # Create target and engine
    target = create_target(config)
    engine = UploadEngine(config, target, manifest_path)

    exit_code = engine.run()
    sys.exit(exit_code)
