"""Adapters for the machine-readable supplier exports.

No model is called here. These files are already structured; the only problem
is that no two suppliers agree on field names. That is a mapping problem, and a
mapping written by hand is deterministic, free, instant, and can be tested.
Sending clean JSON to an LLM would buy nothing and cost accuracy.

The trade-off is that a new supplier export needs a new adapter. See the
write-up for why that is the right side of the trade at this document count and
what would change my mind.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Quotation

EXTRACTOR = "structured_json"


def detect(payload: dict) -> str | None:
    """Identify which supplier export this is from its own shape."""
    if payload.get("meta", {}).get("source_system") == "SanovaERP":
        return "sanova"
    if "catalogue" in payload and "products" in payload:
        return "ubuntu_health"
    if payload.get("document_type") == "supplier_quotation":
        return "zenith"
    return None


def extract(path: Path) -> list[Quotation]:
    payload = json.loads(path.read_text())
    supplier = detect(payload)
    if supplier is None:
        raise ValueError(f"No adapter for {path.name} - inspect and add one")
    return {
        "sanova": _sanova,
        "ubuntu_health": _ubuntu_health,
        "zenith": _zenith,
    }[supplier](payload, path.name)


def _zenith(payload: dict, source: str) -> list[Quotation]:
    terms = payload.get("commercial_terms", {})
    supplier = payload.get("supplier", {}).get("short_name")
    out = []
    for item in payload.get("line_items", []):
        q = Quotation(
            product_name=item["product_name"],
            model_or_sku=None,  # this export has no SKU, only a line number
            price_per_unit=item.get("price_per_uom"),
            currency=terms.get("currency"),
            source_document=source,
            supplier_name=supplier,
            inn=item.get("inn"),
            unit_of_measure=item.get("unit_of_measure"),
            units_per_pack=item.get("units_per_pack"),
            price_per_pack=item.get("price_per_pack"),
            price_basis="stated",
            extractor=EXTRACTOR,
            source_locator=f"line_items[{item.get('line_no')}]",
        )
        q.mark("price_per_unit", "high", "stated explicitly as price_per_uom")
        out.append(q)
    return out


def _sanova(payload: dict, source: str) -> list[Quotation]:
    offer = payload.get("offer", {})
    currency = offer.get("price_basis", {}).get("currency")
    supplier = payload.get("vendor", {}).get("name")
    out = []
    for index, product in enumerate(offer.get("products", [])):
        packaging = product.get("packaging", {})
        commercials = product.get("commercials", {})
        q = Quotation(
            product_name=product.get("trade_name"),
            model_or_sku=product.get("sku"),
            # This export says so itself in note_on_pricing: pack price only.
            price_per_unit=None,
            currency=currency,
            source_document=source,
            supplier_name=supplier,
            inn=", ".join(product.get("generic_name", [])) or None,
            unit_of_measure=packaging.get("unit_label"),
            units_per_pack=packaging.get("units_per_pack"),
            price_per_pack=commercials.get("price_per_pack"),
            extractor=EXTRACTOR,
            source_locator=f"offer.products[{index}]",
        )
        if packaging.get("pack_note"):
            # The TB kit is a course of treatment, not a bag of interchangeable
            # tablets, so a per-tablet price is arithmetically fine and
            # commercially meaningless. Say so rather than hide it.
            q.flag(
                f"Pack is a treatment course ({packaging['pack_note']}) - "
                "per-unit price may not be the right basis for comparison"
            )
        out.append(q)
    return out


def _ubuntu_health(payload: dict, source: str) -> list[Quotation]:
    catalogue = payload.get("catalogue", {})
    currency = catalogue.get("quotation_currency")
    supplier = catalogue.get("issuer")
    out = []
    for index, product in enumerate(payload.get("products", [])):
        pack = product.get("pack", {})
        tiers = sorted(product.get("price_tiers", []), key=lambda t: t.get("tier", 0))
        # A tiered list has no single price. Taking tier 1 is the defensible
        # default because it is the price at the lowest committed volume, i.e.
        # the one a buyer is certain to be able to get. The alternatives are
        # recorded so a reviewer can see what was left on the table.
        first = tiers[0] if tiers else {}
        q = Quotation(
            product_name=product.get("product_name"),
            model_or_sku=product.get("item_code"),
            price_per_unit=None,
            currency=currency,
            source_document=source,
            supplier_name=supplier,
            inn=product.get("inn"),
            unit_of_measure=product.get("unit_of_measure"),
            units_per_pack=pack.get("units_per_pack"),
            price_per_pack=first.get("price_per_pack"),
            extractor=EXTRACTOR,
            source_locator=f"products[{index}].price_tiers[tier={first.get('tier')}]",
        )
        if len(tiers) > 1:
            spread = ", ".join(
                f"tier {t['tier']}: {t['price_per_pack']} from {t['min_packs']} packs"
                for t in tiers
            )
            q.mark(
                "price_per_unit",
                "medium",
                f"volume-tiered price, tier 1 taken ({spread})",
            )
            q.flag("Tiered pricing - confirm the volume band before comparing")
        if catalogue.get("price_note"):
            q.flag(f"Catalogue note: {catalogue['price_note']}")
        out.append(q)
    return out
