from domain.value_objects import SKU
from infrastructure.persistence.tenant.models import ProductModel
from infrastructure.phone_catalog import PHONES, PhoneSpec, sku_for


def test_catalog_is_non_empty_with_filled_fields() -> None:
    assert PHONES
    for spec in PHONES:
        assert spec.brand.strip()
        assert spec.model.strip()
        assert spec.storage_gb > 0


def test_every_sku_is_valid_and_within_limit() -> None:
    for spec in PHONES:
        sku = sku_for(spec)
        assert SKU.parse(sku).value == sku
        assert len(sku) <= SKU.MAX_LENGTH


def test_skus_are_unique() -> None:
    skus = [sku_for(spec) for spec in PHONES]
    assert len(skus) == len(set(skus))


def test_names_and_model_labels_fit_the_columns() -> None:
    name_limit = ProductModel.__table__.c.name.type.length
    model_limit = ProductModel.__table__.c.model.type.length
    for spec in PHONES:
        assert len(spec.name) <= name_limit
        assert len(spec.model_label) <= model_limit


def test_sku_for_sanitizes_disallowed_characters() -> None:
    assert sku_for(PhoneSpec("Realme", "12 Pro", 256)) == "REALME-12-PRO-256"
    assert sku_for(PhoneSpec("Realme", "12 Pro+", 256)) == "REALME-12-PRO-PLUS-256"
