const OP_MOVE = 0x01;
const OP_CLICK = 0x02;
const OP_SCROLL = 0x03;
const OP_DRAG = 0x04;
const OP_TEXT = 0x05;
const OP_KEY_ACTION = 0x06;

class RemoteMouseClient {
    private ws: WebSocket | null = null;
    private statusEl: HTMLElement;
    private touchpadEl: HTMLElement;
    private keyboardBtn: HTMLElement;
    private keyboardInput: HTMLTextAreaElement;

    // 手势识别相关变量
    private pointers = new Map<number, {x: number, y: number}>();
    private isDragging = false;
    private hasMoved = false;
    private lastRightClickTime = 0;

    // 移动优化变量
    private moveSensitivity = 2;
    private accumulatorX = 0;
    private accumulatorY = 0;
    private pendingDx = 0;
    private pendingDy = 0;

    // 复用 Buffer，减少 GC
    private moveBuffer = new ArrayBuffer(5);
    private moveView = new DataView(this.moveBuffer);

    // 键盘相关
    private isKeyboardOpen = false;
    private isComposing = false;

    // 功能键/修饰键相关
    private activeModifiers = 0; // Bitmask: 1=Ctrl, 2=Shift, 4=Alt, 8=Win
    private fnPanelEl: HTMLElement;

    constructor() {
        this.statusEl = document.getElementById('status')!;
        this.touchpadEl = document.getElementById('touchpad')!;
        this.keyboardBtn = document.getElementById('btn-keyboard')!;
        this.keyboardInput = document.getElementById('keyboard-input')! as HTMLTextAreaElement;
        this.fnPanelEl = document.getElementById('fn-panel')!;

        this.initWebSocket();
        this.initInputs();
        this.initKeyboard();
        this.initFnKeys();
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
        this.moveView.setInt16(1, dx, false);
        this.moveView.setInt16(3, dy, false);
        this.sendCommand(this.moveBuffer);
    }

    private sendClick(button: number, modifierMask?: number) {
        // [OpCode] [Button] [ModifierMask]
        const mask = modifierMask !== undefined ? modifierMask : this.activeModifiers;
        const buffer = new ArrayBuffer(3);
        const view = new DataView(buffer);
        view.setUint8(0, OP_CLICK);
        view.setUint8(1, button);
        view.setUint8(2, mask);
        this.sendCommand(buffer);

        if (mask !== 0) {
            this.resetModifiers();
        }
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
        view.setUint8(1, state);
        this.sendCommand(buffer);
    }

    private sendText(text: string) {
        if (!text) return;
        const encoder = new TextEncoder();
        const textBytes = encoder.encode(text);
        const buffer = new Uint8Array(1 + textBytes.length);
        buffer[0] = OP_TEXT;
        buffer.set(textBytes, 1);
        this.sendCommand(buffer.buffer);
    }

    private sendKeyAction(keyName: string, modifierMask?: number) {
        // [OpCode] [ModifierMask] [KeyName]
        const mask = modifierMask !== undefined ? modifierMask : this.activeModifiers;
        const encoder = new TextEncoder();
        const keyBytes = encoder.encode(keyName);
        const buffer = new Uint8Array(2 + keyBytes.length);
        buffer[0] = OP_KEY_ACTION;
        buffer[1] = mask;
        buffer.set(keyBytes, 2);
        this.sendCommand(buffer.buffer);

        if (mask !== 0) {
            this.resetModifiers();
        }
    }

    private resetModifiers() {
        this.activeModifiers = 0;
        const modifiers = this.fnPanelEl.querySelectorAll('.modifier');
        modifiers.forEach(el => el.classList.remove('active'));
    }

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
        this.touchpadEl.addEventListener('touchstart', (e) => {
            e.preventDefault();
        }, { passive: false });

