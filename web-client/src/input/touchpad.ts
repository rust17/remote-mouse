interface TouchpadCallbacks {
    onMove: (dx: number, dy: number) => void;
    onClick: (button: number) => void;
    onScroll: (sx: number, sy: number) => void;
    onDrag: (active: boolean) => void;
}

export class TouchpadHandler {
    private element: HTMLElement;
    private callbacks: TouchpadCallbacks;

    // State
    private pointers = new Map<number, {x: number, y: number}>();
    private isDragging = false;
    private hasMoved = false;
    private lastRightClickTime = 0;

    // Movement optimization
    private accumulatorX = 0;
    private accumulatorY = 0;
    private scrollAccumulatorX = 0;
    private scrollAccumulatorY = 0;

    // Config
    public sensitivity = 2;
    public scrollSensitivity = 1;

    constructor(element: HTMLElement, callbacks: TouchpadCallbacks) {
        this.element = element;
        this.callbacks = callbacks;
        this.initListeners();
    }

    public setSensitivity(val: number) {
        this.sensitivity = val;
    }

    public setScrollSensitivity(val: number) {
        this.scrollSensitivity = val;
    }

    private initListeners() {
        // Prevent all default touch actions to stop iOS gestures (text selection, magnifying glass, undo/redo menu)
        const preventAll = (e: Event) => {
            e.preventDefault();
            e.stopPropagation();
        };

        this.element.addEventListener('touchstart', preventAll, { passive: false });
        this.element.addEventListener('touchmove', preventAll, { passive: false });
        this.element.addEventListener('touchend', preventAll, { passive: false });
        this.element.addEventListener('touchcancel', preventAll, { passive: false });

        // Disable context menu
        this.element.addEventListener('contextmenu', preventAll, { passive: false });

        // Disable iOS specific gestures (pinch to zoom etc, which might interfere)
        // @ts-ignore - gesture events are non-standard but exist on WebKit
        this.element.addEventListener('gesturestart', preventAll, { passive: false });
        // @ts-ignore
        this.element.addEventListener('gesturechange', preventAll, { passive: false });
        // @ts-ignore
        this.element.addEventListener('gestureend', preventAll, { passive: false });

        this.element.addEventListener('pointerdown', this.handlePointerDown.bind(this));
        this.element.addEventListener('pointermove', this.handlePointerMove.bind(this));
        this.element.addEventListener('pointerup', this.handlePointerUp.bind(this));
        this.element.addEventListener('pointercancel', this.handlePointerUp.bind(this));

        // Reset state when page becomes hidden (e.g. lock screen, switch app)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.resetState();
            }
        });
    }

    private resetState() {
        this.pointers.clear();
        this.isDragging = false;
        this.hasMoved = false;
        this.accumulatorX = 0;
        this.accumulatorY = 0;
        this.scrollAccumulatorX = 0;
        this.scrollAccumulatorY = 0;
        if (this.isDragging) {
             this.callbacks.onDrag(false);
        }
    }

    private handlePointerDown(e: PointerEvent) {
        // Assume external logic handles "keyboard open check" or we add a "disabled" state to this class

        if (this.pointers.size === 0) {
            this.hasMoved = false;
        }

        this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        this.accumulatorX = 0;
        this.accumulatorY = 0;
        this.scrollAccumulatorX = 0;
        this.scrollAccumulatorY = 0;

        try {
            this.element.setPointerCapture(e.pointerId);
        } catch (err) {
            // Ignore in tests or if capture fails
        }

        if (this.pointers.size === 3) {
            this.isDragging = true;
            this.callbacks.onDrag(true);
        }
    }

    private handlePointerMove(e: PointerEvent) {
        if (!this.pointers.has(e.pointerId)) return;

        const prev = this.pointers.get(e.pointerId)!;
        const rawDx = e.clientX - prev.x;
        const rawDy = e.clientY - prev.y;

        if (Math.abs(rawDx) > 1 || Math.abs(rawDy) > 1) {
            this.hasMoved = true;
        }

        this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

        if (this.pointers.size === 1) {
            // Single finger move
            this.accumulatorX += rawDx * this.sensitivity;
            this.accumulatorY += rawDy * this.sensitivity;

            const stepX = Math.trunc(this.accumulatorX);
            const stepY = Math.trunc(this.accumulatorY);

            if (stepX !== 0 || stepY !== 0) {
                this.accumulatorX -= stepX;
                this.accumulatorY -= stepY;
                this.callbacks.onMove(stepX, stepY);
            }
        } else if (this.pointers.size === 2) {
            // Two finger scroll - only trigger for the first pointer to avoid double events
            if (e.pointerId === Array.from(this.pointers.keys())[0]) {
                this.scrollAccumulatorX += rawDx * this.scrollSensitivity;
                this.scrollAccumulatorY += rawDy * this.scrollSensitivity;

                const stepX = Math.trunc(this.scrollAccumulatorX);
                const stepY = Math.trunc(this.scrollAccumulatorY);

                if (stepX !== 0 || stepY !== 0) {
                    this.scrollAccumulatorX -= stepX;
                    this.scrollAccumulatorY -= stepY;
                    this.callbacks.onScroll(stepX, stepY);
                }
            }
        } else if (this.pointers.size === 3) {
            // Three finger drag move
            this.accumulatorX += rawDx * this.sensitivity;
            this.accumulatorY += rawDy * this.sensitivity;

            const stepX = Math.trunc(this.accumulatorX);
            const stepY = Math.trunc(this.accumulatorY);

            if (stepX !== 0 || stepY !== 0) {
                this.accumulatorX -= stepX;
                this.accumulatorY -= stepY;
                this.callbacks.onMove(stepX, stepY);
            }
        }
    }

    private handlePointerUp(e: PointerEvent) {
        if (!this.pointers.has(e.pointerId)) return;

        const now = Date.now();

        // Fix: Do not trigger clicks on pointercancel (e.g. lock screen, system interruption)
        if (e.type !== 'pointercancel') {
            if (this.pointers.size === 1) {
                // Tap (Left Click)
                // Logic: Not moved, Not in drag mode, Time since last right click > 300ms
                if (!this.hasMoved && !this.isDragging && (now - this.lastRightClickTime > 300)) {
                    this.callbacks.onClick(1);
                }
            } else if (this.pointers.size === 2) {
                // Two finger tap (Right Click)
                if (!this.hasMoved) {
                    this.callbacks.onClick(2); // OP_CLICK (0x02) used as button ID in original code
                    this.lastRightClickTime = now;
                }
            }
        }

        if (this.isDragging && this.pointers.size <= 3) {
            this.isDragging = false;
            this.callbacks.onDrag(false);
        }

        try {
            this.element.releasePointerCapture(e.pointerId);
        } catch (err) {
            // ignore
        }
        this.pointers.delete(e.pointerId);
    }
}
