import { describe, it, expect, vi, beforeEach } from 'vitest';
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
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));

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

    it('should trigger Right Click (2) on two finger tap', () => {
        // Finger 1 down
        element.dispatchEvent(createEvent('pointerdown', 1, 100, 100));
        // Finger 2 down
        element.dispatchEvent(createEvent('pointerdown', 2, 120, 100));

        // Finger 2 up
        element.dispatchEvent(createEvent('pointerup', 2, 120, 100));
        // Finger 1 up
        element.dispatchEvent(createEvent('pointerup', 1, 100, 100));

        expect(callbacks.onClick).toHaveBeenCalledWith(2);
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
});
