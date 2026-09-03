"""Text-bearing and image documents: PDF, email, scans.

Each of these gets the document to the model in the form that loses the least.
The shared post-processing lives in `_to_quotations` so the three paths differ
only where they genuinely differ.
"""

from __future__ import annotations

import base64
import email
import email.policy
from pathlib import Path

import pdfplumber

from ..models import Confidence, Quotation
from . import llm


def _to_quotations(
    result: dict, source: str, extractor: str, floor: Confidence | None = None
) -> list[Quotation]:
    """Turn a model response into Quotations, honouring its own confidence.

    `floor` caps confidence for sources that cannot be trusted above a level
    however sure the model sounds. A model reading a glared photograph will
    happily report high confidence, and it should not be believed.
    """
    order = {"high": 0, "medium": 1, "low": 2}
    out = []
    for item in result.get("line_items", []):
        reported: Confidence = item.get("confidence", "medium")
        if floor and order[reported] < order[floor]:
            reported = floor

        q = Quotation(
            product_name=item.get("product_name") or "(unnamed)",
            model_or_sku=item.get("model_or_sku"),
            price_per_unit=item.get("price_per_unit"),
            currency=item.get("currency") or result.get("currency"),
            source_document=source,
            supplier_name=result.get("supplier_name"),
            inn=item.get("inn"),
            unit_of_measure=item.get("unit_of_measure"),
            units_per_pack=item.get("units_per_pack"),
            price_per_pack=item.get("price_per_pack"),
            price_basis="inferred" if floor == "low" else "stated",
            extractor=extractor,
            source_locator=item.get("source_locator"),
        )
        q.mark("price_per_unit", reported, item.get("notes") or "model-reported")
        if item.get("notes"):
            q.flag(item["notes"])
        if not item.get("product_name"):
            q.flag("Product name not readable")
        out.append(q)
    return out


def extract_pdf(path: Path) -> list[Quotation]:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n\n".join(f"--- page {i + 1} ---\n{p}" for i, p in enumerate(pages))

    if not text.strip():
        # A PDF with no text layer is a scan wearing a PDF costume. Rather than
        # return nothing, say so loudly - rasterising and going through the
        # vision path would be the fix, and is noted in the write-up.
        q = Quotation(
            product_name="(no text layer)",
            model_or_sku=None,
            price_per_unit=None,
            currency=None,
            source_document=path.name,
            extractor="pdf",
        )
        q.mark("price_per_unit", "low", "PDF has no extractable text layer")
        q.flag("PDF appears to be a scan - not processed")
        return [q]

    return _to_quotations(llm.extract_from_text(text, path.name), path.name, "pdf")


def extract_email(path: Path) -> list[Quotation]:
    message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)

    # Prefer text/plain. The HTML alternative of this thread carries the same
    # figures, and passing both invites the model to reconcile two copies of the
    # same thing rather than read one carefully.
    body = message.get_body(preferencelist=("plain",))
    if body is None:
        body = message.get_body(preferencelist=("html",))
    content = body.get_content() if body else ""

    header = (
        f"From: {message.get('From')}\n"
        f"Subject: {message.get('Subject')}\n"
        f"Date: {message.get('Date')}\n\n"
    )

    # Prices in prose get revised later in a thread. The prompt tells the model
    # that a later figure supersedes an earlier one and to record the
    # superseded value in notes, which is where the correction handling lives.
    return _to_quotations(
        llm.extract_from_text(header + content, path.name), path.name, "email"
    )


def extract_image(path: Path) -> list[Quotation]:
    encoded = base64.b64encode(path.read_bytes()).decode()
    return _to_quotations(
        llm.extract_from_image(encoded, path.name),
        path.name,
        "image",
    )
