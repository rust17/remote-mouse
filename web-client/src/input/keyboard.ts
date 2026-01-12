interface KeyboardCallbacks {
    onText: (text: string) => void;
    onKeyAction: (key: string, modifierMask?: number) => void;
}

export class KeyboardHandler {
    private inputEl: HTMLTextAreaElement;
    private toggleBtn: HTMLElement;
    private fnPanelEl: HTMLElement;
    private callbacks: KeyboardCallbacks;

    private isComposing = false;
    private isOpen = false;
    private activeModifiers = 0; // Bitmask: 1=Ctrl, 2=Shift, 4=Alt, 8=Win

    constructor(
        inputEl: HTMLTextAreaElement,
        toggleBtn: HTMLElement,
        fnPanelEl: HTMLElement,
        callbacks: KeyboardCallbacks
    ) {
        this.inputEl = inputEl;
        this.toggleBtn = toggleBtn;
        this.fnPanelEl = fnPanelEl;
        this.callbacks = callbacks;

        this.initListeners();
        this.initFnKeys();
    }

    public toggle(show?: boolean) {
        this.isOpen = show !== undefined ? show : !this.isOpen;
        if (this.isOpen) {
            this.inputEl.focus();
            this.toggleBtn.classList.add('active');
        } else {
            this.inputEl.blur();
            this.toggleBtn.classList.remove('active');
        }
    }

    public isOpenState() {
        return this.isOpen;
    }

    public getActiveModifiers() {
        return this.activeModifiers;
    }

    private initListeners() {
        this.toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });

        this.inputEl.addEventListener('compositionstart', () => {
            this.isComposing = true;
        });

        this.inputEl.addEventListener('compositionend', (e) => {
            this.isComposing = false;
            if (e.data) {
                this.callbacks.onText(e.data);
            }
            this.inputEl.value = '';
        });

        this.inputEl.addEventListener('input', (e) => {
            const event = e as InputEvent;
            if (this.isComposing) return;

            if (event.data) {
                // If modifiers are active and it's a single char, treat as KeyAction (e.g. Ctrl+C)
                if (this.activeModifiers > 0 && event.data.length === 1) {
                    this.callbacks.onKeyAction(event.data.toLowerCase(), this.activeModifiers);
                    this.resetModifiers();
                } else {
                    this.callbacks.onText(event.data);
                }
            }

            // Clear input asynchronously
            setTimeout(() => {
                this.inputEl.value = '';
            }, 0);
        });

        this.inputEl.addEventListener('keydown', (e) => {
            if (this.isComposing) return;

            if (e.key === 'Backspace') {
                this.callbacks.onKeyAction('backspace', this.activeModifiers);
                this.resetModifiers();
                e.preventDefault();
            } else if (e.key === 'Delete') {
                this.callbacks.onKeyAction('delete', this.activeModifiers);
                this.resetModifiers();
                e.preventDefault();
            } else if (e.key === 'Enter') {
                this.callbacks.onKeyAction('enter', this.activeModifiers);
                this.resetModifiers();
                e.preventDefault();
            }
        });
    }

    private initFnKeys() {
        this.fnPanelEl.addEventListener('click', (e) => {
            const target = (e.target as HTMLElement).closest('.fn-btn');
            if (!target) return;

            const modifier = target.getAttribute('data-modifier');
            const key = target.getAttribute('data-key');

            if (modifier) {
                let bit = 0;
                if (modifier === 'ctrl') bit = 1;
                else if (modifier === 'shift') bit = 2;
                else if (modifier === 'alt') bit = 4;
                else if (modifier === 'win') bit = 8;

                if (bit > 0) {
                    if (this.activeModifiers & bit) {
                        this.activeModifiers &= ~bit;
                        target.classList.remove('active');
                    } else {
                        this.activeModifiers |= bit;
                        target.classList.add('active');
                    }
                }
            } else if (key) {
                this.callbacks.onKeyAction(key, this.activeModifiers);
                this.resetModifiers();
            }
        });
    }

    public resetModifiers() {
        if (this.activeModifiers === 0) return;
        this.activeModifiers = 0;
        const modifiers = this.fnPanelEl.querySelectorAll('.modifier');
        modifiers.forEach(el => el.classList.remove('active'));
    }
}
