from pathlib import Path

import pytest

from src.extract.structured_json import extract
from src.normalise import finalise

DOCUMENTS = Path(__file__).parent.parent / "documents"


def by_name(quotations, name):
    return next(q for q in quotations if q.product_name == name)


def test_zenith_uses_the_stated_unit_price():
    quotations = [finalise(q) for q in extract(DOCUMENTS / "zenith_pharma_quotation_ZPL-Q-2026-4471.json")]
    assert len(quotations) == 4
    zenamox = by_name(quotations, "Zenamox 500/125")
    assert zenamox.price_per_unit == 0.0642
    assert zenamox.currency == "USD"
    assert zenamox.price_basis == "stated"


def test_sanova_derives_because_the_export_says_it_has_no_unit_price():
    quotations = [finalise(q) for q in extract(DOCUMENTS / "sanova_offer_export_2026-08-03.json")]
    tld = by_name(quotations, "Sanotri-TLD")
    assert tld.price_per_unit == 0.035  # 3.15 / 90
    assert tld.price_basis == "derived"
    assert tld.currency == "EUR"


def test_sanova_flags_the_treatment_course_pack():
    quotations = [finalise(q) for q in extract(DOCUMENTS / "sanova_offer_export_2026-08-03.json")]
    kit = by_name(quotations, "Sanofour Kit")
    assert any("treatment course" in flag for flag in kit.review_flags)


def test_ubuntu_takes_tier_one_and_says_so():
    quotations = [finalise(q) for q in extract(DOCUMENTS / "ubuntu_health_price_list_Q3-2026.json")]
    panadel = by_name(quotations, "Panadel 500")
    assert panadel.price_per_pack == 41.5  # tier 1, not the cheapest tier
    assert panadel.price_per_unit == 0.0415
    assert panadel.currency == "ZAR"
    assert any("Tiered pricing" in flag for flag in panadel.review_flags)


def test_unknown_export_shape_raises_rather_than_returning_nothing(tmp_path):
    # A new supplier export must fail loudly. Returning an empty list here would
    # silently drop a whole document from the review table.
    unknown = tmp_path / "acme_export.json"
    unknown.write_text('{"some_other_shape": {"items": []}}')
    with pytest.raises(ValueError):
        extract(unknown)
