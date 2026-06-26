import { useTranslation } from "react-i18next";
import { setLang } from "../i18n";

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const lang = i18n.language;

  return (
    <div className="flex items-center gap-1 text-xs font-medium">
      <button
        onClick={() => setLang("ru")}
        className={lang === "ru" ? "text-gray-800" : "text-gray-400 hover:text-gray-600"}
      >
        RU
      </button>
      <span className="text-gray-300">/</span>
      <button
        onClick={() => setLang("en")}
        className={lang === "en" ? "text-gray-800" : "text-gray-400 hover:text-gray-600"}
      >
        EN
      </button>
    </div>
  );
}
