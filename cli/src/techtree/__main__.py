"""Support ``python -m techtree``. Spec section 10.2."""

from __future__ import annotations

from techtree.cli.app import main as cli_main


def main() -> None:
    """Invoke the Techtree CLI entry point."""
    cli_main()


if __name__ == "__main__":
    main()
