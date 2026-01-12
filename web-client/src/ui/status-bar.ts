export class StatusBar {
    private indicatorEl: HTMLElement;
    private textEl: HTMLElement;

    constructor(indicatorEl: HTMLElement) {
        this.indicatorEl = indicatorEl;
        this.textEl = indicatorEl.querySelector('.status-text')!;
    }

    public update(status: string, state: 'connected' | 'disconnected' | 'connecting') {
        this.textEl.textContent = status;
        this.indicatorEl.classList.remove('status-connected', 'status-disconnected', 'status-connecting');
        this.indicatorEl.classList.add(`status-${state}`);
    }
}
