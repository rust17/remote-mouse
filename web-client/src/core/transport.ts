type ConnectionState = 'connected' | 'disconnected' | 'connecting';

interface TransportOptions {
    onStateChange?: (state: ConnectionState, statusText: string) => void;
}

export class Transport {
    private ws: WebSocket | null = null;
    private options: TransportOptions;
    private reconnectTimer: number | null = null;
    private isExplicitlyClosed = false;

    constructor(options: TransportOptions) {
        this.options = options;
    }

    public connect(url: string) {
        this.isExplicitlyClosed = false;
        this.updateState('connecting', '正在连接...');

        try {
            this.ws = new WebSocket(url);
            this.ws.binaryType = 'arraybuffer';

            this.ws.onopen = () => {
                this.updateState('connected', '已连接');
                console.log('WebSocket opened');
            };

            this.ws.onclose = () => {
                this.updateState('disconnected', '连接断开');
                this.scheduleReconnect(url);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateState('disconnected', '连接错误');
                // onerror usually is followed by onclose, so we let onclose handle reconnect
            };

        } catch (e) {
            console.error('Connection failed synchronously', e);
            this.updateState('disconnected', '连接失败');
            this.scheduleReconnect(url);
        }
    }

    public disconnect() {
        this.isExplicitlyClosed = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    public send(data: ArrayBuffer | Uint8Array) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(data);
        }
    }

    private scheduleReconnect(url: string) {
        if (this.isExplicitlyClosed) return;

        if (this.reconnectTimer === null) {
            this.reconnectTimer = window.setTimeout(() => {
                this.reconnectTimer = null;
                this.connect(url);
            }, 3000);
        }
    }

    private updateState(state: ConnectionState, text: string) {
        if (this.options.onStateChange) {
            this.options.onStateChange(state, text);
        }
    }
}
