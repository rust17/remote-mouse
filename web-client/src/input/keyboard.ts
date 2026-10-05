import { WebHaptics } from 'web-haptics';
import { i18n } from '../core/i18n';

interface KeyboardCallbacks {
    onText: (text: string) => boolean | void;
    onKeyAction: (key: string, modifierMask?: number) => void;
}

interface InputPanel {
    panel: HTMLElement;
    composer: HTMLElement;
    draft: HTMLInputElement;
    send: HTMLButtonElement;
    feedback: HTMLElement;
    modeButtons: NodeListOf<HTMLButtonElement>;
}

type InputMode = 'realtime' | 'draft';

export class KeyboardHandler {
    private inputEl: HTMLInputElement;
    private toggleBtn: HTMLElement;
    private fnPanelEl: HTMLElement;
    private callbacks: KeyboardCallbacks;
    private haptics: WebHaptics;
    private panel?: InputPanel;
    private isComposing = false;
    private committedComposition: string | null = null;
    private compositionTimer: number | null = null;
    private isOpen = false;
    private focusSuspended = false;
    private activeModifiers = 0;
    private inputMode: InputMode = 'realtime';

    constructor(inputEl: HTMLInputElement, toggleBtn: HTMLElement, fnPanelEl: HTMLElement,
        callbacks: KeyboardCallbacks, haptics: WebHaptics, panel?: InputPanel) {
        this.inputEl = inputEl;
        this.toggleBtn = toggleBtn;
        this.fnPanelEl = fnPanelEl;
        this.callbacks = callbacks;
        this.haptics = haptics;
        this.panel = panel;
        this.initListeners();
        this.initFnKeys();
        if (panel) this.initPanel(panel);
    }

    public toggle(show?: boolean) {
        if (!this.toggleBtn.closest('.native-haptic-target')) this.haptics.trigger('light');
        this.setOpen(show !== undefined ? show : !this.isOpen);
    }

    public close() { this.setOpen(false); }

    private setOpen(show: boolean) {
        this.isOpen = show;
        this.toggleBtn.classList.toggle('active', this.isOpen);
        this.toggleBtn.setAttribute('aria-expanded', String(this.isOpen));
        this.toggleBtn.setAttribute('data-i18n-aria', this.isOpen ? 'input.close' : 'input.open');
        this.toggleBtn.setAttribute('aria-label', i18n.t(this.isOpen ? 'input.close' : 'input.open'));
        document.getElementById('app')?.classList.toggle('typing', this.isOpen);
        if (this.panel) this.panel.panel.hidden = !this.isOpen;
        if (this.isOpen) this.restoreFocus();
        else this.currentInput().blur();
    }

    public isOpenState() { return this.isOpen; }
    public getActiveModifiers() { return this.activeModifiers; }

    private currentInput() {
        return this.inputMode === 'draft' && this.panel ? this.panel.draft : this.inputEl;
    }

    public restoreFocus() {
        if (this.isOpen && !this.focusSuspended) this.currentInput().focus({ preventScroll: true });
    }

    public suspendFocus() { this.focusSuspended = true; this.currentInput().blur(); }
    public resumeFocus() { this.focusSuspended = false; this.restoreFocus(); }

