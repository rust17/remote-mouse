import html from '../index.html?raw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsManager } from '../src/ui/settings';
import { installNativeHapticTargets } from '../src/ui/native-haptics';

describe('settings dialog focus', () => {
    const get = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id)! as T;
    const pointerDown = (element: HTMLElement) => element.dispatchEvent(
        new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' })
    );
    const keyDown = (element: HTMLElement, key: string) => element.dispatchEvent(
        new KeyboardEvent('keydown', { bubbles: true, cancelable: true, key })
    );
    const initialize = (lifecycle: { onOpen?: () => void; onClose?: () => void } = {}) => new SettingsManager(
        get('settings-modal'), get('btn-settings'), get('btn-close-settings'),
        get<HTMLInputElement>('sensitivity-slider'), get('sensitivity-value'),
        get<HTMLInputElement>('scroll-sensitivity-slider'), get('scroll-sensitivity-value'),
        get<HTMLInputElement>('theme-toggle'), get<HTMLInputElement>('scroll-pos-toggle'),
        get<HTMLInputElement>('rate-monitor-toggle'), get<HTMLSelectElement>('lang-select'),
        vi.fn(), vi.fn(), vi.fn(), lifecycle
    );
    const openWithTouch = () => {
        pointerDown(get('btn-settings'));
        get('btn-settings').click();
        expect(document.activeElement).toBe(get('btn-close-settings'));
    };

    beforeEach(() => { localStorage.clear(); document.body.innerHTML = html; });
    afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });

    it('releases dialog focus after touching the close button', () => {
        initialize();
        openWithTouch();
        pointerDown(get('btn-close-settings'));
        get('btn-close-settings').click();
        expect(get('settings-modal').classList.contains('hidden')).toBe(true);
        expect(document.activeElement).toBe(document.body);
    });

    it('does not return focus after a backdrop tap even when opened with a keyboard', () => {
        initialize();
        keyDown(get('btn-settings'), 'Enter');
        get('btn-settings').click();
        pointerDown(get('settings-modal'));
        get('settings-modal').click();
        expect(document.activeElement).toBe(document.body);
    });

    it('returns focus for Escape after opening with touch', () => {
        initialize();
        openWithTouch();
        keyDown(get('btn-close-settings'), 'Escape');
        expect(get('settings-modal').classList.contains('hidden')).toBe(true);
        expect(document.activeElement).toBe(get('btn-settings'));
    });

    it('returns focus for keyboard activation of the close button', () => {
        initialize();
        openWithTouch();
        keyDown(get('btn-close-settings'), 'Enter');
        get('btn-close-settings').click();
        expect(document.activeElement).toBe(get('btn-settings'));
    });

    it('handles zero-detail clicks forwarded by iOS haptic switches after keyboard use', () => {
        initialize();
        keyDown(get('btn-settings'), 'Enter');
        get('btn-settings').click();
        keyDown(get('btn-close-settings'), 'Escape');
        vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('iPhone');
        const vibrate = Object.getOwnPropertyDescriptor(navigator, 'vibrate');
        const nativeSwitch = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'switch');
        Object.defineProperty(navigator, 'vibrate', { configurable: true, value: undefined });
        Object.defineProperty(HTMLInputElement.prototype, 'switch', { configurable: true, value: false });
        try {
            installNativeHapticTargets(get('app'));
            const openSwitch = get('btn-settings').parentElement!.querySelector<HTMLInputElement>('input')!;
            const closeSwitch = get('btn-close-settings').parentElement!.querySelector<HTMLInputElement>('input')!;
            pointerDown(openSwitch);
            openSwitch.click();
            pointerDown(closeSwitch);
            closeSwitch.focus();
            closeSwitch.click();
            expect(document.activeElement).toBe(document.body);
            expect(get('settings-modal').classList.contains('hidden')).toBe(true);
        } finally {
            if (vibrate) Object.defineProperty(navigator, 'vibrate', vibrate);
            else Reflect.deleteProperty(navigator, 'vibrate');
            if (nativeSwitch) Object.defineProperty(HTMLInputElement.prototype, 'switch', nativeSwitch);
            else Reflect.deleteProperty(HTMLInputElement.prototype, 'switch');
        }
    });

    it('lets the input panel restore its focus after pointer dismissal', () => {
        const input = get('keyboard-input');
        initialize({ onOpen: () => input.blur(), onClose: () => input.focus() });
        input.focus();
        openWithTouch();
        pointerDown(get('btn-close-settings'));
        get('btn-close-settings').click();
        expect(document.activeElement).toBe(input);
    });

    it('reflects and changes the mobile debug setting', () => {
        const setEnabled = vi.fn();
        window.remoteMouseDebug = { isEnabled: () => true, setEnabled };
        try {
            initialize();
            const toggle = get<HTMLInputElement>('debug-toggle');
            expect(toggle.checked).toBe(true);
            toggle.click();
            expect(setEnabled).toHaveBeenCalledExactlyOnceWith(false);
            toggle.click();
            expect(setEnabled).toHaveBeenLastCalledWith(true);
        } finally {
            delete window.remoteMouseDebug;
        }
    });
});
