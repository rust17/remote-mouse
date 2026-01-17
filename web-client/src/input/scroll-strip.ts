interface ScrollStripCallbacks {
    onScroll: (sx: number, sy: number) => void;
}

export class ScrollStripHandler {
    private element: HTMLElement;
    private callbacks: ScrollStripCallbacks;

    // State
    private activePointerId: number | null = null;
    private lastY: number = 0;
    private accumulatorY = 0;

    // Config
    public sensitivity = 1;

    constructor(element: HTMLElement, callbacks: ScrollStripCallbacks) {
        this.element = element;
        this.callbacks = callbacks;
        this.initListeners();
    }

    public setSensitivity(val: number) {
        this.sensitivity = val;
    }

    private initListeners() {
        // Prevent default touch actions
        const preventAll = (e: Event) => {
            e.preventDefault();
            e.stopPropagation();
        };

        this.element.addEventListener('touchstart', preventAll, { passive: false });
        this.element.addEventListener('touchmove', preventAll, { passive: false });
        this.element.addEventListener('touchend', preventAll, { passive: false });
        this.element.addEventListener('touchcancel', preventAll, { passive: false });

        this.element.addEventListener('pointerdown', this.handlePointerDown.bind(this));
        this.element.addEventListener('pointermove', this.handlePointerMove.bind(this));
        this.element.addEventListener('pointerup', this.handlePointerUp.bind(this));
        this.element.addEventListener('pointercancel', this.handlePointerUp.bind(this));
    }

    private handlePointerDown(e: PointerEvent) {
        // Stop propagation so the parent touchpad handler doesn't steal capture
        e.stopPropagation();

        if (this.activePointerId !== null) return;

        this.activePointerId = e.pointerId;
        this.lastY = e.clientY;
        this.accumulatorY = 0;

        this.element.classList.add('active');

        try {
            this.element.setPointerCapture(e.pointerId);
        } catch (err) {
            // ignore
        }
    }

    private handlePointerMove(e: PointerEvent) {
        if (this.activePointerId !== e.pointerId) return;

        const rawDy = e.clientY - this.lastY;
        this.lastY = e.clientY;

        // Accumulate movement
        this.accumulatorY += rawDy * this.sensitivity;

        const stepY = Math.trunc(this.accumulatorY);

        if (stepY !== 0) {
            this.accumulatorY -= stepY;
            // Send scroll event (0 for X, stepY for Y)
            this.callbacks.onScroll(0, stepY);
        }
    }

    private handlePointerUp(e: PointerEvent) {
        if (this.activePointerId !== e.pointerId) return;

        this.activePointerId = null;
        this.element.classList.remove('active');

        try {
            this.element.releasePointerCapture(e.pointerId);
        } catch (err) {
            // ignore
        }
    }
}
