/* Locale catalogs in /static/locales/{en,fi}.json. i18next is optional (vendored).
   Finnish must work even if the library file fails to load. */
(function (global) {
  const KEY = "sk_lang";
  const THEME_KEY = "sk_theme";
  let lang = "fi";
  let packs = { en: {}, fi: {} };

  function detect() {
    const saved = localStorage.getItem(KEY);
    if (saved === "en") return "en";
    return "fi";
  }

  function detectTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "light") return saved;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(name) {
    const theme = name === "dark" ? "dark" : "light";
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.style.colorScheme = theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch (_) {}
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0e1511" : "#f6f3ec");
    return theme;
  }

  function tIn(which, key, ...args) {
    if (key == null || key === "") return "";
    const k = String(key);
    const pack = packs[which] || {};
    let v = pack[k];
    if (v == null || v === "") v = (packs.en || {})[k];
    if (v == null || v === "") v = k;
    for (let i = 0; i < args.length; i++) v = String(v).split("{" + i + "}").join(args[i]);
    return v;
  }
  function t(key, ...args) {
    return tIn(lang, key, ...args);
  }
  function produceLabel(name) {
    const raw = String(name == null ? "" : name).trim();
    if (!raw) return "";
    return t(raw);
  }

  function setLang(next) {
    lang = next === "fi" ? "fi" : "en";
    localStorage.setItem(KEY, lang);
    document.documentElement.lang = lang;
    if (global.i18next && global.i18next.changeLanguage) global.i18next.changeLanguage(lang);
    return lang;
  }

  function getLang() { return lang; }
  function dateLocale() { return lang === "fi" ? "fi-FI" : "en-GB"; }
  function getTheme() { return document.documentElement.getAttribute("data-theme") || "light"; }

  lang = detect();
  document.documentElement.lang = lang;
  applyTheme(detectTheme());

  global.t = t;
  global.tIn = tIn;
  global.produceLabel = produceLabel;
  global.setLang = setLang;
  global.getLang = getLang;
  global.dateLocale = dateLocale;
  global.getTheme = getTheme;
  global.setTheme = applyTheme;
  global.i18nReady = (async function () {
    const [en, fi] = await Promise.all([
      fetch("/static/locales/en.json").then((r) => r.json()),
      fetch("/static/locales/fi.json").then((r) => r.json()),
    ]);
    packs.en = en;
    packs.fi = fi;
    const i18n = global.i18next;
    if (i18n && i18n.init) {
      await i18n.init({
        lng: lang,
        fallbackLng: "en",
        resources: {
          en: { translation: en },
          fi: { translation: fi },
        },
        interpolation: { escapeValue: false, prefix: "{", suffix: "}" },
        returnNull: false,
        keySeparator: false,
        nsSeparator: false,
      });
    }
    return lang;
  })();
})(window);
