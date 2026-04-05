export const OP_MOVE = 0x01;
export const OP_CLICK = 0x02;
export const OP_SCROLL = 0x03;
export const OP_DRAG = 0x04;
export const OP_TEXT = 0x05;
export const OP_KEY_ACTION = 0x06;

export const ConnectionStatus = {
    Connected: 'connected',
    Disconnected: 'disconnected',
    Connecting: 'connecting',
} as const;

export type ConnectionStatus = (typeof ConnectionStatus)[keyof typeof ConnectionStatus];

export const allConnectionStatuses = Object.values(ConnectionStatus);


