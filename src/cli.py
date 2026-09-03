from __future__ import annotations

import argparse
import logging
from collections import Counter
from pathlib import Path

from .pipeline import run
from .sink import write_csv, write_sqlite


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract quotation lines for review.")
    parser.add_argument("--documents", type=Path, default=Path("documents"))
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    quotations = run(args.documents)
    write_csv(quotations, args.out / "extractions.csv")
    write_sqlite(quotations, args.out / "extractions.sqlite")

    counts = Counter(q.overall_confidence for q in quotations)
    flagged = sum(1 for q in quotations if q.review_flags)
    print(
        f"\n{len(quotations)} line items from "
        f"{len({q.source_document for q in quotations})} documents"
    )
    print(
        f"  confidence: {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low"
    )
    print(f"  {flagged} carry at least one review flag")
    print(f"  written to {args.out}/extractions.csv and extractions.sqlite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
