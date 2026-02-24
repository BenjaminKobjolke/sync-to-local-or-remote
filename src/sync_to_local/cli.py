"""CLI argument parsing for sync-to-local."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from sync_to_local.config import SyncConfig, load_config, merge_cli_args
from sync_to_local.constants import DEFAULT_MANIFEST_FILENAME
from sync_to_local.sources import create_source
from sync_to_local.sync_engine import SyncEngine


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="sync-to-local",
        description="Sync files from remote sources to local folders",
    )
    parser.add_argument("--source-url", default=None, help="Remote source URL")
    parser.add_argument("--target-dir", default=None, help="Local target directory")
    parser.add_argument("--source-type", default=None, help="Source type (default: nextcloud)")
    parser.add_argument("--source-subdir", default=None, help="Subdirectory on source")
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
        help="List remote files and write manifest without downloading",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> None:
    """Parse args, build config, and run the sync engine."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load base config from file if provided
    base_config: SyncConfig | None = None
    if args.config:
        base_config = load_config(Path(args.config))

    # Build CLI overrides dict
    cli_overrides: dict[str, object] = {
        "source_url": args.source_url,
        "target_dir": args.target_dir,
        "source_type": args.source_type,
        "source_subdir": args.source_subdir,
        "password": args.password,
        "retries": args.retries,
        "timeout": args.timeout,
        "log_level": args.log_level,
        "manifest_path": args.manifest_path,
    }

    if args.index_only:
        cli_overrides["index_only"] = True

    # Merge config
    try:
        config = merge_cli_args(base_config, cli_overrides)
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
        manifest_path = config.target_dir / DEFAULT_MANIFEST_FILENAME

    # Create source and engine
    source = create_source(config)
    engine = SyncEngine(config, source, manifest_path)

    exit_code = engine.run()
    sys.exit(exit_code)
