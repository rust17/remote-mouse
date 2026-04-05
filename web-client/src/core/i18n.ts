import { zh } from '../lang/zh';
import type { TranslationKeys } from '../lang/zh';
import { en } from '../lang/en';

type Language = 'zh' | 'en';

class I18nManager {
    private currentLang: Language = 'zh';
    private translations: Record<Language, TranslationKeys> = { zh, en };

    constructor() {
        const savedLang = localStorage.getItem('remote-mouse-lang') as Language;
        if (savedLang && (savedLang === 'zh' || savedLang === 'en')) {
            this.currentLang = savedLang;
        }
    }

    public setLanguage(lang: Language) {
        this.currentLang = lang;
        localStorage.setItem('remote-mouse-lang', lang);
        this.updateDOM();
    }

    public getLanguage(): Language {
        return this.currentLang;
    }

    public t<K1 extends keyof TranslationKeys, K2 extends keyof TranslationKeys[K1]>(
        key: `${K1}.${K2 & string}`
    ): string {
        const [k1, k2] = key.split('.') as [K1, K2 & string];
        return this.translations[this.currentLang][k1][k2] as unknown as string;
    }

    public updateDOM() {
        const elements = document.querySelectorAll('[data-i18n]');
        elements.forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                // @ts-ignore - simplified access
                const text = this.t(key as any);
                if (text) el.textContent = text;
            }
        });

        // Update titles if necessary
        const titles = document.querySelectorAll('[data-i18n-title]');
        titles.forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                // @ts-ignore
                const text = this.t(key as any);
                if (text) (el as HTMLElement).title = text;
            }
        });
    }
}

export const i18n = new I18nManager();