    private initPanel(panel: InputPanel) {
        this.inputMode = localStorage.getItem('remote-mouse-input-mode') === 'draft' ? 'draft' : 'realtime';
        this.renderInputMode();
        panel.modeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const mode = button.dataset.inputMode;
                if (mode === 'realtime' || mode === 'draft') this.setInputMode(mode);
            });
        });
        panel.send.addEventListener('pointerdown', e => {
            if (!(e.target as HTMLElement).classList.contains('native-haptic-switch')) e.preventDefault();
        });
        panel.send.addEventListener('click', () => {
            if (this.isComposing || this.inputMode !== 'draft' || !panel.draft.value) {
                this.restoreFocus();
                return;
            }
            // Only clear a draft accepted by the WebSocket transport. This is not an execution ACK.
            if (this.callbacks.onText(panel.draft.value) !== false) {
                panel.draft.value = '';
                panel.feedback.textContent = '';
                panel.feedback.removeAttribute('data-i18n');
            } else {
                panel.feedback.setAttribute('data-i18n', 'input.not_sent');
                panel.feedback.textContent = i18n.t('input.not_sent');
            }
            this.restoreFocus();
        });
        panel.draft.addEventListener('compositionstart', () => { this.isComposing = true; });
        panel.draft.addEventListener('compositionend', () => { this.isComposing = false; });
        panel.draft.addEventListener('keydown', e => {
            if (this.isComposing || e.isComposing) return;
            if (e.key === 'Enter') {
                e.preventDefault();
                this.keyAction('enter'); // Confirm on the computer; sending is an explicit action.
            }
        });
        panel.draft.addEventListener('input', () => {
            panel.feedback.textContent = '';
            panel.feedback.removeAttribute('data-i18n');
        });
    }

    public setInputMode(mode: InputMode) {
        if (mode === this.inputMode) return;
        this.currentInput().blur();
        this.isComposing = false;
        this.clearComposition();
        this.inputEl.value = '';
        this.inputMode = mode;
        localStorage.setItem('remote-mouse-input-mode', mode);
        this.renderInputMode();
        this.restoreFocus();
    }

    private renderInputMode() {
        if (!this.panel) return;
        this.panel.composer.hidden = this.inputMode !== 'draft';
        this.panel.panel.classList.toggle('draft-mode', this.inputMode === 'draft');
        this.panel.modeButtons.forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.inputMode === this.inputMode));
        });
    }

    private clearComposition() {
        if (this.compositionTimer !== null) window.clearTimeout(this.compositionTimer);
        this.compositionTimer = null;
        this.committedComposition = null;
    }

    private keyAction(key: string) {
        this.callbacks.onKeyAction(key, this.activeModifiers);
        this.resetModifiers();
    }

    private initListeners() {
        this.toggleBtn.addEventListener('pointerdown', e => {
            if (!(e.target as HTMLElement).classList.contains('native-haptic-switch')) e.preventDefault();
        });
        this.toggleBtn.addEventListener('click', e => { e.stopPropagation(); this.toggle(); });
        this.inputEl.addEventListener('compositionstart', () => {
            this.clearComposition();
            this.isComposing = true;
        });
        this.inputEl.addEventListener('compositionend', e => {
            this.isComposing = false;
            if (this.inputMode !== 'realtime') return;
            if (e.data) {
                this.callbacks.onText(e.data);
                // Some browsers emit a final input event after compositionend.
                this.committedComposition = e.data;
                this.compositionTimer = window.setTimeout(() => this.clearComposition(), 0);
            }
            this.inputEl.value = '';
        });
        this.inputEl.addEventListener('input', e => {
            const event = e as InputEvent;
            if (this.isComposing || event.isComposing || this.inputMode !== 'realtime') return;
            const text = event.data ?? this.inputEl.value;
            if (text && text === this.committedComposition) {
                this.clearComposition();
                this.inputEl.value = '';
                return;
            }
            this.clearComposition();
            if (text) {
                if (this.activeModifiers && text.length === 1) this.keyAction(text.toLowerCase());
                else this.callbacks.onText(text);
            }
            this.inputEl.value = '';
        });
        // Soft keyboards can delete without a keydown event.
        this.inputEl.addEventListener('beforeinput', e => {
            const event = e as InputEvent;
            if (this.isComposing || event.isComposing || this.inputMode !== 'realtime') return;
            if (event.inputType === 'deleteContentBackward' || event.inputType === 'deleteContentForward') {
                e.preventDefault();
                this.keyAction(event.inputType === 'deleteContentBackward' ? 'backspace' : 'delete');
            }
        });
        this.inputEl.addEventListener('keydown', e => {
            if (this.isComposing || e.isComposing || this.inputMode !== 'realtime') return;
            const key = { Backspace: 'backspace', Delete: 'delete', Enter: 'enter' }[e.key];
            if (key) { e.preventDefault(); this.keyAction(key); }
        });
    }

    private initFnKeys() {
        this.fnPanelEl.addEventListener('click', e => {
            const target = this.getFnButton(e.target);
            if (!target || target.hasAttribute('disabled') || target.closest('[hidden]')) return;
            this.restoreFocus();
            const modifier = target.getAttribute('data-modifier');
            const key = target.getAttribute('data-key');
            const bits: Record<string, number> = { ctrl: 1, shift: 2, alt: 4, win: 8 };
            if (modifier && bits[modifier]) {
                this.activeModifiers ^= bits[modifier];
                target.classList.toggle('active', !!(this.activeModifiers & bits[modifier]));
                target.setAttribute('aria-pressed', String(!!(this.activeModifiers & bits[modifier])));
            } else if (key) this.keyAction(key);
        });
        this.fnPanelEl.addEventListener('pointerdown', e => {
            const target = this.getFnButton(e.target);
            if (!target) return;
            if (!(e.target as HTMLElement).classList.contains('native-haptic-switch')) e.preventDefault();
            if (!target.hasAttribute('data-modifier')) target.classList.add('active');
        });
        const clearActive = (e: PointerEvent) => {
            const target = this.getFnButton(e.target);
            if (!target || target.hasAttribute('data-modifier')) return;
            if (e.type === 'pointerout' && this.getFnButton(e.relatedTarget) === target) return;
            target.classList.remove('active');
        };
        for (const type of ['pointerup', 'pointerout', 'pointercancel'] as const) {
            this.fnPanelEl.addEventListener(type, clearActive);
        }
    }

    private getFnButton(target: EventTarget | null): HTMLElement | null {
        if (!(target instanceof Element)) return null;
        return target.closest<HTMLElement>('.fn-btn')
            ?? target.closest('.native-haptic-target')?.querySelector<HTMLElement>('.fn-btn') ?? null;
    }

    public resetModifiers() {
        this.activeModifiers = 0;
        this.fnPanelEl.querySelectorAll('.modifier').forEach(el => {
            el.classList.remove('active');
            el.setAttribute('aria-pressed', 'false');
        });
    }
}
