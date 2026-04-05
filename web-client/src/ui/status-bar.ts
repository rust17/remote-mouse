import { ConnectionStatus, allConnectionStatuses } from '../core/protocol';
import { i18n } from '../core/i18n';

export class StatusBar {
    private indicatorEl: HTMLElement;
    private textEl: HTMLElement;
    private currentKey: string = 'status.connecting';

    constructor(indicatorEl: HTMLElement) {
        this.indicatorEl = indicatorEl;
        this.textEl = indicatorEl.querySelector('.status-text')!;
        
        // Ensure initial translation
        this.updateDOM();
    }

    public update(key: string, status: ConnectionStatus) {
        this.currentKey = key;
        this.updateDOM();
        
        const allStatusClasses = allConnectionStatuses.map(s => `status-${s}`);
        this.indicatorEl.classList.remove(...allStatusClasses);
        this.indicatorEl.classList.add(`status-${status}`);
    }

    private updateDOM() {
        // @ts-ignore
        this.textEl.textContent = i18n.t(this.currentKey as any);
        // Also set as data-i18n for reactive updates from i18n.updateDOM()
        this.textEl.setAttribute('data-i18n', this.currentKey);
    }
}



