"""sync-to-local: Sync files from remote sources to local folders."""

__version__ = "0.1.0"


def main() -> None:
    """Entry point for the sync-to-local CLI."""
    from sync_to_local.cli import run

    run()
