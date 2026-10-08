export type ControlMode = 'computer' | 'tv';

const DOUBLE_TAP_INTERVAL = 300;
const DOUBLE_TAP_DISTANCE = 24;
const TAP_MOVEMENT_THRESHOLD = 4;

interface TouchpadCallbacks {
    onMove: (dx: number, dy: number) => void;
    onClick: (button: number) => void;
    onScroll: (sx: number, sy: number) => void;
    onDrag: (active: boolean) => void;
}

export class TouchpadHandler {
    private pointers = new Map<number, { x: number; y: number; startX: number; startY: number }>();
    private dragPointerCount = 0;
    private lastTap: { x: number; y: number; time: number } | null = null;
    private tapStartedAt = 0;
    private doubleTapCandidate = false;
    private hasMoved = false;
    private maxPointers = 0;
    private cancelled = false;
    private mode: ControlMode = 'computer';
    private accumulatorX = 0;
    private accumulatorY = 0;
    private scrollAccumulatorX = 0;
    private scrollAccumulatorY = 0;
    public sensitivity = 2;
    public scrollSensitivity = 1;
    private element: HTMLElement;
    private callbacks: TouchpadCallbacks;

    constructor(element: HTMLElement, callbacks: TouchpadCallbacks) {
        this.element = element;
        this.callbacks = callbacks;
        this.initListeners();
    }

    public setSensitivity(val: number) { this.sensitivity = val; }
    public setScrollSensitivity(val: number) { this.scrollSensitivity = val; }

    public setMode(mode: ControlMode) {
        if (mode === this.mode) return;
        this.resetState();
        this.mode = mode;
    }

