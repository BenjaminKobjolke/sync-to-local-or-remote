"""sync-to-local: Sync files between remote sources and local folders."""

__version__ = "0.2.0"


def main() -> None:
    """Entry point for the sync-to-local CLI."""
    from sync_to_local.cli import run

    run()


def main_upload() -> None:
    """Entry point for the sync-to-remote CLI."""
    from sync_to_local.upload_cli import run

    run()
