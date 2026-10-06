import { readPreference, writePreference } from '../core/preferences';
import { i18n } from '../core/i18n';

export class SettingsManager {
    private modal: HTMLElement;
    private openBtn: HTMLElement;
    private closeBtn: HTMLElement;
    private sensitivitySlider: HTMLInputElement;
    private sensitivityLabel: HTMLElement;
    private scrollSensitivitySlider: HTMLInputElement;
    private scrollSensitivityLabel: HTMLElement;
    private themeToggle: HTMLInputElement;
    private scrollPosToggle: HTMLInputElement;
    private rateMonitorToggle: HTMLInputElement;
    private langSelect: HTMLSelectElement;

    private onSensitivityChange: (val: number) => void;
    private onScrollSensitivityChange: (val: number) => void;
    private onRateMonitorChange: (enabled: boolean) => void;
    private lifecycle: { onOpen?: () => void; onClose?: () => void };

    constructor(
        modal: HTMLElement,
        openBtn: HTMLElement,
        closeBtn: HTMLElement,
        slider: HTMLInputElement,
        label: HTMLElement,
        scrollSlider: HTMLInputElement,
        scrollLabel: HTMLElement,
        themeToggle: HTMLInputElement,
        scrollPosToggle: HTMLInputElement,
        rateMonitorToggle: HTMLInputElement,
        langSelect: HTMLSelectElement,
        onSensitivityChange: (val: number) => void,
        onScrollSensitivityChange: (val: number) => void,
        onRateMonitorChange: (enabled: boolean) => void,
        lifecycle: { onOpen?: () => void; onClose?: () => void } = {}
    ) {
        this.modal = modal;
        this.openBtn = openBtn;
        this.closeBtn = closeBtn;
        this.sensitivitySlider = slider;
        this.sensitivityLabel = label;
        this.scrollSensitivitySlider = scrollSlider;
        this.scrollSensitivityLabel = scrollLabel;
        this.themeToggle = themeToggle;
        this.scrollPosToggle = scrollPosToggle;
        this.rateMonitorToggle = rateMonitorToggle;
        this.langSelect = langSelect;
        this.onSensitivityChange = onSensitivityChange;
        this.onScrollSensitivityChange = onScrollSensitivityChange;
        this.onRateMonitorChange = onRateMonitorChange;
        this.lifecycle = lifecycle;

        this.init();
    }

    private init() {
        // Load saved language
        const savedLang = i18n.getLanguage();
        this.langSelect.value = savedLang;
        i18n.updateDOM();

        // Load saved sensitivity
        const saved = readPreference('remote-mouse-sensitivity');
        if (saved) {
            const val = parseFloat(saved);
            this.sensitivitySlider.value = saved;
            this.sensitivityLabel.textContent = saved;
            this.onSensitivityChange(val);
        }

        // Load saved scroll sensitivity
        const savedScroll = readPreference('remote-mouse-scroll-sensitivity');
        if (savedScroll) {
            const val = parseFloat(savedScroll);
            this.scrollSensitivitySlider.value = savedScroll;
            this.scrollSensitivityLabel.textContent = savedScroll;
            this.onScrollSensitivityChange(val);
        }

        // Load saved theme
        const savedTheme = readPreference('remote-mouse-theme');
        if (savedTheme === 'light') {
            document.body.classList.add('light-mode');
            document.documentElement.classList.add('light-mode');
            this.themeToggle.checked = true;
        }

        // Load saved scroll position
        const savedScrollPos = readPreference('remote-mouse-scroll-pos');
        if (savedScrollPos === 'right') {
            document.body.classList.add('scroll-right');
            this.scrollPosToggle.checked = true;
        }

        // Load saved rate monitor
        const savedRateMonitor = readPreference('remote-mouse-rate-monitor');
        if (savedRateMonitor === 'true') {
            this.rateMonitorToggle.checked = true;
            this.onRateMonitorChange(true);
        }

        // Events
        let restoreTriggerFocus = true;
        const pointerInteraction = () => { restoreTriggerFocus = false; };
        // The parent also receives taps on the iOS haptic switch wrapping the button.
        this.openBtn.parentElement?.addEventListener('pointerdown', pointerInteraction, true);
        this.modal.addEventListener('pointerdown', pointerInteraction, true);
        this.openBtn.addEventListener('keydown', () => { restoreTriggerFocus = true; });

        this.openBtn.addEventListener('click', () => {
            this.lifecycle.onOpen?.();
            this.modal.classList.remove('hidden');
            this.closeBtn.focus({ preventScroll: true });
        });

        const close = () => {
            this.modal.classList.add('hidden');
            if (restoreTriggerFocus) {
                this.openBtn.focus({ preventScroll: true });
            } else {
                const active = document.activeElement;
                if (active instanceof HTMLElement && this.modal.contains(active)) active.blur();
            }
            this.lifecycle.onClose?.();
        };
        this.closeBtn.addEventListener('click', close);

        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                close();
            }
        });
        this.modal.addEventListener('keydown', e => {
            restoreTriggerFocus = true;
            if (e.key === 'Escape') { e.preventDefault(); close(); }
            if (e.key === 'Tab') {
                const focusable = Array.from(this.modal.querySelectorAll<HTMLElement>(
                    'button:not(:disabled), input, select'
                )).filter(el => !el.classList.contains('native-haptic-switch') && el.tabIndex >= 0);
                const first = focusable[0], last = focusable[focusable.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault(); last?.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault(); first?.focus();
                }
            }
        });

        this.sensitivitySlider.addEventListener('input', () => {
            const val = this.sensitivitySlider.value;
            this.sensitivityLabel.textContent = val;
            this.onSensitivityChange(parseFloat(val));
        });

        this.sensitivitySlider.addEventListener('change', () => {
            writePreference('remote-mouse-sensitivity', this.sensitivitySlider.value);
        });

        this.scrollSensitivitySlider.addEventListener('input', () => {
            const val = this.scrollSensitivitySlider.value;
            this.scrollSensitivityLabel.textContent = val;
            this.onScrollSensitivityChange(parseFloat(val));
        });

        this.scrollSensitivitySlider.addEventListener('change', () => {
            writePreference('remote-mouse-scroll-sensitivity', this.scrollSensitivitySlider.value);
        });

        this.themeToggle.addEventListener('change', () => {
            if (this.themeToggle.checked) {
                document.body.classList.add('light-mode');
                document.documentElement.classList.add('light-mode');
                writePreference('remote-mouse-theme', 'light');
            } else {
                document.body.classList.remove('light-mode');
                document.documentElement.classList.remove('light-mode');
                writePreference('remote-mouse-theme', 'dark');
            }
        });

        this.scrollPosToggle.addEventListener('change', () => {
            if (this.scrollPosToggle.checked) {
                document.body.classList.add('scroll-right');
                writePreference('remote-mouse-scroll-pos', 'right');
            } else {
                document.body.classList.remove('scroll-right');
                writePreference('remote-mouse-scroll-pos', 'left');
            }
        });

        this.rateMonitorToggle.addEventListener('change', () => {
            const enabled = this.rateMonitorToggle.checked;
            writePreference('remote-mouse-rate-monitor', enabled.toString());
            this.onRateMonitorChange(enabled);
        });

        this.langSelect.addEventListener('change', () => {
            i18n.setLanguage(this.langSelect.value as 'zh' | 'en');
        });
    }
}