    private initListeners() {
        const preventAll = (e: Event) => { e.preventDefault(); e.stopPropagation(); };
        for (const type of ['touchstart', 'touchmove', 'touchend', 'touchcancel', 'contextmenu',
            'gesturestart', 'gesturechange', 'gestureend']) {
            this.element.addEventListener(type, preventAll, { passive: false });
        }
        this.element.addEventListener('pointerdown', e => this.handlePointerDown(e));
        this.element.addEventListener('pointermove', e => this.handlePointerMove(e));
        this.element.addEventListener('pointerup', e => this.handlePointerUp(e));
        this.element.addEventListener('pointercancel', e => this.handlePointerUp(e));
        this.element.addEventListener('lostpointercapture', e => this.handlePointerUp(e));
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) this.resetState();
        });
        window.addEventListener('pagehide', () => this.resetState());
    }

    public resetState() {
        // Release before clearing the drag flag, including interrupted gestures.
        if (this.dragPointerCount) this.callbacks.onDrag(false);
        this.dragPointerCount = 0;
        this.lastTap = null;
        this.doubleTapCandidate = false;
        const ids = [...this.pointers.keys()];
        this.pointers.clear();
        for (const id of ids) {
            try { this.element.releasePointerCapture(id); } catch { /* Capture may already be lost. */ }
        }
        this.hasMoved = false;
        this.maxPointers = 0;
        this.cancelled = false;
        this.clearAccumulators();
    }

    private clearAccumulators() {
        this.accumulatorX = this.accumulatorY = 0;
        this.scrollAccumulatorX = this.scrollAccumulatorY = 0;
    }

    private handlePointerDown(e: PointerEvent) {
        e.preventDefault(); // Keep the software keyboard focused while using the pad.
        if (this.pointers.size === 0) {
            this.hasMoved = false;
            this.maxPointers = 0;
            this.cancelled = false;
            this.tapStartedAt = Date.now();
            this.doubleTapCandidate = this.lastTap !== null
                && this.tapStartedAt - this.lastTap.time <= DOUBLE_TAP_INTERVAL
                && Math.hypot(e.clientX - this.lastTap.x, e.clientY - this.lastTap.y) <= DOUBLE_TAP_DISTANCE;
            this.lastTap = null;
        } else {
            this.doubleTapCandidate = false;
            // An extra finger interrupts a single-finger drag until all fingers lift.
            if (this.dragPointerCount === 1) {
                this.dragPointerCount = 0;
                this.callbacks.onDrag(false);
                this.cancelled = true;
            }
        }
        this.pointers.set(e.pointerId, {
            x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY
        });
        this.maxPointers = Math.max(this.maxPointers, this.pointers.size);
        this.clearAccumulators();
        try { this.element.setPointerCapture(e.pointerId); } catch { /* Unsupported in tests. */ }
        if (this.pointers.size === 3 && !this.cancelled) {
            this.dragPointerCount = 3;
            this.callbacks.onDrag(true);
        }
    }

    private handlePointerMove(e: PointerEvent) {
        const prev = this.pointers.get(e.pointerId);
        if (!prev || this.cancelled) return;
        let rawDx = e.clientX - prev.x;
        let rawDy = e.clientY - prev.y;
        prev.x = e.clientX;
        prev.y = e.clientY;
        const distance = Math.hypot(e.clientX - prev.startX, e.clientY - prev.startY);
        if (this.pointers.size === 1 && this.maxPointers === 1 && !this.hasMoved) {
            // Ignore jitter on either tap, retaining the whole movement when sliding starts.
            if (distance <= TAP_MOVEMENT_THRESHOLD) return;
            rawDx = e.clientX - prev.startX;
            rawDy = e.clientY - prev.startY;
            if (this.doubleTapCandidate) {
                this.doubleTapCandidate = false;
                this.dragPointerCount = 1;
                this.callbacks.onDrag(true);
            }
        }
        if (distance > 2) this.hasMoved = true;
        // Remaining fingers after a multi-finger gesture must not move the cursor.
        if ((this.pointers.size === 1 && this.maxPointers === 1) || this.dragPointerCount) {
            this.accumulatorX += rawDx * this.sensitivity;
            this.accumulatorY += rawDy * this.sensitivity;
            const dx = Math.trunc(this.accumulatorX), dy = Math.trunc(this.accumulatorY);
            if (dx || dy) {
                this.accumulatorX -= dx;
                this.accumulatorY -= dy;
                this.callbacks.onMove(dx, dy);
                // Any transmitted movement disqualifies the gesture as a click.
                this.hasMoved = true;
            }
        } else if (this.pointers.size === 2 && this.maxPointers === 2
            && e.pointerId === this.pointers.keys().next().value) {
            this.scrollAccumulatorX += rawDx * this.scrollSensitivity;
            this.scrollAccumulatorY += rawDy * this.scrollSensitivity;
            const sx = Math.trunc(this.scrollAccumulatorX), sy = Math.trunc(this.scrollAccumulatorY);
            if (sx || sy) {
                this.scrollAccumulatorX -= sx;
                this.scrollAccumulatorY -= sy;
                this.callbacks.onScroll(sx, sy);
                this.hasMoved = true;
            }
        }
    }

    private handlePointerUp(e: PointerEvent) {
        if (!this.pointers.has(e.pointerId)) return;
        if (e.type !== 'pointerup') {
            this.cancelled = true;
        }
        this.pointers.delete(e.pointerId);
        this.doubleTapCandidate = false;
        if (this.dragPointerCount && this.pointers.size < this.dragPointerCount) {
            this.dragPointerCount = 0;
            this.callbacks.onDrag(false);
        }
        try { this.element.releasePointerCapture(e.pointerId); } catch { /* Capture may already be lost. */ }
        if (this.pointers.size === 0 && !this.cancelled && !this.hasMoved) {
            if (this.maxPointers === 1) {
                if (Date.now() - this.tapStartedAt <= DOUBLE_TAP_INTERVAL) {
                    this.lastTap = { x: e.clientX, y: e.clientY, time: Date.now() };
                }
                this.callbacks.onClick(1);
            } else if (this.maxPointers === 2) this.callbacks.onClick(2);
        }
    }
}
