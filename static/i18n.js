/* i18next catalogs: /static/locales/{en,fi}.json. Saved lang wins, else fi if the phone is Finnish. */
(function (global) {
  const KEY = "sk_lang";
  let lang = "en";

  function detect() {
    const saved = localStorage.getItem(KEY);
    if (saved === "fi" || saved === "en") return saved;
    const nav = String(navigator.language || navigator.userLanguage || "").toLowerCase();
    return nav.startsWith("fi") ? "fi" : "en";
  }

  function t(key, ...args) {
    if (key == null || key === "") return "";
    if (!global.i18next) return String(key);
    const opts = {};
    args.forEach((v, i) => { opts[String(i)] = v; });
    return global.i18next.t(String(key), Object.assign({ defaultValue: String(key) }, opts));
  }

  function setLang(next) {
    lang = next === "fi" ? "fi" : "en";
    localStorage.setItem(KEY, lang);
    document.documentElement.lang = lang;
    if (global.i18next) global.i18next.changeLanguage(lang);
    return lang;
  }

  function getLang() { return lang; }
  function dateLocale() { return lang === "fi" ? "fi-FI" : "en-GB"; }

  lang = detect();
  document.documentElement.lang = lang;

  global.t = t;
  global.setLang = setLang;
  global.getLang = getLang;
  global.dateLocale = dateLocale;
  global.i18nReady = (async function () {
    const i18n = global.i18next;
    if (!i18n) throw new Error("i18next failed to load");
    const [en, fi] = await Promise.all([
      fetch("/static/locales/en.json").then((r) => r.json()),
      fetch("/static/locales/fi.json").then((r) => r.json()),
    ]);
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
    return lang;
  })();
})(window);
