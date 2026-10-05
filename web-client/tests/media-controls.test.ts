import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MediaControls } from '../src/ui/media-controls';
import { encodeMedia, mediaActions, parseMediaMessage } from '../src/core/protocol';

const state = (revision = 1, overrides = {}) => ({
    type: 'media_snapshot', version: 1, revision,
    capabilities: Object.keys(mediaActions), unavailable: {},
    state: { volume: 64, muted: false, playing: null, fullscreen: null }, ...overrides
});

describe('server-backed media controls', () => {
    let media: MediaControls;
    let send: ReturnType<typeof vi.fn>;
    let keepFocus: ReturnType<typeof vi.fn>;
    const button = (action: string) => document.querySelector<HTMLButtonElement>(`[data-media="${action}"]`)!;
    const feedback = () => document.getElementById('media-unavailable')!.textContent;
    const receive = (message: any) => {
        if (message.type === 'media_snapshot' && message.requestId === undefined && message.queryId === undefined) {
            message = { ...message, queryId: send.mock.calls.filter(call => new Uint8Array(call[0])[0] === 8).length };
        }
        media.receive(JSON.stringify(message));
    };
    const packet = () => new DataView(send.mock.calls.at(-1)![0] as ArrayBuffer);
    beforeEach(() => {
        vi.useFakeTimers();
        vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
        document.body.innerHTML = `<div id="app">
          ${Object.keys(mediaActions).filter(a => a !== 'fullscreen').map(a => `<button disabled data-media="${a}"></button>`).join('')}
          <button id="btn-fullscreen" disabled></button>
          <div id="volume-toast" aria-hidden="true"><div class="volume-toast-meter"></div><output id="media-volume"></output></div>
          <p id="media-unavailable"></p><p id="media-reason"></p></div>`;
        send = vi.fn(() => true);
        keepFocus = vi.fn();
        media = new MediaControls(document.getElementById('app')!, send, keepFocus);
    });
    afterEach(() => {
        media.setConnected(false);
        vi.clearAllTimers();
        vi.useRealTimers();
        vi.restoreAllMocks();
        Reflect.deleteProperty(HTMLInputElement.prototype, 'switch');
    });
    const ready = () => { media.setConnected(true); receive(state()); };

    it('encodes exact actions and big-endian request ids, rejects invalid replies', () => {
        expect([...new Uint8Array(encodeMedia('fullscreen', 0x12345678))]).toEqual([7, 7, 0x12, 0x34, 0x56, 0x78]);
        for (const raw of ['bad', '{}', JSON.stringify(state(1, { version: 2 })), JSON.stringify(state(1, { state: { volume: 50, muted: false, playing: true, fullscreen: null } }))]) {
            expect(parseMediaMessage(raw)).toBeNull();
        }
    });

    it('only enables advertised capabilities and renders actual volume and mute', () => {
        media.setConnected(true);
        expect([...new Uint8Array(send.mock.calls[0][0])]).toEqual([8]);
        expect(button('play_pause').disabled).toBe(true);
        receive(state(1, { capabilities: ['mute', 'play_pause'], unavailable: { fullscreen: 'input_permission' }, state: { volume: 27, muted: true, playing: null, fullscreen: null } }));
        expect(button('play_pause').disabled).toBe(false);
        expect(button('volume_up').disabled).toBe(true);
        expect(button('fullscreen').disabled).toBe(true);
        expect(document.getElementById('media-volume')!.textContent).toBe('27%');
        expect(button('mute').getAttribute('aria-pressed')).toBe('true');
        expect(button('play_pause').hasAttribute('aria-pressed')).toBe(false);
        expect(button('fullscreen').hasAttribute('aria-pressed')).toBe(false);
        expect(document.getElementById('media-reason')!.textContent).toContain('辅助功能');
    });

    it('matches receipts and never optimistically toggles state', () => {
        ready();
        button('mute').click();
        const id = packet().getUint32(2, false);
        expect(button('mute').getAttribute('aria-pressed')).toBe('false');
        expect(keepFocus).toHaveBeenCalledOnce();
        receive({ type: 'media_result', version: 1, requestId: id + 1, action: 'mute', status: 'verified' });
        receive({ type: 'media_result', version: 1, requestId: id, action: 'play_pause', status: 'issued' });
        expect(button('mute').disabled).toBe(true);
        receive({ type: 'media_result', version: 1, requestId: id, action: 'mute', status: 'verified' });
        expect(feedback()).toContain('已验证');
        expect(button('mute').getAttribute('aria-pressed')).toBe('false');
        receive(state(2, { requestId: id, state: { volume: 64, muted: true, playing: null, fullscreen: null } }));
        expect(button('mute').getAttribute('aria-pressed')).toBe('true');
        button('play_pause').click();
        const playId = packet().getUint32(2, false);
        receive({ type: 'media_result', version: 1, requestId: playId, action: 'play_pause', status: 'issued' });
        expect(feedback()).toContain('状态未知');
    });

    it('polls only in visible TV and ignores older snapshots', () => {
        ready();
        vi.advanceTimersByTime(1000);
        expect(send).toHaveBeenCalledTimes(1);
        media.setMode('tv');
        receive(state(3));
        vi.advanceTimersByTime(1000);
        receive(state(2, { state: { volume: 10, muted: true, playing: null, fullscreen: null } }));
        expect(document.getElementById('media-volume')!.textContent).toBe('64%');
        const count = send.mock.calls.length;
        media.setMode('computer');
        vi.advanceTimersByTime(1000);
        expect(send).toHaveBeenCalledTimes(count);
        media.setMode('tv');
        vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
        document.dispatchEvent(new Event('visibilitychange'));
        const hiddenCount = send.mock.calls.length;
        vi.advanceTimersByTime(1000);
        expect(send).toHaveBeenCalledTimes(hiddenCount);
    });

    it('times out without retry, discards expired replies, and resets on reconnect', () => {
        ready();
        button('fullscreen').click();
        const id = packet().getUint32(2, false);
        vi.advanceTimersByTime(3000);
        expect(send).toHaveBeenCalledTimes(2);
        expect(feedback()).toContain('结果未知');
        receive({ type: 'media_result', version: 1, requestId: id, action: 'fullscreen', status: 'issued' });
        receive(state(4, { requestId: id, state: { volume: 1, muted: true, playing: null, fullscreen: null } }));
        expect(document.getElementById('media-volume')!.textContent).toBe('64%');
        media.setConnected(false);
        receive(state(5));
        expect(button('fullscreen').disabled).toBe(true);
        media.setConnected(true);
        receive(state(1, { queryId: 1 }));
        expect(button('fullscreen').disabled).toBe(false);
        button('fullscreen').click();
        expect(packet().getUint32(2, false)).not.toBe(id);
    });

    it('leaves buttons disabled with old servers and expires stale capabilities', () => {
        media.setConnected(true);
        media.setMode('tv');
        vi.advanceTimersByTime(5000);
        expect(button('play_pause').disabled).toBe(true);
        receive(state(1, { queryId: 1 })); // Original query expired; discard it.
        expect(button('play_pause').disabled).toBe(true);
        receive(state(2)); // Fresh response to replacement query.
        expect(button('play_pause').disabled).toBe(false);
        media.setMode('computer');
        vi.advanceTimersByTime(4000);
        expect(button('play_pause').disabled).toBe(true);
        expect(document.getElementById('media-volume')!.textContent).toBe('—');
    });

    it('installs iOS haptics after capability arrives and forwards once with focus', () => {
        vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('iPhone');
        Object.defineProperty(HTMLInputElement.prototype, 'switch', { configurable: true, value: false });
        ready();
        const overlay = button('mute').parentElement!.querySelector<HTMLInputElement>('input')!;
        overlay.click();
        expect(send).toHaveBeenCalledTimes(2);
        expect(keepFocus).toHaveBeenCalledOnce();
        expect(overlay.disabled).toBe(true);
        overlay.click();
        expect(send).toHaveBeenCalledTimes(2);
        media.setConnected(false);
        expect(overlay.disabled).toBe(true);
    });
    it('keeps available iOS controls usable when neighboring buttons are disabled', () => {
        vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('iPhone');
        Object.defineProperty(HTMLInputElement.prototype, 'switch', { configurable: true, value: false });
        media.setConnected(true);
        receive(state(1, { capabilities: ['mute'] }));
        const overlay = button('mute').parentElement!.querySelector<HTMLInputElement>('input')!;
        overlay.click();
        const id = packet().getUint32(2, false);
        receive({ type: 'media_result', version: 1, requestId: id, action: 'mute', status: 'verified' });
        expect(overlay.disabled).toBe(false);
        overlay.click();
        expect(send).toHaveBeenCalledTimes(3);
    });

    it('shows the volume HUD only after a verified audio receipt and measured snapshot', () => {
        media.setMode('tv');
        ready();
        const toast = document.getElementById('volume-toast')!;
        expect(toast.classList.contains('visible')).toBe(false);
        button('volume_up').click();
        const id = packet().getUint32(2, false);
        expect(toast.classList.contains('visible')).toBe(false);
        expect(document.getElementById('media-volume')!.textContent).toBe('64%');
        receive({ type: 'media_result', version: 1, requestId: id, action: 'volume_up', status: 'verified' });
        expect(toast.classList.contains('visible')).toBe(false);
        receive(state(2, { requestId: id, state: { volume: 69, muted: false, playing: null, fullscreen: null } }));
        expect(toast.classList.contains('visible')).toBe(true);
        expect(toast.style.getPropertyValue('--volume-level')).toBe('69%');
        media.setMode('computer');
        expect(toast.classList.contains('visible')).toBe(false);
    });

    it('does not show failed or expired adjustments and dismisses on hide or disconnect', () => {
        media.setMode('tv');
        ready();
        const toast = document.getElementById('volume-toast')!;
        button('mute').click();
        const failedId = packet().getUint32(2, false);
        receive({ type: 'media_result', version: 1, requestId: failedId, action: 'mute', status: 'error', errorCode: 'audio_failed' });
        receive(state(2, { requestId: failedId }));
        expect(toast.classList.contains('visible')).toBe(false);
        button('mute').click();
        const id = packet().getUint32(2, false);
        receive({ type: 'media_result', version: 1, requestId: id, action: 'mute', status: 'verified' });
        receive(state(3, { requestId: id, state: { volume: 64, muted: true, playing: null, fullscreen: null } }));
        expect(toast.dataset.volumeLevel).toBe('muted');
        expect(toast.classList.contains('visible')).toBe(true);
        vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
        document.dispatchEvent(new Event('visibilitychange'));
        expect(toast.classList.contains('visible')).toBe(false);
        vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
        document.dispatchEvent(new Event('visibilitychange'));
        button('volume_down').click();
        const expiredId = packet().getUint32(2, false);
        vi.advanceTimersByTime(3000);
        receive({ type: 'media_result', version: 1, requestId: expiredId, action: 'volume_down', status: 'verified' });
        receive(state(4, { requestId: expiredId }));
        expect(toast.classList.contains('visible')).toBe(false);
        media.setConnected(false);
        expect(toast.getAttribute('aria-hidden')).toBe('true');
    });

});
