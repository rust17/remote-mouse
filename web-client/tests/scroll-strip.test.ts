import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ScrollStripHandler } from '../src/input/scroll-strip';

describe('ScrollStripHandler', () => {
    let element: HTMLElement;
    let handler: ScrollStripHandler;
    let onScroll: any;

    beforeEach(() => {
        element = document.createElement('div');
        onScroll = vi.fn();

        // Mock setPointerCapture and releasePointerCapture as they are not implemented in JSDOM
        element.setPointerCapture = vi.fn();
        element.releasePointerCapture = vi.fn();

        handler = new ScrollStripHandler(element, { onScroll });
    });

    it('should initialize with default sensitivity', () => {
        expect(handler.sensitivity).toBe(1);
    });

    it('should handle pointer down', () => {
        const stopPropagation = vi.fn();
        const event = new PointerEvent('pointerdown', {
            pointerId: 1,
            clientY: 100,
            bubbles: true
        });
        event.stopPropagation = stopPropagation;

        element.dispatchEvent(event);

        expect(stopPropagation).toHaveBeenCalled();
        expect(element.classList.contains('active')).toBe(true);
        expect(element.setPointerCapture).toHaveBeenCalledWith(1);
    });

    it('should ignore other pointers when active', () => {
        // First pointer down
        const event1 = new PointerEvent('pointerdown', { pointerId: 1, clientY: 100 });
        element.dispatchEvent(event1);

        // Second pointer down
        const event2 = new PointerEvent('pointerdown', { pointerId: 2, clientY: 100 });
        event2.stopPropagation = vi.fn(); // To check if it stops propagation
        element.dispatchEvent(event2);

        // Should ignore second pointer (no capture call for it)
        expect(element.setPointerCapture).toHaveBeenCalledTimes(1);
        expect(element.setPointerCapture).toHaveBeenCalledWith(1);
    });

    it('should trigger onScroll when moved vertically', () => {
        // Down
        element.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientY: 100 }));

        // Move
        element.dispatchEvent(new PointerEvent('pointermove', { pointerId: 1, clientY: 110 }));

        // 10px move * sensitivity 1 = 10 scroll units
        expect(onScroll).toHaveBeenCalledWith(0, 10);
    });

    it('should accumulate small movements based on sensitivity', () => {
        handler.setSensitivity(0.5);

        // Down
        element.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientY: 100 }));

        // Move 1px -> 0.5 scroll units (truncates to 0, no event)
        element.dispatchEvent(new PointerEvent('pointermove', { pointerId: 1, clientY: 101 }));
        expect(onScroll).not.toHaveBeenCalled();

        // Move another 1px -> total 2px -> 1.0 scroll units
        element.dispatchEvent(new PointerEvent('pointermove', { pointerId: 1, clientY: 102 }));
        expect(onScroll).toHaveBeenCalledWith(0, 1);
    });

    it('should handle negative scrolling (upwards)', () => {
        // Down
        element.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientY: 100 }));

        // Move Up
        element.dispatchEvent(new PointerEvent('pointermove', { pointerId: 1, clientY: 90 }));

        expect(onScroll).toHaveBeenCalledWith(0, -10);
    });

    it('should cleanup on pointer up', () => {
        // Down
        element.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientY: 100 }));
        expect(element.classList.contains('active')).toBe(true);

        // Up
        element.dispatchEvent(new PointerEvent('pointerup', { pointerId: 1, clientY: 100 }));

        expect(element.classList.contains('active')).toBe(false);
        expect(element.releasePointerCapture).toHaveBeenCalledWith(1);
    });

    it('should ignore moves from other pointers', () => {
        // Down Pointer 1
        element.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientY: 100 }));

        // Move Pointer 2
        element.dispatchEvent(new PointerEvent('pointermove', { pointerId: 2, clientY: 110 }));

        expect(onScroll).not.toHaveBeenCalled();
    });

    it('should handle pointer cancel like pointer up', () => {
        // Down
        element.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientY: 100 }));

        // Cancel
        element.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 1, clientY: 100 }));

        expect(element.classList.contains('active')).toBe(false);
        expect(element.releasePointerCapture).toHaveBeenCalledWith(1);
    });
});
