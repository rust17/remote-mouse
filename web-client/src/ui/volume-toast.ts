import type { MediaSnapshot } from '../core/protocol';

const DISPLAY_TIME = 1600;

export class VolumeToast {
    private element: HTMLElement;
    private value: HTMLOutputElement;
    private meter: HTMLElement;
    private timer: number | null = null;
    private state: MediaSnapshot['state'] | null = null;

    constructor(element: HTMLElement) {
        this.element = element;
        this.value = element.querySelector<HTMLOutputElement>('#media-volume')!;
        this.meter = element.querySelector<HTMLElement>('.volume-toast-meter')!;
    }

    public update(state: MediaSnapshot['state'] | null) {
        this.state = state;
        const volume = state?.volume;
        const text = volume === null || volume === undefined ? '—' : `${Math.round(volume)}%`;
        if (this.value.textContent !== text) this.value.textContent = text;
        if (volume === null || volume === undefined || state?.muted === null) {
            this.meter.removeAttribute('aria-valuenow');
            this.hide();
            return;
        }
        const level = Math.max(0, Math.min(100, volume));
        this.element.style.setProperty('--volume-level', `${level}%`);
        this.element.dataset.volumeLevel = state?.muted ? 'muted' : volume === 0 ? 'off' : volume < 50 ? 'low' : 'high';
        this.meter.setAttribute('aria-valuenow', String(level));
    }

    public show() {
        if (this.state?.volume === null || this.state?.volume === undefined || this.state.muted === null) return;
        if (this.timer !== null) clearTimeout(this.timer);
        this.element.classList.add('visible');
        this.element.setAttribute('aria-hidden', 'false');
        this.timer = window.setTimeout(() => this.hide(), DISPLAY_TIME);
    }

    public hide() {
        if (this.timer !== null) clearTimeout(this.timer);
        this.timer = null;
        this.element.classList.remove('visible');
        this.element.setAttribute('aria-hidden', 'true');
    }
}
