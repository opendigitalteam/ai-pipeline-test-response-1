"""Core data shapes.

The target schema in the brief is a starting point. Two things are added to it:
a `unit_basis` block, because most of these documents do not state a unit price
directly and the derivation matters more than the number, and a `confidence`
block, because a reviewer needs to know which fields to look at twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional

# How a unit price came to exist. Reviewers treat these very differently:
# "stated" needs a spot check at most, "derived" needs the pack size checking,
# "inferred" means a model read it off a bad scan and should be checked properly.
PriceBasis = Literal["stated", "derived", "inferred"]

Confidence = Literal["high", "medium", "low"]


@dataclass
class FieldConfidence:
    """Per-field confidence plus the reason, so a reviewer sees *why*."""

    field_name: str
    confidence: Confidence
    reason: str


@dataclass
class Quotation:
    # --- target schema ---
    product_name: str
    model_or_sku: Optional[str]
    price_per_unit: Optional[float]
    currency: Optional[str]
    source_document: str

    # --- additions, see module docstring ---
    supplier_name: Optional[str] = None
    inn: Optional[str] = None
    unit_of_measure: Optional[str] = None
    units_per_pack: Optional[int] = None
    price_per_pack: Optional[float] = None
    price_basis: PriceBasis = "stated"
    derivation_note: Optional[str] = None

    overall_confidence: Confidence = "high"
    field_confidence: list[FieldConfidence] = field(default_factory=list)
    review_flags: list[str] = field(default_factory=list)

    # Provenance. `source_locator` is deliberately free-form: a JSON pointer for
    # exports, a line number for email, a page for PDFs. A reviewer needs to be
    # able to find the number again, and the useful form of that differs.
    extractor: str = ""
    source_locator: Optional[str] = None

    def flag(self, message: str) -> None:
        if message not in self.review_flags:
            self.review_flags.append(message)

    def mark(
        self,
        field_name: str,
        confidence: Confidence,
        reason: str,
        escalate: bool = True,
    ) -> None:
        """Record confidence in one field.

        `escalate=False` records the doubt without dragging the record's overall
        confidence down. Overall confidence is a claim about whether the *price*
        can be trusted, so a missing SKU belongs on the row but should not push
        a cleanly stated price into the review queue.
        """
        self.field_confidence.append(FieldConfidence(field_name, confidence, reason))
        order = {"high": 0, "medium": 1, "low": 2}
        if escalate and order[confidence] > order[self.overall_confidence]:
            self.overall_confidence = confidence

    def to_row(self) -> dict:
        row = asdict(self)
        row["field_confidence"] = "; ".join(
            f"{fc.field_name}={fc.confidence} ({fc.reason})"
            for fc in self.field_confidence
        )
        row["review_flags"] = " | ".join(self.review_flags)
        return row


CSV_COLUMNS = [
    "source_document",
    "supplier_name",
    "product_name",
    "model_or_sku",
    "inn",
    "price_per_unit",
    "currency",
    "unit_of_measure",
    "units_per_pack",
    "price_per_pack",
    "price_basis",
    "derivation_note",
    "overall_confidence",
    "field_confidence",
    "review_flags",
    "extractor",
    "source_locator",
]
