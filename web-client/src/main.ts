import {
    OP_MOVE, OP_CLICK, OP_SCROLL, OP_DRAG, OP_TEXT, OP_KEY_ACTION
} from './core/protocol';
import { Transport } from './core/transport';
import { TouchpadHandler } from './input/touchpad';
import { ScrollStripHandler } from './input/scroll-strip';
import { KeyboardHandler } from './input/keyboard';
import { StatusBar } from './ui/status-bar';
import { SettingsManager } from './ui/settings';
import { WebHaptics } from 'web-haptics';

class RemoteMouseApp {
    private transport: Transport;
    private touchpad: TouchpadHandler;
    private scrollStrip: ScrollStripHandler;
    private keyboard: KeyboardHandler;
    private statusBar: StatusBar;
    private haptics = new WebHaptics();
    private moveBuffer = new ArrayBuffer(5);
    private moveView = new DataView(this.moveBuffer);
    private rateMonitorTimer: number | null = null;

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
            },
            this.haptics
        );

        // 6. Settings
        const rateMonitorEl = document.getElementById('rate-monitor')!;
        const ratePpsEl = document.getElementById('rate-pps')!;
        const rateBpsEl = document.getElementById('rate-bps')!;

        new SettingsManager(
            document.getElementById('settings-modal')!,
            document.getElementById('btn-settings')!,
            document.getElementById('btn-close-settings')!,
            document.getElementById('sensitivity-slider')! as HTMLInputElement,
            document.getElementById('sensitivity-value')!,
            document.getElementById('scroll-sensitivity-slider')! as HTMLInputElement,
            document.getElementById('scroll-sensitivity-value')!,
            document.getElementById('theme-toggle')! as HTMLInputElement,
            document.getElementById('scroll-pos-toggle')! as HTMLInputElement,
            document.getElementById('rate-monitor-toggle')! as HTMLInputElement,
            document.getElementById('lang-select')! as HTMLSelectElement,
            (val) => this.touchpad.setSensitivity(val),
            (val) => {
                this.touchpad.setScrollSensitivity(val);
                this.scrollStrip.setSensitivity(val);
            },
            (enabled) => {
                // Client-side rate monitor
                if (enabled) {
                    rateMonitorEl.classList.remove('hidden');
                    if (!this.rateMonitorTimer) {
                        this.rateMonitorTimer = window.setInterval(() => {
                            const { packetsSent, bytesSent } = this.transport.getMetrics();
                            ratePpsEl.textContent = packetsSent.toString();
                            rateBpsEl.textContent = this.formatBytes(bytesSent);
                        }, 1000);
                    }
                } else {
                    rateMonitorEl.classList.add('hidden');
                    if (this.rateMonitorTimer) {
                        clearInterval(this.rateMonitorTimer);
                        this.rateMonitorTimer = null;
                    }
                }

                // Server-side tray rate
                fetch(`/api/settings/tray/rate?enabled=${enabled ? 'true' : 'false'}`, {
                    method: 'POST'
                }).catch(e => console.error('Failed to update server tray rate', e));
            }
        );

        // Connect
        this.transport.connect(url);

        // Handle touchpad/keyboard interaction
        document.getElementById('touchpad')!.addEventListener('pointerdown', () => {
            if (this.keyboard.isOpenState()) {
                this.keyboard.toggle(false);
            }
        });

        // Global haptic feedback for buttons and interactive inputs
        document.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            if (target.closest('button') || target.closest('input[type="checkbox"]') || target.closest('input[type="range"]')) {
                this.haptics.trigger('light');
            }
        });
    }

    private formatBytes(bytes: number): string {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB/s', 'MB/s'];
        const i = bytes > 0 ? Math.floor(Math.log(bytes) / Math.log(k)) : 0;
        const val = parseFloat((bytes / Math.pow(k, i)).toFixed(1));
        return val + ' ' + (i === 0 ? 'B' : sizes[i]);
    }

    // --- Encoding Helpers ---

    private sendMove(dx: number, dy: number) {
        this.moveView.setUint8(0, OP_MOVE);
        this.moveView.setInt16(1, dx, false);
        this.moveView.setInt16(3, dy, false);
        this.transport.send(this.moveBuffer);
    }

    private sendClick(button: number) {
        this.haptics.trigger('medium');
        // [OpCode] [Button] [ModifierMask]
        const mask = this.keyboard.getActiveModifiers();
        const buffer = new ArrayBuffer(3);
        const view = new DataView(buffer);
        view.setUint8(0, OP_CLICK);
        view.setUint8(1, button);
        view.setUint8(2, mask);
        this.transport.send(buffer);

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
