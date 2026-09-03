from src.models import Quotation
from src.normalise import derive_unit_price, finalise, sanity_check


def quotation(**overrides) -> Quotation:
    base = dict(
        product_name="Test",
        model_or_sku="SKU-1",
        price_per_unit=None,
        currency="USD",
        source_document="test.json",
    )
    base.update(overrides)
    return Quotation(**base)


def test_derives_unit_price_from_pack():
    q = derive_unit_price(quotation(price_per_pack=3.15, units_per_pack=90))
    assert q.price_per_unit == 0.035
    assert q.price_basis == "derived"
    # A derived price is never high confidence: the pack size is an assumption
    # about what the supplier meant by "pack".
    assert q.overall_confidence == "medium"


def test_stated_price_is_left_alone():
    q = derive_unit_price(quotation(price_per_unit=0.0642, price_per_pack=0.899, units_per_pack=14))
    assert q.price_per_unit == 0.0642
    assert q.price_basis == "stated"
    assert q.review_flags == []


def test_flags_disagreement_between_stated_and_pack_price():
    # 1.430 / 20 = 0.0715, so a stated 0.09 is a real inconsistency.
    q = derive_unit_price(quotation(price_per_unit=0.09, price_per_pack=1.430, units_per_pack=20))
    assert q.overall_confidence == "medium"
    assert any("inconsistent" in flag for flag in q.review_flags)


def test_missing_pack_size_is_flagged_not_guessed():
    q = derive_unit_price(quotation(price_per_pack=1.55, units_per_pack=None))
    assert q.price_per_unit is None
    assert q.overall_confidence == "low"


def test_implausibly_low_price_is_flagged():
    q = sanity_check(quotation(price_per_unit=0.00001))
    assert q.overall_confidence == "low"
    assert any("plausible floor" in flag for flag in q.review_flags)


def test_missing_currency_is_flagged():
    q = finalise(quotation(price_per_unit=0.5, currency=None))
    assert q.overall_confidence == "low"
    assert any("Currency missing" in flag for flag in q.review_flags)
