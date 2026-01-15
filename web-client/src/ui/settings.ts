export class SettingsManager {
    private modal: HTMLElement;
    private openBtn: HTMLElement;
    private closeBtn: HTMLElement;
    private sensitivitySlider: HTMLInputElement;
    private sensitivityLabel: HTMLElement;
    private scrollSensitivitySlider: HTMLInputElement;
    private scrollSensitivityLabel: HTMLElement;

    private onSensitivityChange: (val: number) => void;
    private onScrollSensitivityChange: (val: number) => void;

    constructor(
        modal: HTMLElement,
        openBtn: HTMLElement,
        closeBtn: HTMLElement,
        slider: HTMLInputElement,
        label: HTMLElement,
        scrollSlider: HTMLInputElement,
        scrollLabel: HTMLElement,
        onSensitivityChange: (val: number) => void,
        onScrollSensitivityChange: (val: number) => void
    ) {
        this.modal = modal;
        this.openBtn = openBtn;
        this.closeBtn = closeBtn;
        this.sensitivitySlider = slider;
        this.sensitivityLabel = label;
        this.scrollSensitivitySlider = scrollSlider;
        this.scrollSensitivityLabel = scrollLabel;
        this.onSensitivityChange = onSensitivityChange;
        this.onScrollSensitivityChange = onScrollSensitivityChange;

        this.init();
    }

    private init() {
        // Load saved sensitivity
        const saved = localStorage.getItem('remote-mouse-sensitivity');
        if (saved) {
            const val = parseFloat(saved);
            this.sensitivitySlider.value = saved;
            this.sensitivityLabel.textContent = saved;
            this.onSensitivityChange(val);
        }

        // Load saved scroll sensitivity
        const savedScroll = localStorage.getItem('remote-mouse-scroll-sensitivity');
        if (savedScroll) {
            const val = parseFloat(savedScroll);
            this.scrollSensitivitySlider.value = savedScroll;
            this.scrollSensitivityLabel.textContent = savedScroll;
            this.onScrollSensitivityChange(val);
        }

        // Events
        this.openBtn.addEventListener('click', () => {
            this.modal.classList.remove('hidden');
        });

        this.closeBtn.addEventListener('click', () => {
            this.modal.classList.add('hidden');
        });

        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.modal.classList.add('hidden');
            }
        });

        this.sensitivitySlider.addEventListener('input', () => {
            const val = this.sensitivitySlider.value;
            this.sensitivityLabel.textContent = val;
            this.onSensitivityChange(parseFloat(val));
        });

        this.sensitivitySlider.addEventListener('change', () => {
            localStorage.setItem('remote-mouse-sensitivity', this.sensitivitySlider.value);
        });

        this.scrollSensitivitySlider.addEventListener('input', () => {
            const val = this.scrollSensitivitySlider.value;
            this.scrollSensitivityLabel.textContent = val;
            this.onScrollSensitivityChange(parseFloat(val));
        });

        this.scrollSensitivitySlider.addEventListener('change', () => {
            localStorage.setItem('remote-mouse-scroll-sensitivity', this.scrollSensitivitySlider.value);
        });
    }
}
