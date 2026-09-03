"""Writing the review table.

Both outputs are written from the same rows. CSV because a reviewer will open
it in a spreadsheet, SQLite because the moment there is a second run someone
will want to diff them.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .models import CSV_COLUMNS, Quotation


def write_csv(quotations: list[Quotation], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for quotation in quotations:
            writer.writerow(quotation.to_row())


def write_sqlite(quotations: list[Quotation], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    columns = ", ".join(f"{name} TEXT" for name in CSV_COLUMNS)
    connection.execute("DROP VIEW IF EXISTS needs_review")
    connection.execute("DROP TABLE IF EXISTS quotations")
    connection.execute(f"CREATE TABLE quotations (id INTEGER PRIMARY KEY, {columns})")
    connection.executemany(
        f"INSERT INTO quotations ({', '.join(CSV_COLUMNS)}) "
        f"VALUES ({', '.join('?' for _ in CSV_COLUMNS)})",
        [
            tuple(str(q.to_row().get(c, "")) for c in CSV_COLUMNS)
            for q in quotations
        ],
    )
    # The review queue is the point of the whole thing, so it gets a view.
    connection.execute(
        "CREATE VIEW needs_review AS SELECT * FROM quotations "
        "WHERE overall_confidence != 'high' OR review_flags != ''"
    )
    connection.commit()
    connection.close()
