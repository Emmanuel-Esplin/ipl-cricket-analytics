"""Command line: `python -m ingestion.run [--archive path.zip] [--refresh]`."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ingestion.cricsheet import ingest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use a downloaded zip instead of fetching.")
    parser.add_argument("--refresh", action="store_true", help="Rewrite every match.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    archive = args.archive.read_bytes() if args.archive else None
    print(ingest(archive, args.refresh))


if __name__ == "__main__":
    main()
