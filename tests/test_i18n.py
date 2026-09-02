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
    assert FI["Satokori"] == "Satokori"
    assert FI["REKO"] == "REKO"
    assert FI["Try another REKO location."] == "Kokeile toista REKO-paikkaa."
    assert FI["All"] == "Kaikki"
    assert FI["Meat"] == "Liha"
    assert FI["Greens"] == "Vihreät"


def test_i18n_bootstrap_uses_i18next():
    boot = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")
    html = (ROOT / "static" / "square.html").read_text(encoding="utf-8")
    assert "/static/locales/fi.json" in boot
    assert "/static/vendor/i18next.min.js" in html
    assert 'id="view-browse"' in html
    assert 't("Satokori")' in html
    assert '["reko", t("REKO")' not in html
    assert 'filterCat === "reko"' in html
    assert "filterReko" in html
    assert '["all","reko","greens","root"' in html
    assert "drop-banner" not in html
    assert "farmgate" not in html
    assert "data-demo-email" not in html
    assert "data-demo-password" not in html
    assert "paintOpenFarms" not in html
    assert 'id="claim-open"' not in html
    assert 'id="guest-settings"' in html
    assert 'id="settings-btn"' in html
    assert 'id="theme-btn"' in html
    assert "function applyPickedTheme" in html
    assert 'list.push("saved")' in html
    assert "function produceSrc" in html
    assert "openSettings" in html
