from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from bugdoctor.app import run_app


def main() -> None:
    parser = argparse.ArgumentParser(description="BugDoctor")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional config.yaml path",
    )
    args = parser.parse_args()
    asyncio.run(run_app(args.config))


if __name__ == "__main__":
    main()
