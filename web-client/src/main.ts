const OP_MOVE = 0x01;
const OP_CLICK = 0x02;
const OP_SCROLL = 0x03;
const OP_DRAG = 0x04;

class RemoteMouseClient {
    private ws: WebSocket | null = null;
    private statusEl: HTMLElement;
    private touchpadEl: HTMLElement;

    // 手势识别相关变量
    private pointers = new Map<number, {x: number, y: number}>();
    private isDragging = false;
    private hasMoved = false;
    private lastTapTime = 0;
    private lastRightClickTime = 0;

    // 移动优化变量
    private moveSensitivity = 2;
    private dragSensitivity = this.moveSensitivity / 2; // 降低拖拽灵敏度，提高选择精度
    private accumulatorX = 0;
    private accumulatorY = 0;
    private pendingDx = 0;
    private pendingDy = 0;

    // 复用 Buffer，减少 GC
    private moveBuffer = new ArrayBuffer(5);
    private moveView = new DataView(this.moveBuffer);

    constructor() {
        this.statusEl = document.getElementById('status')!;
        this.touchpadEl = document.getElementById('touchpad')!;
        this.initWebSocket();
        this.initInputs();
        this.startLoop(); // 启动 RAF 发送循环
    }

    private updateStatus(status: string, className: string) {
        this.statusEl.textContent = status;
        this.statusEl.className = className;
    }

    private initWebSocket() {
        this.updateStatus('正在连接...', 'connecting');

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
            this.updateStatus('已连接', 'connected');
            console.log('WebSocket opened');
        };

        this.ws.onclose = () => {
            this.updateStatus('连接断开', 'disconnected');
            setTimeout(() => this.initWebSocket(), 3000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateStatus('连接错误', 'disconnected');
        };
    }

    private sendCommand(buffer: ArrayBuffer) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(buffer);
        }
    }

    // 使用预分配的 Buffer 和 View，降低频繁创建对象带来的开销
    private sendMove(dx: number, dy: number) {
        this.moveView.setUint8(0, OP_MOVE);
        this.moveView.setInt16(1, dx, false); // big-endian
        this.moveView.setInt16(3, dy, false);
        this.sendCommand(this.moveBuffer);
    }

    private sendClick(button: number) {
        const buffer = new ArrayBuffer(2);
        const view = new DataView(buffer);
        view.setUint8(0, OP_CLICK);
        view.setUint8(1, button); // 0x01 left, 0x02 right
        this.sendCommand(buffer);
    }

    private sendScroll(sx: number, sy: number) {
        const buffer = new ArrayBuffer(5);
        const view = new DataView(buffer);
        view.setUint8(0, OP_SCROLL);
        view.setInt16(1, sx, false);
        view.setInt16(3, sy, false);
        this.sendCommand(buffer);
    }

    private sendDrag(state: number) {
        const buffer = new ArrayBuffer(2);
        const view = new DataView(buffer);
        view.setUint8(0, OP_DRAG);
        view.setUint8(1, state); // 0x01 start, 0x00 end
        this.sendCommand(buffer);
    }

    // 心跳循环
    private startLoop() {
        const loop = () => {
            if (this.pendingDx !== 0 || this.pendingDy !== 0) {
                this.sendMove(this.pendingDx, this.pendingDy);
                this.pendingDx = 0;
                this.pendingDy = 0;
            }
            requestAnimationFrame(loop); // 与屏幕刷新率同步
        };
        requestAnimationFrame(loop);
    }

    private initInputs() {
        this.touchpadEl.addEventListener('pointerdown', (e) => {
            if (this.pointers.size === 0) {
                this.hasMoved = false;
            }
            this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

            // 每次按下新手指，重置累加器
            this.accumulatorX = 0;
            this.accumulatorY = 0;

            if (this.pointers.size === 3) {
                this.isDragging = true;
                this.sendDrag(0x01);
            }
        });

        this.touchpadEl.addEventListener('pointermove', (e) => {
            if (!this.pointers.has(e.pointerId)) return;

            const prev = this.pointers.get(e.pointerId)!;
            const rawDx = e.clientX - prev.x;
            const rawDy = e.clientY - prev.y;

            if (Math.abs(rawDx) > 1 || Math.abs(rawDy) > 1) {
                this.hasMoved = true;
            }

            this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

            if (this.pointers.size === 1) {
                // 单指移动 - 只累加，不发送，由 startLoop 处理
                this.accumulatorX += rawDx * this.moveSensitivity;
                this.accumulatorY += rawDy * this.moveSensitivity;

                const stepX = Math.trunc(this.accumulatorX);
                const stepY = Math.trunc(this.accumulatorY);

                this.accumulatorX -= stepX;
                this.accumulatorY -= stepY;

                this.pendingDx += stepX;
                this.pendingDy += stepY;

            } else if (this.pointers.size === 2) {
                // 双指滚动
                if (e.pointerId === Array.from(this.pointers.keys())[0]) {
                    this.sendScroll(Math.round(rawDx), Math.round(rawDy));
                }
            } else if (this.pointers.size === 3) {
                // 三指移动
                this.accumulatorX += rawDx * this.dragSensitivity;
                this.accumulatorY += rawDy * this.dragSensitivity;

                const stepX = Math.trunc(this.accumulatorX);
                const stepY = Math.trunc(this.accumulatorY);

                this.accumulatorX -= stepX;
                this.accumulatorY -= stepY;

                this.pendingDx += stepX;
                this.pendingDy += stepY;
            }
        });

        const handlePointerUp = (e: PointerEvent) => {
            if (this.pointers.size === 1) {
                // 处理点击 (Tap)
                const now = Date.now();
                if (now - this.lastTapTime < 300) {
                   // double tap logic could go here
                }
            } else if (this.pointers.size === 2) {
                // 双指点击 -> 右键
                if (!this.hasMoved) {
                    this.sendClick(0x02);
                    this.lastRightClickTime = Date.now();
                }
            }

            if (this.isDragging && this.pointers.size < 3) {
                this.isDragging = false;
                this.sendDrag(0x00);
            }

            this.pointers.delete(e.pointerId);
        };

        this.touchpadEl.addEventListener('pointerup', handlePointerUp);
        this.touchpadEl.addEventListener('pointercancel', handlePointerUp);

        // 处理单击逻辑
        this.touchpadEl.addEventListener('click', () => {
            const now = Date.now();
            if (!this.hasMoved && (now - this.lastRightClickTime > 300)) {
                this.sendClick(0x01);
            }
        });
    }
}

new RemoteMouseClient();
