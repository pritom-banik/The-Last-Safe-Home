/** i18next setup (SPEC §10.8). Language comes from the URL, then localStorage, then English. */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { isLang, type Lang } from "../format";
import bn from "./bn.json";
import en from "./en.json";

const STORAGE_KEY = "lsh.lang";

export function storedLang(): Lang | null {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return isLang(v) ? v : null;
  } catch {
    return null;
  }
}

export function storeLang(lang: Lang): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* private mode / blocked storage: the URL still carries the language */
  }
}

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, bn: { translation: bn } },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

export function applyLang(lang: Lang): void {
  if (i18n.language !== lang) void i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
  storeLang(lang);
}

export default i18n;
