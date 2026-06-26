import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const LANG_KEY = "sb_lang";

// Все locales/<lang>/<namespace>.json подхватываются автоматически — новый
// namespace-файл не требует правки этого файла.
const modules = import.meta.glob<{ default: Record<string, string> }>(
  "./locales/*/*.json",
  { eager: true },
);

const resources: Record<string, Record<string, Record<string, string>>> = {};
for (const path in modules) {
  const match = path.match(/\.\/locales\/([^/]+)\/([^/]+)\.json$/);
  if (!match) continue;
  const [, lang, ns] = match;
  resources[lang] ??= {};
  resources[lang][ns] = modules[path].default;
}

export function getStoredLang(): string {
  return localStorage.getItem(LANG_KEY) || "ru";
}

export function setLang(lang: string): void {
  localStorage.setItem(LANG_KEY, lang);
  i18n.changeLanguage(lang);
}

i18n.use(initReactI18next).init({
  resources,
  lng: getStoredLang(),
  fallbackLng: "ru",
  ns: Object.keys(resources.ru || {}),
  defaultNS: "common",
  interpolation: { escapeValue: false },
});

export default i18n;
