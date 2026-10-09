import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TouchpadHandler } from '../src/input/touchpad';

describe('TouchpadHandler', () => {
    let element: HTMLElement;
    let handler: TouchpadHandler;
    let callbacks: any;

    beforeEach(() => {
        // Create a dummy element
        element = document.createElement('div');
        // JSDOM doesn't fully implement setPointerCapture/releasePointerCapture, so we stub them
        element.setPointerCapture = vi.fn();
        element.releasePointerCapture = vi.fn();

        callbacks = {
            onMove: vi.fn(),
            onClick: vi.fn(),
            onScroll: vi.fn(),
            onDrag: vi.fn()
        };

        handler = new TouchpadHandler(element, callbacks);
    });

    afterEach(() => {
        handler.resetState();
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    // Helper to create events
    const createEvent = (type: string, id: number, x: number, y: number) => {
        return new PointerEvent(type, {
            pointerId: id,
            clientX: x,
            clientY: y,
            bubbles: true
        });
    };

    it('should trigger Left Click (1) on single tap', () => {
        vi.useFakeTimers();
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));

        expect(callbacks.onClick).not.toHaveBeenCalled();
        vi.advanceTimersByTime(299);
        expect(callbacks.onClick).not.toHaveBeenCalled();
        vi.advanceTimersByTime(1);
        expect(callbacks.onClick).toHaveBeenCalledWith(1);
        expect(callbacks.onMove).not.toHaveBeenCalled();
    });

    it('should trigger Move when moved significantly', () => {
        handler.setSensitivity(1); // Simplify calc

        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));

        // Small move (ignored by hasMoved check > 1, but might accumulate?)
        // The code: abs(rawDx) > 1 sets hasMoved=true.
        // Let's move 10px
        element.dispatchEvent(createEvent('pointermove', 1, 110, 100));

        // rawDx = 10. sensitivity = 1. accumulator = 10.
        expect(callbacks.onMove).toHaveBeenCalledWith(10, 0);

        element.dispatchEvent(createEvent('pointerup', 1, 110, 100));

        // Should NOT click because it moved
        expect(callbacks.onClick).not.toHaveBeenCalled();
    });

    it.each(['computer', 'tv'] as const)('%s mode sends one right click on a two-finger tap', mode => {
        handler.setMode(mode);
        // Finger 1 down
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        // Finger 2 down
        element.dispatchEvent(createEvent('pointerdown', 2, 120, 100));

        // Finger 2 up
        element.dispatchEvent(createEvent('pointerup', 2, 120, 100));
        // Finger 1 up
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));

        expect(callbacks.onClick).toHaveBeenCalledExactlyOnceWith(2);
    });

    it('should trigger Scroll on two finger move', () => {
        // Finger 1 down
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        // Finger 2 down
        element.dispatchEvent(createEvent('pointerdown', 2, 120, 100));

        // Move Finger 1
        element.dispatchEvent(createEvent('pointermove', 1, 100, 110)); // dy = 10

        expect(callbacks.onScroll).toHaveBeenCalledWith(0, 10);
        expect(callbacks.onMove).not.toHaveBeenCalled();
    });

    it('should respect scroll sensitivity and accumulation', () => {
        handler.setScrollSensitivity(0.5);

        // Finger 1 & 2 down
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerdown', 2, 120, 100));

        // Move 1px (dy=1 * 0.5 = 0.5) -> No scroll event yet
        element.dispatchEvent(createEvent('pointermove', 1, 100, 101));
        expect(callbacks.onScroll).not.toHaveBeenCalled();

        // Move another 1px (total dy=2 * 0.5 = 1.0) -> Scroll event (0, 1)
        element.dispatchEvent(createEvent('pointermove', 1, 100, 102));
        expect(callbacks.onScroll).toHaveBeenCalledWith(0, 1);
    });

    it('should trigger Drag start/end on three fingers', () => {
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerdown', 2, 110, 100));

        expect(callbacks.onDrag).not.toHaveBeenCalled();

        element.dispatchEvent(createEvent('pointerdown', 3, 120, 100));

        expect(callbacks.onDrag).toHaveBeenCalledWith(true);

        // Release one
        element.dispatchEvent(createEvent('pointerup', 3, 120, 100));

        expect(callbacks.onDrag).toHaveBeenCalledWith(false);
    });

    it('should prevent default on touch and contextmenu events', () => {
        const events = ['touchstart', 'touchmove', 'touchend', 'touchcancel', 'contextmenu'];

        events.forEach(type => {
            const event = new Event(type, { bubbles: true, cancelable: true });
            const preventSpy = vi.spyOn(event, 'preventDefault');
            const stopSpy = vi.spyOn(event, 'stopPropagation');

            element.dispatchEvent(event);

            expect(preventSpy).toHaveBeenCalled();
            expect(stopSpy).toHaveBeenCalled();
        });
    });

    it.each(['computer', 'tv'] as const)('%s mode sends two left clicks when both taps finish without dragging', mode => {
        vi.useFakeTimers();
        handler.setMode(mode);
        const tap = () => {
            element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
            element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        };
        tap();
        expect(callbacks.onClick).not.toHaveBeenCalled();
        vi.advanceTimersByTime(100);
        tap();
        expect(callbacks.onClick.mock.calls).toEqual([[1], [1]]);
        handler.setMode(mode === 'tv' ? 'computer' : 'tv');
        vi.advanceTimersByTime(300);
        expect(callbacks.onClick.mock.calls).toEqual([[1], [1]]);
    });

    it.each(['computer', 'tv'] as const)('%s mode drags on tap, then touch and slide, releasing on lift', mode => {
        vi.useFakeTimers();
        handler.setMode(mode);
        handler.setSensitivity(1);
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        expect(callbacks.onClick).not.toHaveBeenCalled();

        vi.advanceTimersByTime(100);
        element.dispatchEvent(createEvent('pointerdown', 2, 101, 100));
        // Holding alone and small tap jitter must not press the mouse button.
        vi.advanceTimersByTime(1000);
        element.dispatchEvent(createEvent('pointermove', 2, 104, 100));
        expect(callbacks.onDrag).not.toHaveBeenCalled();
        expect(callbacks.onMove).not.toHaveBeenCalled();

        element.dispatchEvent(createEvent('pointermove', 2, 111, 100));
        expect(callbacks.onDrag).toHaveBeenCalledExactlyOnceWith(true);
        expect(callbacks.onMove).toHaveBeenCalledExactlyOnceWith(10, 0);
        expect(callbacks.onDrag.mock.invocationCallOrder[0])
            .toBeLessThan(callbacks.onMove.mock.invocationCallOrder[0]);
        element.dispatchEvent(createEvent('pointermove', 2, 116, 103));
        expect(callbacks.onMove.mock.calls).toEqual([[10, 0], [5, 3]]);
        element.dispatchEvent(createEvent('pointerup', 2, 116, 103));
        expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
        vi.advanceTimersByTime(1000);
        expect(callbacks.onClick).not.toHaveBeenCalled();
        expect(callbacks.onScroll).not.toHaveBeenCalled();
    });

    it('keeps a slightly shaky second tap as a double click', () => {
        vi.useFakeTimers();
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        vi.advanceTimersByTime(100);
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 103, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 103, 100));
        expect(callbacks.onClick.mock.calls).toEqual([[1], [1]]);
        expect(callbacks.onMove).not.toHaveBeenCalled();
        expect(callbacks.onDrag).not.toHaveBeenCalled();
    });

    it('does not reuse a completed double click as the first tap of another drag', () => {
        vi.useFakeTimers();
        for (let tap = 0; tap < 2; tap++) {
            element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
            element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
            vi.advanceTimersByTime(100);
        }
        expect(callbacks.onClick.mock.calls).toEqual([[1], [1]]);
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 110, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 110, 100));
        expect(callbacks.onDrag).not.toHaveBeenCalled();
        expect(callbacks.onMove).toHaveBeenCalledExactlyOnceWith(20, 0);
    });

    it.each(['mode', 'reset', 'pagehide', 'hidden'])('%s cancels a pending first tap', interruption => {
        vi.useFakeTimers();
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        if (interruption === 'mode') handler.setMode('tv');
        else if (interruption === 'reset') handler.resetState();
        else if (interruption === 'pagehide') window.dispatchEvent(new Event('pagehide'));
        else {
            vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
            document.dispatchEvent(new Event('visibilitychange'));
        }
        vi.advanceTimersByTime(1000);
        expect(callbacks.onClick).not.toHaveBeenCalled();
    });

    it.each(['pointercancel', 'lostpointercapture'])('%s during the second touch discards the pending click', type => {
        vi.useFakeTimers();
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        vi.advanceTimersByTime(100);
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent(type, 1, 100, 100));
        vi.advanceTimersByTime(1000);
        expect(callbacks.onClick).not.toHaveBeenCalled();
        expect(callbacks.onDrag).not.toHaveBeenCalled();
    });

    it.each([0.5, 1, 3])('recognizes tap dragging after %s pixels of first-tap jitter', jitter => {
        vi.useFakeTimers();
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 100 + jitter, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100 + jitter, 100));
        expect(callbacks.onClick).not.toHaveBeenCalled();
        expect(callbacks.onMove).not.toHaveBeenCalled();

        vi.advanceTimersByTime(100);
        element.dispatchEvent(createEvent('pointerdown', 2, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 2, 110, 100));
        element.dispatchEvent(createEvent('pointerup', 2, 110, 100));
        expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
        expect(callbacks.onMove).toHaveBeenCalledExactlyOnceWith(20, 0);
        expect(callbacks.onClick).not.toHaveBeenCalled();
    });

    it('preserves the first movement and subsequent small movements after leaving the tap threshold', () => {
        handler.setSensitivity(0.5);
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 103, 100));
        expect(callbacks.onMove).not.toHaveBeenCalled();
        element.dispatchEvent(createEvent('pointermove', 1, 105, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 106, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 106, 100));
        expect(callbacks.onMove.mock.calls).toEqual([[2, 0], [1, 0]]);
        expect(callbacks.onClick).not.toHaveBeenCalled();
        expect(callbacks.onDrag).not.toHaveBeenCalled();
    });

    it.each([
        { name: 'too late', firstHold: 0, gap: 301, secondX: 100 },
        { name: 'too far away', firstHold: 0, gap: 100, secondX: 125 },
        { name: 'after a long first press', firstHold: 301, gap: 100, secondX: 100 }
    ])('moves normally when the next touch is $name', ({ firstHold, gap, secondX }) => {
        vi.useFakeTimers();
        handler.setSensitivity(1);
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        vi.advanceTimersByTime(firstHold);
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        vi.advanceTimersByTime(gap);
        element.dispatchEvent(createEvent('pointerdown', 1, secondX, 100));
        element.dispatchEvent(createEvent('pointermove', 1, secondX + 10, 100));
        element.dispatchEvent(createEvent('pointerup', 1, secondX + 10, 100));
        expect(callbacks.onMove).toHaveBeenCalledExactlyOnceWith(10, 0);
        expect(callbacks.onDrag).not.toHaveBeenCalled();
        expect(callbacks.onClick).toHaveBeenCalledExactlyOnceWith(1);
    });

    it('preserves movement and fractional sensitivity when starting a tap drag', () => {
        handler.setSensitivity(0.5);
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 103, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 105, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 106, 100));
        expect(callbacks.onMove.mock.calls).toEqual([[2, 0], [1, 0]]);
        expect(callbacks.onDrag).toHaveBeenCalledExactlyOnceWith(true);
    });

    it.each(['tap', 'scroll'])('allows a two-finger %s after the first tap', gesture => {
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerdown', 2, 120, 100));
        if (gesture === 'scroll') {
            element.dispatchEvent(createEvent('pointermove', 1, 100, 110));
            expect(callbacks.onScroll).toHaveBeenCalledExactlyOnceWith(0, 10);
        }
        element.dispatchEvent(createEvent('pointerup', 2, 120, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        expect(callbacks.onClick.mock.calls).toEqual(gesture === 'tap' ? [[1], [2]] : [[1]]);
        expect(callbacks.onDrag).not.toHaveBeenCalled();
        expect(callbacks.onMove).not.toHaveBeenCalled();
    });

    it('adding fingers releases a tap drag and cancels the remaining gesture', () => {
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 110, 100));
        callbacks.onMove.mockClear();
        element.dispatchEvent(createEvent('pointerdown', 2, 120, 100));
        element.dispatchEvent(createEvent('pointerdown', 3, 130, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 110, 110));
        for (const id of [3, 2, 1]) element.dispatchEvent(createEvent('pointerup', id, 110, 110));
        expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
        expect(callbacks.onClick).not.toHaveBeenCalled();
        expect(callbacks.onScroll).not.toHaveBeenCalled();
        expect(callbacks.onMove).not.toHaveBeenCalled();
    });

    it.each(['pointercancel', 'lostpointercapture', 'mode', 'reset', 'pagehide', 'hidden'])
       ('%s interrupts a tap drag and releases the mouse button exactly once', interruption => {
            element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
            element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
            element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
            element.dispatchEvent(createEvent('pointermove', 1, 110, 100));
            callbacks.onMove.mockClear();
            if (interruption === 'mode') handler.setMode('tv');
            else if (interruption === 'reset') handler.resetState();
            else if (interruption === 'pagehide') window.dispatchEvent(new Event('pagehide'));
            else if (interruption === 'hidden') {
                vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
                document.dispatchEvent(new Event('visibilitychange'));
            } else element.dispatchEvent(createEvent(interruption, 1, 110, 100));
            element.dispatchEvent(createEvent('pointermove', 1, 120, 100));
            element.dispatchEvent(createEvent('pointerup', 1, 120, 100));
            expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
            expect(callbacks.onClick).not.toHaveBeenCalled();
            expect(callbacks.onMove).not.toHaveBeenCalled();
        });

    it('resetting forgets the first tap', () => {
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        handler.resetState();
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointermove', 1, 110, 100));
        expect(callbacks.onDrag).not.toHaveBeenCalled();
        expect(callbacks.onMove).toHaveBeenCalledExactlyOnceWith(20, 0);
    });

    it('switching modes cancels an unfinished tap and releases dragging', () => {
        handler.setMode('tv');
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        handler.setMode('computer');
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        expect(callbacks.onClick).not.toHaveBeenCalled();
        for (const id of [1, 2, 3]) element.dispatchEvent(createEvent('pointerdown', id, 100, 100));
        handler.setMode('tv');
        expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
    });

    it('three-finger release never becomes a right or left click', () => {
        for (const id of [1, 2, 3]) element.dispatchEvent(createEvent('pointerdown', id, 100, 100));
        for (const id of [3, 2, 1]) element.dispatchEvent(createEvent('pointerup', id, 100, 100));
        expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
        expect(callbacks.onClick).not.toHaveBeenCalled();
    });

    it('cancelling one finger prevents clicks from the remaining fingers', () => {
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerdown', 2, 110, 100));
        element.dispatchEvent(createEvent('pointercancel', 2, 110, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));
        expect(callbacks.onClick).not.toHaveBeenCalled();
    });

    it('page hiding releases the remote mouse button and stops subsequent movement', () => {
        for (const id of [1, 2, 3]) element.dispatchEvent(createEvent('pointerdown', id, 100, 100));
        vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
        document.dispatchEvent(new Event('visibilitychange'));
        element.dispatchEvent(createEvent('pointermove', 1, 110, 100));
        expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
        expect(callbacks.onMove).not.toHaveBeenCalled();
        expect(element.releasePointerCapture).toHaveBeenCalledTimes(3);
    });

    it('losing pointer capture releases dragging without synthesizing clicks', () => {
        for (const id of [1, 2, 3]) element.dispatchEvent(createEvent('pointerdown', id, 100, 100));
        element.dispatchEvent(createEvent('lostpointercapture', 3, 100, 100));
        for (const id of [2, 1]) element.dispatchEvent(createEvent('pointerup', id, 100, 100));
        expect(callbacks.onDrag.mock.calls).toEqual([[true], [false]]);
        expect(callbacks.onClick).not.toHaveBeenCalled();
    });
});
