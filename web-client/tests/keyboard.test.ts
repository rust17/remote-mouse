import html from '../index.html?raw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WebHaptics } from 'web-haptics';
import { KeyboardHandler } from '../src/input/keyboard';
import { ControlModeController } from '../src/ui/control-mode';
import { i18n } from '../src/core/i18n';

describe('shared keyboard and scene controls', () => {
    let keyboard: KeyboardHandler;
    let onText: ReturnType<typeof vi.fn>;
    let onKeyAction: ReturnType<typeof vi.fn>;
    const get = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id)! as T;
    const click = (selector: string) => document.querySelector<HTMLButtonElement>(selector)!.click();

    beforeEach(() => {
        localStorage.clear();
        window.history.replaceState(null, '', '/');
        document.body.innerHTML = html;
        i18n.setLanguage('zh');
        onText = vi.fn(() => true);
        onKeyAction = vi.fn();
        keyboard = new KeyboardHandler(get<HTMLInputElement>('keyboard-input'), get('btn-keyboard'),
            get('controls-area'), { onText, onKeyAction }, { trigger: vi.fn() } as unknown as WebHaptics,
            { panel: get('input-panel'), composer: get('composer'), draft: get<HTMLInputElement>('draft-input'),
                send: get<HTMLButtonElement>('btn-send'), feedback: get('input-feedback'),
                modeButtons: document.querySelectorAll<HTMLButtonElement>('[data-input-mode]') });
    });
    afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ''; });

    it('sends a composition once even when followed by a final input event', () => {
        vi.useFakeTimers();
        const input = get<HTMLInputElement>('keyboard-input');
        keyboard.toggle(true);
        input.dispatchEvent(new CompositionEvent('compositionstart'));
        input.dispatchEvent(new InputEvent('input', { data: '中文', isComposing: true }));
        input.dispatchEvent(new CompositionEvent('compositionend', { data: '中文' }));
        input.dispatchEvent(new InputEvent('input', { data: '中文', inputType: 'insertText' }));
        expect(onText).toHaveBeenCalledExactlyOnceWith('中文');
        vi.runAllTimers();
        input.dispatchEvent(new InputEvent('input', { data: '中文' }));
        expect(onText).toHaveBeenCalledTimes(2);
    });

    it('combines modifiers for live single characters and resets them after use', () => {
        keyboard.toggle(true);
        click('[data-modifier="ctrl"]'); click('[data-modifier="shift"]');
        get('keyboard-input').dispatchEvent(new InputEvent('input', { data: 'C' }));
        expect(onKeyAction).toHaveBeenCalledExactlyOnceWith('c', 3);
        expect(onText).not.toHaveBeenCalled();
        expect(keyboard.getActiveModifiers()).toBe(0);
        expect(document.querySelector('[data-modifier="ctrl"]')!.getAttribute('aria-pressed')).toBe('false');
    });

    it('handles deletion from a software keyboard without keydown', () => {
        const event = new InputEvent('beforeinput', { inputType: 'deleteContentBackward', cancelable: true });
        get('keyboard-input').dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
        expect(onKeyAction).toHaveBeenCalledExactlyOnceWith('backspace', 0);
    });

    it('preserves drafts across modes and input methods; remote keys do not edit the draft', () => {
        new ControlModeController(get('app'), () => {
            keyboard.resetModifiers();
            keyboard.close();
        }, () => keyboard.restoreFocus());
        keyboard.toggle(true);
        click('[data-input-mode="draft"]');
        const draft = get<HTMLInputElement>('draft-input');
        draft.value = '待发送中文';
        click('#mode-tv');
        expect(window.location.search).toBe('?mode=tv');
        expect(get('fn-panel').hidden).toBe(true);
        expect(get('media-panel').hidden).toBe(false);
        expect(document.activeElement).not.toBe(draft);
        expect(keyboard.isOpenState()).toBe(false);
        expect(get('btn-keyboard').classList.contains('active')).toBe(false);
        keyboard.toggle(true);
        for (const key of ['enter', 'backspace', 'select_all', 'esc']) click(`#tv-input-keys [data-key="${key}"]`);
        expect(onKeyAction.mock.calls).toEqual([['enter', 0], ['backspace', 0], ['select_all', 0], ['esc', 0]]);
        draft.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', cancelable: true }));
        expect(onText).not.toHaveBeenCalled();
        expect(draft.value).toBe('待发送中文');
        click('[data-input-mode="realtime"]'); click('[data-input-mode="draft"]'); click('#mode-computer');
        expect(draft.value).toBe('待发送中文');
        expect(keyboard.isOpenState()).toBe(false);
        keyboard.toggle(true);
        click('#btn-send');
        expect(onText).toHaveBeenCalledExactlyOnceWith('待发送中文');
        expect(draft.value).toBe('');
    });

    it('retains a draft when disconnected and while IME composition is active', () => {
        keyboard.toggle(true); click('[data-input-mode="draft"]');
        const draft = get<HTMLInputElement>('draft-input');
        draft.value = '草稿';
        draft.dispatchEvent(new CompositionEvent('compositionstart'));
        click('#btn-send');
        expect(onText).not.toHaveBeenCalled();
        draft.dispatchEvent(new CompositionEvent('compositionend'));
        onText.mockReturnValue(false);
        click('#btn-send');
        expect(draft.value).toBe('草稿');
        expect(get('input-feedback').textContent).toBe('连接断开，草稿未发送');
    });

    it('uses the URL on startup and never sends media or fabricates media state', () => {
        window.history.replaceState(null, '', '/?mode=tv&keep=1');
        const onMode = vi.fn();
        new ControlModeController(get('app'), onMode, () => keyboard.restoreFocus());
        expect(onMode).toHaveBeenCalledExactlyOnceWith('tv');
        click('#mode-tv');
        expect(onMode).toHaveBeenCalledTimes(1);
        const buttons = document.querySelectorAll<HTMLButtonElement>('[data-media], #btn-fullscreen');
        expect(buttons).toHaveLength(7);
        buttons.forEach(button => { expect(button.disabled).toBe(true); button.click(); });
        expect(onKeyAction).not.toHaveBeenCalled(); expect(onText).not.toHaveBeenCalled();
        expect(document.querySelector('[data-media="mute"]')!.hasAttribute('aria-pressed')).toBe(false);
        expect(document.body.textContent).not.toContain('50%');
        click('#mode-computer');
        expect(window.location.search).toBe('?mode=computer&keep=1');
        expect(get('media-panel').hidden).toBe(true);
        expect(get('btn-fullscreen').hidden).toBe(true);
    });

    it('keeps the input closed after returning from settings and restores it only on explicit reopen', () => {
        keyboard.toggle(true);
        keyboard.close();
        keyboard.suspendFocus();
        click('[data-input-mode="draft"]');
        expect(document.activeElement).not.toBe(get('draft-input'));
        keyboard.resumeFocus();
        expect(document.activeElement).not.toBe(get('draft-input'));
        expect(keyboard.isOpenState()).toBe(false);
        expect(get('input-panel').hidden).toBe(true);
        keyboard.toggle(true);
        expect(document.activeElement).toBe(get('draft-input'));
        i18n.setLanguage('en');
        expect(get('btn-keyboard').getAttribute('aria-label')).toBe('Close keyboard');
        expect(document.querySelector('[data-key="select_all"]')!.textContent).toBe('Select all');
        expect(document.documentElement.lang).toBe('en');
    });
});
