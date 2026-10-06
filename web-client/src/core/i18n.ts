import { readPreference, writePreference } from './preferences';
import { zh } from '../lang/zh';
import type { TranslationKeys } from '../lang/zh';
import { en } from '../lang/en';

type Language = 'zh' | 'en';
type TranslationKey = {
    [Group in keyof TranslationKeys]: `${Group}.${keyof TranslationKeys[Group] & string}`
}[keyof TranslationKeys];

class I18nManager {
    private currentLang: Language = 'zh';
    private translations: Record<Language, TranslationKeys> = { zh, en };

    constructor() {
        const savedLang = readPreference('remote-mouse-lang') as Language;
        if (savedLang && (savedLang === 'zh' || savedLang === 'en')) {
            this.currentLang = savedLang;
        }
    }

    public setLanguage(lang: Language) {
        this.currentLang = lang;
        writePreference('remote-mouse-lang', lang);
        this.updateDOM();
    }

    public getLanguage(): Language {
        return this.currentLang;
    }

    public t(key: TranslationKey): string {
        const [group, name] = key.split('.');
        const translations = this.translations[this.currentLang] as Record<string, Record<string, string>>;
        return translations[group]?.[name] ?? key;
    }

    public updateDOM() {
        document.documentElement.lang = this.currentLang === 'zh' ? 'zh-CN' : 'en';
        const elements = document.querySelectorAll('[data-i18n]');
        elements.forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                const text = this.t(key as TranslationKey);
                if (text) el.textContent = text;
            }
        });

        // Update titles if necessary
        const titles = document.querySelectorAll('[data-i18n-title]');
        titles.forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                const text = this.t(key as TranslationKey);
                if (text) (el as HTMLElement).title = text;
            }
        });
        document.querySelectorAll('[data-i18n-aria]').forEach(el => {
            const key = el.getAttribute('data-i18n-aria');
            if (key) el.setAttribute('aria-label', this.t(key as TranslationKey));
        });
    }
}

export const i18n = new I18nManager();
