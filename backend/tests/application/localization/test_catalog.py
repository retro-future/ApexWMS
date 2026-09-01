from pathlib import Path

import pytest

from application.localization.catalog import MessageCatalog
from application.localization.locale import Locale


@pytest.fixture
def catalog(tmp_path: Path) -> MessageCatalog:
    (tmp_path / "en.toml").write_text(
        '[errors]\nboom = "Boom {name}"\n[documents]\ntitle = "Invoice"\n', "utf-8"
    )
    (tmp_path / "ru.toml").write_text(
        '[errors]\nboom = "Бум {name}"\n[documents]\n', "utf-8"
    )
    (tmp_path / "uz.toml").write_text("[errors]\n[documents]\n", "utf-8")
    return MessageCatalog(tmp_path)


def test_render_localized(catalog: MessageCatalog) -> None:
    assert catalog.render(Locale.RU, "errors", "boom", name="x") == "Бум x"


def test_falls_back_to_english(catalog: MessageCatalog) -> None:
    assert catalog.render(Locale.UZ, "errors", "boom", name="x") == "Boom x"


def test_missing_key_returns_none(catalog: MessageCatalog) -> None:
    assert catalog.render(Locale.EN, "errors", "nope") is None


def test_missing_placeholder_returns_template(catalog: MessageCatalog) -> None:
    assert catalog.render(Locale.EN, "errors", "boom") == "Boom {name}"


def test_packaged_catalog_loads_and_documents_keys_match_across_locales() -> None:
    cat = MessageCatalog()
    en_docs = cat.keys("documents")
    assert "invoice_title" in en_docs
    for locale in (Locale.RU, Locale.UZ):
        assert cat.locale_keys(locale, "documents") >= en_docs


def test_every_english_key_is_translated_in_ru_and_uz() -> None:
    cat = MessageCatalog()
    for table in ("errors", "documents"):
        english = cat.keys(table)
        for locale in (Locale.RU, Locale.UZ):
            missing = english - cat.locale_keys(locale, table)
            assert not missing, f"{locale.value} {table} missing: {sorted(missing)}"
