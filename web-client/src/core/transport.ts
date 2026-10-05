import { ConnectionStatus } from './protocol';

interface TransportOptions {
    onMessage?: (data: unknown) => void;
    onStateChange?: (state: ConnectionStatus, statusText: string) => void;
}

export class Transport {
    private ws: WebSocket | null = null;
    private options: TransportOptions;
    private reconnectTimer: number | null = null;
    private isExplicitlyClosed = false;

    private metrics = {
        packetsSent: 0,
        bytesSent: 0
    };

    constructor(options: TransportOptions) {
        this.options = options;
    }

    public getMetrics() {
        const result = { ...this.metrics };
        this.metrics.packetsSent = 0;
        this.metrics.bytesSent = 0;
        return result;
    }

    public connect(url: string) {
        this.isExplicitlyClosed = false;
        if (this.reconnectTimer !== null) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        const previous = this.ws;
        this.ws = null;
        previous?.close();
        this.updateState(ConnectionStatus.Connecting, 'status.connecting');

        try {
            const socket = new WebSocket(url);
            this.ws = socket;
            this.ws.binaryType = 'arraybuffer';

            socket.onmessage = event => {
                if (this.ws === socket && socket.readyState === WebSocket.OPEN) {
                    this.options.onMessage?.(event.data);
                }
            };

            socket.onopen = () => {
                if (this.ws !== socket) return;
                this.updateState(ConnectionStatus.Connected, 'status.connected');
                console.log('WebSocket opened');
            };

            socket.onclose = () => {
                if (this.ws !== socket) return;
                this.ws = null;
                this.updateState(ConnectionStatus.Disconnected, 'status.disconnected');
                this.scheduleReconnect(url);
            };

            socket.onerror = (error) => {
                if (this.ws !== socket) return;
                console.error('WebSocket error:', error);
                this.updateState(ConnectionStatus.Disconnected, 'status.error');
                // onerror usually is followed by onclose, so we let onclose handle reconnect
            };

        } catch (e) {
            console.error('Connection failed synchronously', e);
            this.updateState(ConnectionStatus.Disconnected, 'status.failed');
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
            const socket = this.ws;
            this.ws = null;
            socket.close();
            this.updateState(ConnectionStatus.Disconnected, 'status.disconnected');
        }
    }

    public send(data: ArrayBuffer | Uint8Array) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                this.ws.send(data);
            } catch {
                return false;
            }
            this.metrics.packetsSent++;
            this.metrics.bytesSent += data.byteLength;
            return true;
        }
        return false;
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

    private updateState(state: ConnectionStatus, text: string) {
        if (this.options.onStateChange) {
            this.options.onStateChange(state, text);
        }
    }
}
