import {
    OP_MOVE, OP_CLICK, OP_SCROLL, OP_DRAG, OP_TEXT, OP_KEY_ACTION
} from './core/protocol';
import { Transport } from './core/transport';
import { TouchpadHandler } from './input/touchpad';
import { ScrollStripHandler } from './input/scroll-strip';
import { KeyboardHandler } from './input/keyboard';
import { StatusBar } from './ui/status-bar';
import { SettingsManager } from './ui/settings';

class RemoteMouseApp {
    private transport: Transport;
    private touchpad: TouchpadHandler;
    private scrollStrip: ScrollStripHandler;
    private keyboard: KeyboardHandler;
    private statusBar: StatusBar;
    private moveBuffer = new ArrayBuffer(5);
    private moveView = new DataView(this.moveBuffer);

    constructor() {
        // 1. UI Elements
        this.statusBar = new StatusBar(document.getElementById('status-indicator')!);

        // 2. Transport
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws`;

        this.transport = new Transport({
            onStateChange: (state, text) => {
                this.statusBar.update(text, state);
            }
        });

        // 3. Touchpad
        this.touchpad = new TouchpadHandler(
            document.getElementById('touchpad')!,
            {
                onMove: (dx, dy) => this.sendMove(dx, dy),
                onClick: (button) => this.sendClick(button), // Button is already 1 or 2 from Handler
                onScroll: (sx, sy) => this.sendScroll(sx, sy),
                onDrag: (active) => this.sendDrag(active ? 1 : 0)
            }
        );

        // 4. Scroll Strip
        this.scrollStrip = new ScrollStripHandler(
            document.getElementById('scroll-strip')!,
            {
                onScroll: (sx, sy) => this.sendScroll(sx, sy)
            }
        );

        // 5. Keyboard
        this.keyboard = new KeyboardHandler(
            document.getElementById('keyboard-input')! as HTMLTextAreaElement,
            document.getElementById('btn-keyboard')!,
            document.getElementById('fn-panel')!,
            {
                onText: (text) => this.sendText(text),
                onKeyAction: (key, modifierMask) => this.sendKeyAction(key, modifierMask)
            }
        );

        // 6. Settings
        new SettingsManager(
            document.getElementById('settings-modal')!,
            document.getElementById('btn-settings')!,
            document.getElementById('btn-close-settings')!,
            document.getElementById('sensitivity-slider')! as HTMLInputElement,
            document.getElementById('sensitivity-value')!,
            document.getElementById('scroll-sensitivity-slider')! as HTMLInputElement,
            document.getElementById('scroll-sensitivity-value')!,
            (val) => this.touchpad.setSensitivity(val),
            (val) => {
                this.touchpad.setScrollSensitivity(val);
                this.scrollStrip.setSensitivity(val);
            }
        );

        // Connect
        this.transport.connect(url);

        // Handle touchpad/keyboard interaction
        // If keyboard is open, and touchpad is clicked, maybe close keyboard?
        // The original logic had: "touchpad pointerdown -> if keyboard open -> close it".
        // TouchpadHandler exposes logic, but doesn't expose "onPointerDown".
        // We can add a simple global listener or modify TouchpadHandler.
        // For now, let's attach a simple listener to the touchpad element here for that specific interaction
        // to avoid coupling TouchpadHandler to Keyboard logic.
        document.getElementById('touchpad')!.addEventListener('pointerdown', () => {
            if (this.keyboard.isOpenState()) {
                this.keyboard.toggle(false);
            }
        });
    }

    // --- Encoding Helpers ---

    private sendMove(dx: number, dy: number) {
        this.moveView.setUint8(0, OP_MOVE);
        this.moveView.setInt16(1, dx, false);
        this.moveView.setInt16(3, dy, false);
        this.transport.send(this.moveBuffer);
    }

    private sendClick(button: number) {
        // [OpCode] [Button] [ModifierMask]
        const mask = this.keyboard.getActiveModifiers();
        const buffer = new ArrayBuffer(3);
        const view = new DataView(buffer);
        view.setUint8(0, OP_CLICK);
        view.setUint8(1, button);
        view.setUint8(2, mask);
        this.transport.send(buffer);

        // If mask was used, we might want to reset it?
        // Original code: if (mask !== 0) this.resetModifiers();
        // But resetModifiers is private in KeyboardHandler.
        // The KeyboardHandler only resets modifiers on KeyAction or Manual Toggle.
        // Original code logic:
        // sendClick: if (mask !== 0) { this.resetModifiers(); }
        // sendKeyAction: if (mask !== 0) { this.resetModifiers(); }

        // Current KeyboardHandler implementation ONLY resets on sendKeyAction (inside input/keyboard.ts).
        // It does NOT expose a public resetModifiers().
        // For Clicks, if I Ctrl+Click, usually I expect Ctrl to be consumed?
        // Yes. So I should probably expose `resetModifiers` too, or make `getActiveModifiers` optionally consume them.
        // Let's call a new method `consumeModifiers()` on KeyboardHandler.
        if (mask !== 0) {
             this.keyboard.resetModifiers();
        }
    }

    private sendScroll(sx: number, sy: number) {
        const buffer = new ArrayBuffer(5);
        const view = new DataView(buffer);
        view.setUint8(0, OP_SCROLL);
        view.setInt16(1, sx, false);
        view.setInt16(3, sy, false);
        this.transport.send(buffer);
    }

    private sendDrag(state: number) {
        const buffer = new ArrayBuffer(2);
        const view = new DataView(buffer);
        view.setUint8(0, OP_DRAG);
        view.setUint8(1, state);
        this.transport.send(buffer);
    }

    private sendText(text: string) {
        if (!text) return;
        const encoder = new TextEncoder();
        const textBytes = encoder.encode(text);
        const buffer = new Uint8Array(1 + textBytes.length);
        buffer[0] = OP_TEXT;
        buffer.set(textBytes, 1);
        this.transport.send(buffer.buffer);
    }

    private sendKeyAction(keyName: string, modifierMask: number = 0) {
        const encoder = new TextEncoder();
        const keyBytes = encoder.encode(keyName);
        const buffer = new Uint8Array(2 + keyBytes.length);
        buffer[0] = OP_KEY_ACTION;
        buffer[1] = modifierMask;
        buffer.set(keyBytes, 2);
        this.transport.send(buffer.buffer);
    }
}

new RemoteMouseApp();
