import html from '../index.html?raw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('web-haptics', () => ({
    WebHaptics: class { trigger = vi.fn(); }
}));

describe('startup with unavailable preference storage', () => {
    const get = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id)! as T;
    let socket: { readyState: number; onopen?: () => void; send: ReturnType<typeof vi.fn> };
    let connect: ReturnType<typeof vi.fn>;
    let windowListeners: ReturnType<typeof vi.spyOn>;
    let documentListeners: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        vi.resetModules();
        vi.useFakeTimers();
        localStorage.clear();
        document.body.innerHTML = html;
        document.body.className = '';
        document.documentElement.className = '';
        window.history.replaceState(null, '', '/');
        windowListeners = vi.spyOn(window, 'addEventListener');
        documentListeners = vi.spyOn(document, 'addEventListener');
        vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })));
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({})));
        socket = { readyState: 0, send: vi.fn() };
        connect = vi.fn();
        vi.stubGlobal('WebSocket', class {
            static OPEN = 1;
            constructor(url: string) { connect(url); return socket; }
        });
    });

    afterEach(() => {
        for (const [type, listener, options] of windowListeners.mock.calls) {
            window.removeEventListener(type, listener, options);
        }
        for (const [type, listener, options] of documentListeners.mock.calls) {
            document.removeEventListener(type, listener, options);
        }
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        vi.useRealTimers();
        document.body.innerHTML = '';
        document.body.className = '';
        document.documentElement.className = '';
    });

    const boot = async () => {
        await import('../src/main');
        expect(connect).toHaveBeenCalledExactlyOnceWith(`ws://${window.location.host}/ws`);
        socket.readyState = 1;
        socket.onopen!();
        expect(get('status-indicator').classList.contains('status-connected')).toBe(true);
    };

    it.each(['access', 'read', 'write'] as const)('keeps controls working when storage %s throws', async failure => {
        if (failure === 'access') {
            vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
                throw new DOMException('Access denied', 'SecurityError');
            });
        } else {
            vi.spyOn(Storage.prototype, failure === 'read' ? 'getItem' : 'setItem')
                .mockImplementation(() => {
                    throw new DOMException('Storage unavailable', failure === 'write' ? 'QuotaExceededError' : 'SecurityError');
                });
        }

        await boot();
        expect(get<HTMLSelectElement>('lang-select').value).toBe('zh');
        expect(get<HTMLInputElement>('theme-toggle').checked).toBe(false);
        expect(get('composer').hidden).toBe(true);

        get('btn-keyboard').click();
        expect(get('input-panel').hidden).toBe(false);
        get('btn-settings').click();
        expect(get('settings-modal').classList.contains('hidden')).toBe(false);

        const sensitivity = get<HTMLInputElement>('sensitivity-slider');
        sensitivity.value = '3';
        sensitivity.dispatchEvent(new Event('input'));
        sensitivity.dispatchEvent(new Event('change'));
        expect(get('sensitivity-value').textContent).toBe('3');
        get('theme-toggle').click();
        expect(document.body.classList.contains('light-mode')).toBe(true);
        get('scroll-pos-toggle').click();
        expect(document.body.classList.contains('scroll-right')).toBe(true);
        get('rate-monitor-toggle').click();
        expect(get('rate-monitor').classList.contains('hidden')).toBe(false);

        const language = get<HTMLSelectElement>('lang-select');
        language.value = 'en';
        language.dispatchEvent(new Event('change'));
        expect(document.documentElement.lang).toBe('en');
        expect(get('settings-title').textContent).toBe('Settings');

        document.querySelector<HTMLButtonElement>('[data-input-mode="draft"]')!.click();
        expect(get('composer').hidden).toBe(false);
        get('btn-close-settings').click();
        get('btn-keyboard').click();
        const draft = get<HTMLInputElement>('draft-input');
        draft.value = 'Hello';
        socket.send.mockClear();
        get('btn-send').click();
        expect(socket.send).toHaveBeenCalledOnce();
        const packet = new Uint8Array(socket.send.mock.calls[0][0]);
        expect(new TextDecoder().decode(packet.subarray(1))).toBe('Hello');
        expect(draft.value).toBe('');
    });

    it('restores and saves preferences when storage is available', async () => {
        localStorage.setItem('remote-mouse-lang', 'en');
        localStorage.setItem('remote-mouse-theme', 'light');
        localStorage.setItem('remote-mouse-input-mode', 'draft');
        localStorage.setItem('remote-mouse-sensitivity', '3');
        await boot();
        expect(document.documentElement.lang).toBe('en');
        expect(document.body.classList.contains('light-mode')).toBe(true);
        expect(get('composer').hidden).toBe(false);
        expect(get('sensitivity-value').textContent).toBe('3');

        get('theme-toggle').click();
        document.querySelector<HTMLButtonElement>('[data-input-mode="realtime"]')!.click();
        expect(localStorage.getItem('remote-mouse-theme')).toBe('dark');
        expect(localStorage.getItem('remote-mouse-input-mode')).toBe('realtime');
    });
});
