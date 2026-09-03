"""Unit-price derivation and the sanity checks that go with it.

Deliberately not an LLM job. Dividing a pack price by a pack size is arithmetic,
and arithmetic done by a language model is arithmetic you have to check. Every
extractor hands its numbers here so the derivation rules live in one place and
are covered by tests.
"""

from __future__ import annotations

from .models import Quotation

# Below this, a "unit price" is more likely a units-per-pack mix-up than a
# genuinely cheap tablet. Paracetamol at fractions of a cent is real, so this is
# set low enough to only catch obvious nonsense.
IMPLAUSIBLY_CHEAP = 0.0005
IMPLAUSIBLY_EXPENSIVE = 10_000.0


def derive_unit_price(quotation: Quotation) -> Quotation:
    """Fill in price_per_unit from pack price and pack size where it is missing.

    Leaves a stated unit price alone but cross-checks it against the pack price
    when both are present, because a disagreement there is a genuine finding
    rather than a rounding artefact.
    """
    if quotation.price_per_unit is None:
        if quotation.price_per_pack is None or not quotation.units_per_pack:
            quotation.mark(
                "price_per_unit", "low", "no unit price and no pack size to derive from"
            )
            quotation.flag("Unit price could not be established")
            return quotation

        quotation.price_per_unit = round(
            quotation.price_per_pack / quotation.units_per_pack, 6
        )
        quotation.price_basis = "derived"
        quotation.derivation_note = (
            f"{quotation.price_per_pack} per pack / {quotation.units_per_pack} "
            f"{quotation.unit_of_measure or 'units'} per pack"
        )
        quotation.mark(
            "price_per_unit", "medium", "derived from pack price, not stated in source"
        )
        return quotation

    if quotation.price_per_pack and quotation.units_per_pack:
        implied = quotation.price_per_pack / quotation.units_per_pack
        # 2% covers the supplier having rounded their own pack price for display.
        if abs(implied - quotation.price_per_unit) > max(implied * 0.02, 1e-6):
            quotation.mark(
                "price_per_unit",
                "medium",
                f"stated unit price disagrees with pack price / pack size ({implied:.6f})",
            )
            quotation.flag(
                "Stated unit price and pack price are inconsistent - check which governs"
            )

    return quotation


def sanity_check(quotation: Quotation) -> Quotation:
    price = quotation.price_per_unit
    if price is None:
        return quotation

    if price <= 0:
        quotation.mark("price_per_unit", "low", "non-positive price")
        quotation.flag("Non-positive unit price")
    elif price < IMPLAUSIBLY_CHEAP:
        quotation.mark("price_per_unit", "low", f"implausibly low unit price ({price})")
        quotation.flag("Unit price below plausible floor - check pack size")
    elif price > IMPLAUSIBLY_EXPENSIVE:
        quotation.mark("price_per_unit", "low", f"implausibly high unit price ({price})")
        quotation.flag("Unit price above plausible ceiling - check currency and pack size")

    if not quotation.currency:
        quotation.mark("currency", "low", "no currency found on the document")
        quotation.flag("Currency missing - price is not comparable without it")

    if not quotation.model_or_sku:
        quotation.mark(
            "model_or_sku",
            "medium",
            "no SKU or item code in source",
            escalate=False,
        )

    return quotation


def finalise(quotation: Quotation) -> Quotation:
    return sanity_check(derive_unit_price(quotation))
