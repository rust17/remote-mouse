import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VolumeToast } from '../src/ui/volume-toast';

const state = (volume: number | null, muted: boolean | null = false) => ({ volume, muted, playing: null, fullscreen: null });

describe('volume toast', () => {
    let element: HTMLElement;
    let toast: VolumeToast;
    beforeEach(() => {
        vi.useFakeTimers();
        document.body.innerHTML = '<div id="volume-toast" aria-hidden="true"><div class="volume-toast-meter"></div><output id="media-volume"></output></div>';
        element = document.getElementById('volume-toast')!;
        toast = new VolumeToast(element);
    });
    afterEach(() => { toast.hide(); vi.useRealTimers(); });

    it('updates measured values without displaying a toast during polling', () => {
        toast.update(state(33));
        expect(element.classList.contains('visible')).toBe(false);
        expect(element.style.getPropertyValue('--volume-level')).toBe('33%');
        expect(element.dataset.volumeLevel).toBe('low');
        toast.show();
        expect(element.getAttribute('aria-hidden')).toBe('false');
        vi.advanceTimersByTime(1600);
        expect(element.getAttribute('aria-hidden')).toBe('true');
    });

    it('keeps one toast and extends its lifetime only when shown again', () => {
        toast.update(state(50));
        toast.show();
        vi.advanceTimersByTime(1000);
        toast.update(state(55));
        toast.show();
        vi.advanceTimersByTime(1000);
        expect(element.classList.contains('visible')).toBe(true);
        toast.update(state(60)); // A background query must not reset the dismissal timer.
        vi.advanceTimersByTime(600);
        expect(element.classList.contains('visible')).toBe(false);
    });

    it('shows actual mute and zero state, clamps the meter while retaining measured percent', () => {
        toast.update(state(69, true));
        toast.show();
        expect(element.dataset.volumeLevel).toBe('muted');
        expect(document.getElementById('media-volume')!.textContent).toBe('69%');
        toast.update(state(0));
        expect(element.dataset.volumeLevel).toBe('off');
        toast.update(state(120));
        expect(element.style.getPropertyValue('--volume-level')).toBe('100%');
        expect(document.getElementById('media-volume')!.textContent).toBe('120%');
        toast.update(state(null, null));
        expect(element.getAttribute('aria-hidden')).toBe('true');
        toast.show();
        expect(element.classList.contains('visible')).toBe(false);
    });
});
