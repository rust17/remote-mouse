import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Transport } from '../src/core/transport';
import { ConnectionStatus } from '../src/core/protocol';

// Mock WebSocket
class MockWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    static instances: MockWebSocket[] = [];
    onmessage: ((event: { data: unknown }) => void) | null = null;
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;
    onerror: ((err: any) => void) | null = null;
    readyState: number = MockWebSocket.CONNECTING;
    binaryType = 'blob';

    constructor(public url: string) {
        MockWebSocket.instances.push(this);
    }

    send = vi.fn();
    close = vi.fn(() => {
        this.readyState = MockWebSocket.CLOSED;
        if (this.onclose) this.onclose();
    });

    // Helper to simulate connection open
    open() {
        this.readyState = MockWebSocket.OPEN;
        if (this.onopen) this.onopen();
    }

    // Helper to simulate connection close
    terminate() {
        this.readyState = MockWebSocket.CLOSED;
        if (this.onclose) this.onclose();
    }
}

// Stub global WebSocket
vi.stubGlobal('WebSocket', MockWebSocket);

describe('Transport', () => {
    let transport: Transport;
    let onStateChange: any;

    beforeEach(() => {
        MockWebSocket.instances = [];
        vi.useFakeTimers();
        onStateChange = vi.fn();
        transport = new Transport({ onStateChange });
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('should connect and update state to connecting then connected', () => {
        transport.connect('ws://localhost/ws');

        expect(onStateChange).toHaveBeenCalledWith(ConnectionStatus.Connecting, 'status.connecting');
        expect(MockWebSocket.instances.length).toBe(1);

        const ws = MockWebSocket.instances[0];
        ws.open(); // Simulate server accept

        expect(onStateChange).toHaveBeenCalledWith(ConnectionStatus.Connected, 'status.connected');
    });

    it('should attempt reconnect after 3 seconds on close', () => {
        transport.connect('ws://localhost/ws');
        const ws = MockWebSocket.instances[0];
        ws.open();

        // Simulate close
        ws.terminate();
        expect(onStateChange).toHaveBeenCalledWith(ConnectionStatus.Disconnected, 'status.disconnected');

        // Should not have reconnected yet
        expect(MockWebSocket.instances.length).toBe(1);

        // Fast forward 3 seconds
        vi.advanceTimersByTime(3000);

        // Should have created a new connection
        expect(MockWebSocket.instances.length).toBe(2);
        expect(onStateChange).toHaveBeenLastCalledWith(ConnectionStatus.Connecting, 'status.connecting');
    });

    it('should send data only when connected', () => {
        transport.connect('ws://localhost/ws');
        const ws = MockWebSocket.instances[0];

        const data = new ArrayBuffer(8);

        // Not open yet
        expect(transport.send(data)).toBe(false);
        expect(ws.send).not.toHaveBeenCalled();

        // Open
        ws.open();
        expect(transport.send(data)).toBe(true);
        expect(ws.send).toHaveBeenCalledWith(data);
    });
    it('ignores events from obsolete sockets and prevents reconnect after disconnect', () => {
        const onMessage = vi.fn();
        transport = new Transport({ onStateChange, onMessage });
        transport.connect('ws://localhost/ws');
        const old = MockWebSocket.instances[0];
        old.open();
        transport.connect('ws://localhost/ws');
        const current = MockWebSocket.instances[1];
        current.open();
        old.onmessage?.({ data: 'old' });
        old.onclose?.();
        old.onopen?.();
        current.onmessage?.({ data: 'new' });
        expect(onMessage).toHaveBeenCalledExactlyOnceWith('new');
        transport.disconnect();
        current.onmessage?.({ data: 'closed' });
        vi.advanceTimersByTime(6000);
        expect(MockWebSocket.instances).toHaveLength(2);
    });

});
