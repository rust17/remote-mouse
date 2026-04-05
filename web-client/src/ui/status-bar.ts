import { ConnectionStatus, allConnectionStatuses } from '../core/protocol';

export class StatusBar {
    private indicatorEl: HTMLElement;
    private textEl: HTMLElement;

    constructor(indicatorEl: HTMLElement) {
        this.indicatorEl = indicatorEl;
        this.textEl = indicatorEl.querySelector('.status-text')!;
    }

    public update(text: string, status: ConnectionStatus) {
        this.textEl.textContent = text;
        const allStatusClasses = allConnectionStatuses.map(s => `status-${s}`);
        this.indicatorEl.classList.remove(...allStatusClasses);
        this.indicatorEl.classList.add(`status-${status}`);
    }
}


