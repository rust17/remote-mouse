export class SettingsManager {
    private modal: HTMLElement;
    private openBtn: HTMLElement;
    private closeBtn: HTMLElement;
    private sensitivitySlider: HTMLInputElement;
    private sensitivityLabel: HTMLElement;

    private onSensitivityChange: (val: number) => void;

    constructor(
        modal: HTMLElement,
        openBtn: HTMLElement,
        closeBtn: HTMLElement,
        slider: HTMLInputElement,
        label: HTMLElement,
        onSensitivityChange: (val: number) => void
    ) {
        this.modal = modal;
        this.openBtn = openBtn;
        this.closeBtn = closeBtn;
        this.sensitivitySlider = slider;
        this.sensitivityLabel = label;
        this.onSensitivityChange = onSensitivityChange;

        this.init();
    }

    private init() {
        // Load saved
        const saved = localStorage.getItem('remote-mouse-sensitivity');
        if (saved) {
            const val = parseFloat(saved);
            this.sensitivitySlider.value = saved;
            this.sensitivityLabel.textContent = saved;
            this.onSensitivityChange(val);
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
    }
}
