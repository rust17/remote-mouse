import type { ControlMode } from '../input/touchpad';

export class ControlModeController {
    private mode: ControlMode;
    private app: HTMLElement;
    private onChange: (mode: ControlMode) => void;
    private keepFocus: () => void;

    constructor(app: HTMLElement, onChange: (mode: ControlMode) => void, keepFocus: () => void) {
        this.app = app;
        this.onChange = onChange;
        this.keepFocus = keepFocus;
        this.mode = this.modeFromURL();
        this.render();
        this.onChange(this.mode);
        app.querySelectorAll<HTMLButtonElement>('#mode-switch [data-mode]').forEach(button => {
            button.addEventListener('pointerdown', event => {
                if (!(event.target as HTMLElement).classList.contains('native-haptic-switch')) {
                    event.preventDefault();
                }
            });
            button.addEventListener('click', () => {
                const mode = button.dataset.mode;
                if (mode === 'computer' || mode === 'tv') this.setMode(mode, true);
                this.keepFocus();
            });
        });
        window.addEventListener('popstate', () => { this.setMode(this.modeFromURL()); this.keepFocus(); });
    }

    private modeFromURL(): ControlMode {
        return new URLSearchParams(window.location.search).get('mode') === 'tv' ? 'tv' : 'computer';
    }

    private setMode(mode: ControlMode, updateURL = false) {
        if (mode === this.mode) return;
        this.mode = mode;
        this.onChange(mode);
        this.render();
        if (updateURL) {
            const url = new URL(window.location.href);
            url.searchParams.set('mode', mode);
            window.history.replaceState(null, '', url);
        }
    }

    private render() {
        this.app.dataset.mode = this.mode;
        this.app.querySelectorAll<HTMLButtonElement>('#mode-switch [data-mode]').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.mode === this.mode));
        });
        this.app.querySelector<HTMLElement>('#fn-panel')!.hidden = this.mode !== 'computer';
        this.app.querySelector<HTMLElement>('#media-panel')!.hidden = this.mode !== 'tv';
        this.app.querySelector<HTMLElement>('#btn-fullscreen')!.hidden = this.mode !== 'tv';
    }
}
