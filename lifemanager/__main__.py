"""
Application entry point.
Run with:  python -m lifemanager
Or after install:  lifemanager
"""

from __future__ import annotations

from lifemanager.bootstrap import build_application


def main() -> None:
    build_application().run()


if __name__ == "__main__":
    main()