        this.touchpadEl.addEventListener('pointerdown', (e) => {
            // 点击触控板时，如果键盘打开，则收起键盘
            if (this.isKeyboardOpen) {
                this.toggleKeyboard(false);
                return; // 防止误触
            }

            if (this.pointers.size === 0) {
                this.hasMoved = false;
            }
            this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
            this.accumulatorX = 0;
            this.accumulatorY = 0;
            this.touchpadEl.setPointerCapture(e.pointerId);

            if (this.pointers.size === 3) {
                this.isDragging = true;
                this.sendDrag(OP_MOVE);
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
                this.accumulatorX += rawDx * this.moveSensitivity;
                this.accumulatorY += rawDy * this.moveSensitivity;
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
                if (!this.hasMoved && !this.isDragging && (now - this.lastRightClickTime > 300) && !this.isKeyboardOpen) {
                    this.sendClick(OP_MOVE);
                }
            } else if (this.pointers.size === 2) {
                // 双指点击 -> 右键
                if (!this.hasMoved) {
                    this.sendClick(OP_CLICK); // 传入 0x02 表示右键，mask 会在 sendClick 内部获取
                    this.lastRightClickTime = Date.now();
                }
            }

            if (this.isDragging && this.pointers.size < 3) {
                this.isDragging = false;
                this.sendDrag(0x00);
            }

            this.touchpadEl.releasePointerCapture(e.pointerId);
            this.pointers.delete(e.pointerId);
        };

        this.touchpadEl.addEventListener('pointerup', handlePointerUp);
        this.touchpadEl.addEventListener('pointercancel', handlePointerUp);
    }

    private toggleKeyboard(show: boolean) {
        this.isKeyboardOpen = show;
        if (show) {
            this.keyboardInput.focus();
            this.keyboardBtn.classList.add('active');
        } else {
            this.keyboardInput.blur();
            this.keyboardBtn.classList.remove('active');
        }
    }

    private initFnKeys() {
        this.fnPanelEl.addEventListener('click', (e) => {
            const target = (e.target as HTMLElement).closest('.fn-btn');
            if (!target) return;

            const modifier = target.getAttribute('data-modifier');
            const key = target.getAttribute('data-key');

            if (modifier) {
                // Handle sticky modifiers
                let bit = 0;
                if (modifier === 'ctrl') bit = 1;
                else if (modifier === 'shift') bit = 2;
                else if (modifier === 'alt') bit = 4;
                else if (modifier === 'win') bit = 8;

                if (bit > 0) {
                    // Toggle bit
                    if (this.activeModifiers & bit) {
                        this.activeModifiers &= ~bit;
                        target.classList.remove('active');
                    } else {
                        this.activeModifiers |= bit;
                        target.classList.add('active');
                    }
                }
            } else if (key) {
                // Handle normal key action
                this.sendKeyAction(key);
            }
        });
    }

    private initKeyboard() {
        this.keyboardBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleKeyboard(!this.isKeyboardOpen);
        });

        // 监听 Composition 事件 (处理中文输入)
        this.keyboardInput.addEventListener('compositionstart', () => {
            this.isComposing = true;
        });

        this.keyboardInput.addEventListener('compositionend', (e) => {
            this.isComposing = false;
            if (e.data) {
                this.sendText(e.data);
            }
            this.keyboardInput.value = '';
        });

        // 监听 input 事件
        this.keyboardInput.addEventListener('input', (e) => {
            const event = e as InputEvent;

            if (this.isComposing) return;

            if (event.data) {
                // 如果有激活的修饰键，或者输入的字符是单个字母/数字，
                // 且 activeModifiers > 0，则当作 KeyAction 发送
                // 例如 Ctrl+C
                if (this.activeModifiers > 0 && event.data.length === 1) {
                    this.sendKeyAction(event.data.toLowerCase());
                } else {
                    this.sendText(event.data);
                }
            }

            // 清空输入框
            setTimeout(() => {
                this.keyboardInput.value = '';
            }, 0);
        });

        // 某些浏览器可能需要 keydown 来捕获特定键
        this.keyboardInput.addEventListener('keydown', (e) => {
             if (this.isComposing) return;

             if (e.key === 'Backspace') {
                this.sendKeyAction('backspace');
                e.preventDefault();
             } else if (e.key === 'Delete') {
                this.sendKeyAction('delete');
                e.preventDefault();
             } else if (e.key === 'Enter') {
                this.sendKeyAction('enter');
                e.preventDefault();
             }
        });
    }
}

new RemoteMouseClient();
