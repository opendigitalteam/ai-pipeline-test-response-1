"""Routing and the run itself."""

from __future__ import annotations

import logging
from pathlib import Path

from .extract import documents, structured_json
from .models import Quotation
from .normalise import finalise

log = logging.getLogger(__name__)

ROUTES = {
    ".json": structured_json.extract,
    ".pdf": documents.extract_pdf,
    ".eml": documents.extract_email,
    ".png": documents.extract_image,
    ".jpg": documents.extract_image,
    ".jpeg": documents.extract_image,
}


def process(path: Path) -> list[Quotation]:
    handler = ROUTES.get(path.suffix.lower())
    if handler is None:
        log.warning("No handler for %s - skipped", path.name)
        return []

    try:
        extracted = handler(path)
    except Exception as error:  # noqa: BLE001
        # One unreadable document should not lose the other seven. The failure
        # becomes a row so it shows up in review rather than only in the log.
        log.exception("Extraction failed for %s", path.name)
        failed = Quotation(
            product_name="(extraction failed)",
            model_or_sku=None,
            price_per_unit=None,
            currency=None,
            source_document=path.name,
            extractor="none",
        )
        failed.mark("price_per_unit", "low", f"extraction raised: {error}")
        failed.flag("Extraction failed - needs manual entry")
        return [failed]

    return [finalise(q) for q in extracted]


def run(documents_dir: Path) -> list[Quotation]:
    paths = sorted(p for p in documents_dir.iterdir() if p.is_file())
    results: list[Quotation] = []
    for path in paths:
        log.info("Processing %s", path.name)
        results.extend(process(path))
    return results
