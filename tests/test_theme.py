from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "square.html").read_text(encoding="utf-8")
I18N = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")


def test_dark_and_light_tokens_are_real_themes():
    assert "color-scheme: light" in CSS
    assert "color-scheme: dark" in CSS
    assert 'html[data-theme="dark"]' in CSS
    assert "--paper:" in CSS
    assert "--chip-on:" in CSS
    assert CSS.count("--bg:") >= 2
    dark = CSS.split('html[data-theme="dark"]', 1)[1]
    assert "--bg: #0e1511" in dark
    assert "--paper: #121a16" in dark
    assert "background: var(--paper)" in CSS
    assert ".tile-hero" in CSS
    hero = CSS.split(".tile-hero", 1)[1].split("}", 1)[0]
    assert "var(--paper)" in hero
    assert "#ece6d8" not in hero


def test_theme_toggle_wires_header_and_settings():
    assert 'id="theme-btn"' in HTML
    assert "function applyPickedTheme" in HTML
    assert "applyPickedTheme(getTheme()" in HTML
    assert "setTheme(name)" in HTML
    assert 'setAttribute("data-theme"' in I18N
    assert "theme-color" in I18N
    assert "colorScheme" in I18N
    assert 'THEME_KEY = "sk_theme"' in I18N


def test_theme_assets_are_served(client):
    css = client.get("/static/css/app.css")
    assert css.status_code == 200
    assert b"html[data-theme=\"dark\"]" in css.content
    assert b"color-scheme: dark" in css.content
    page = client.get("/")
    assert 'id="theme-btn"' in page.text
    js = client.get("/static/i18n.js")
    assert js.status_code == 200
    assert b"applyTheme" in js.content
    assert b"theme-color" in js.content
