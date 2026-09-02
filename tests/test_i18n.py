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
    assert FI["Order"] == "Tilaa"
    assert FI["Confirm this week's REKO"] == "Vahvista tämän viikon REKO-jako"
    assert FI["When will you pick up?"] == "Milloin haet?"
    assert FI["Raw milk"] == "Raakamaito"
    assert FI["Raspberries"] == "Vadelmat"
    assert FI["Lehtikaali (kale)"] == "Lehtikaali"
    assert FI["Haskap (hunajamarja)"] == "Hunajamarja"
    assert EN["Tinkimaito"] == "Farm milk"
    assert EN["Tyrni"] == "Sea buckthorn"
    assert EN["Lehtikaali (kale)"] == "Kale"
    assert FI["I'll be there"] == "Tulen"
    assert FI["Not this week"] == "En tällä viikolla"
    assert FI["This is my farm"] == "Tämä on minun tilani"
    assert FI["Create a farmer account, then you can claim this farm."] == "Luo viljelijätili, niin voit lunastaa tämän tilan."
    assert FI["Farm claim"] == "Tilan lunastus"
    assert FI["Farms"] == "Tilat"
    assert FI["Remove"] == "Poista"
    assert FI["Removed"] == "Poistettu"
    assert FI["Approve or decline this claim."] == "Hyväksy tai hylkää tämä lunastus."
    assert FI["Item not found, add a new item"] == "Tuotetta ei löydy, lisää uusi"
    assert FI["Pick an item, or add a new one."] == "Valitse tuote listasta tai lisää uusi."


def test_i18n_bootstrap_uses_i18next():
    boot = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")
    html = (ROOT / "static" / "square.html").read_text(encoding="utf-8")
    assert "/static/locales/fi.json" in boot
    assert "/static/vendor/i18next.min.js" in html
    assert 'id="view-browse"' in html
    assert 'id="view-home"' in html
    assert 'return me ? "browse" : "home"' in html
    assert 't("Satokori")' in html
    assert '["reko", t("REKO")' not in html
    assert "function catalogRings" in html
    assert "filterRing" in html
    assert 'data-ring="all"' in html
    assert 'data-ring="saved"' in html
    assert "drop-banner" not in html
    assert "farmgate" not in html
    assert "data-demo-email" not in html
    assert "data-demo-password" not in html
    assert "paintOpenFarms" not in html
    assert 'id="claim-open"' not in html
    assert 'id="guest-settings"' in html
    assert 'id="settings-btn"' in html
    assert 'id="brand"' in html
    assert 'id="loc-btn"' not in html
    assert "Hyvinkää<small>80 km</small>" not in html
    assert 'id="theme-btn"' not in html
    assert 'id="lang-switch"' not in html
    assert "function applyPickedTheme" in html
    assert 'id="sheet-x"' in html
    assert "function bindSheetDismiss" in html
    assert 'html lang="fi"' in html
    assert 'filterRing === "saved"' in html
    assert "function produceSrc" in html
    assert "const PRODUCE_CATALOG" in html
    assert "function filterProduceSet" in html
    assert "function showAccountForClaim" in html
    assert "sk_claim_farm" in html
    assert "farm_claim" in html
    assert '["farms", t("Farms"), "farm"]' in html
    assert "function liveGoods" in html
    assert "function produceLabel" in boot
    assert "produceLabel(item.produce_name)" in html
    assert "openSettings" in html
