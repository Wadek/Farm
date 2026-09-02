import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = json.loads((ROOT / "static" / "locales" / "en.json").read_text(encoding="utf-8"))
FI = json.loads((ROOT / "static" / "locales" / "fi.json").read_text(encoding="utf-8"))


def test_locale_catalogs_share_the_same_keys():
    assert set(EN) == set(FI)
    assert len(EN) >= 200


def test_finnish_catalog_is_not_english_echo():
    translated = [k for k, v in FI.items() if v != k]
    assert len(translated) > 150
    assert FI["This week's REKO"] == "Tämän viikon REKO-jako"
    assert FI["Search"] == "Haku"


def test_i18n_bootstrap_uses_i18next():
    boot = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")
    html = (ROOT / "static" / "square.html").read_text(encoding="utf-8")
    assert "i18n.init" in boot
    assert "/static/locales/fi.json" in boot
    assert "i18next@23" in html
