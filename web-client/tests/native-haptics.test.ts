import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WebHaptics } from 'web-haptics';
import { installNativeHapticTargets } from '../src/ui/native-haptics';
import { KeyboardHandler } from '../src/input/keyboard';

describe('iOS direct-tap haptics', () => {
    const originalVibrate = Object.getOwnPropertyDescriptor(navigator, 'vibrate');
    beforeEach(() => {
        vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('iPhone');
        Object.defineProperty(navigator, 'vibrate', { configurable: true, get: () => undefined });
        Object.defineProperty(HTMLInputElement.prototype, 'switch', { configurable: true, value: false });
        document.body.innerHTML = `
            <div id="app">
                <button id="keyboard">Keyboard</button>
                <div id="panel">
                    <button class="fn-btn" data-key="enter">Enter</button>
                    <button class="fn-btn modifier" data-modifier="ctrl">Ctrl</button>
                </div>
                <label class="switch"><input type="checkbox"><span class="slider"></span></label>
                <input id="text" type="text">
                <div id="touchpad"></div>
            </div>`;
    });

    afterEach(() => {
        vi.restoreAllMocks();
        if (originalVibrate) Object.defineProperty(navigator, 'vibrate', originalVibrate);
        else Reflect.deleteProperty(navigator, 'vibrate');
        Reflect.deleteProperty(HTMLInputElement.prototype, 'switch');
        document.body.innerHTML = '';
    });

    const install = () => installNativeHapticTargets(document.getElementById('app')!);

    it('forwards each native tap once without cancelling the switch activation', () => {
        const button = document.getElementById('keyboard')!;
        const action = vi.fn();
        button.addEventListener('click', action);
        install();
        const input = button.parentElement!.querySelector('input')!;
        input.click();
        expect(input.checked).toBe(true);
        expect(action).toHaveBeenCalledTimes(1);
        input.click();
        expect(input.checked).toBe(false);
        expect(action).toHaveBeenCalledTimes(2);
        expect(document.querySelector('#touchpad input')).toBeNull();
    });

    it('retains settings changes and does not duplicate overlays on reinstallation', () => {
        const setting = document.querySelector<HTMLInputElement>('.switch input')!;
        const changed = vi.fn();
        setting.addEventListener('change', changed);
        install();
        install();
        setting.click();
        expect(setting.checked).toBe(true);
        expect(setting.hasAttribute('switch')).toBe(true);
        expect(changed).toHaveBeenCalledTimes(1);
        expect(document.querySelectorAll('.native-haptic-target')).toHaveLength(3);
    });

    it('preserves key actions, modifier toggles and keyboard focus', () => {
        const input = document.getElementById('text') as HTMLInputElement;
        const onKeyAction = vi.fn();
        const haptics = { trigger: vi.fn() } as unknown as WebHaptics;
        const keyboard = new KeyboardHandler(input, document.getElementById('keyboard')!,
            document.getElementById('panel')!, { onText: vi.fn(), onKeyAction }, haptics);
        install();
        document.querySelector<HTMLInputElement>('#keyboard + input')!.click();
        expect(keyboard.isOpenState()).toBe(true);
        expect(document.activeElement).toBe(input);
        const ctrl = document.querySelector<HTMLInputElement>('.modifier + input')!;
        ctrl.click();
        expect(keyboard.getActiveModifiers()).toBe(1);
        ctrl.focus();
        const enter = document.querySelector<HTMLInputElement>('[data-key="enter"] + input')!;
        const down = new PointerEvent('pointerdown', { bubbles: true, cancelable: true });
        enter.dispatchEvent(down);
        expect(down.defaultPrevented).toBe(false);
        enter.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
        enter.click();
        expect(onKeyAction).toHaveBeenCalledExactlyOnceWith('enter', 1);
        expect(keyboard.getActiveModifiers()).toBe(0);
        expect(document.activeElement).toBe(input);
        expect(haptics.trigger).not.toHaveBeenCalled();
    });

    it('keeps desktop controls unchanged', () => {
        vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Desktop');
        install();
        expect(document.querySelector('.native-haptic-switch')).toBeNull();
    });

    it('keeps the Vibration API path unchanged', () => {
        vi.spyOn(navigator, 'vibrate', 'get').mockReturnValue(vi.fn());
        install();
        expect(document.querySelector('.native-haptic-switch')).toBeNull();
    });

    it('does not install overlays when native switches are unsupported', () => {
        Reflect.deleteProperty(HTMLInputElement.prototype, 'switch');
        install();
        expect(document.querySelector('.native-haptic-switch')).toBeNull();
    });
});
