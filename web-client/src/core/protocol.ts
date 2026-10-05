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


export const OP_MEDIA = 0x07;
export const OP_MEDIA_QUERY = 0x08;
export const mediaActions = {
    rewind: 1, play_pause: 2, forward: 3, volume_down: 4, mute: 5, volume_up: 6, fullscreen: 7
} as const;
export type MediaAction = keyof typeof mediaActions;
export interface MediaSnapshot {
    type: 'media_snapshot'; version: 1; revision: number; requestId?: number; queryId?: number;
    capabilities: MediaAction[]; unavailable: Partial<Record<MediaAction, string>>;
    state: { volume: number | null; muted: boolean | null; playing: null; fullscreen: null };
}
export interface MediaResult {
    type: 'media_result'; version: 1; requestId: number; action: MediaAction;
    status: 'issued' | 'verified' | 'error'; errorCode?: string;
}
export function encodeMedia(action: MediaAction, requestId: number): ArrayBuffer {
    const packet = new ArrayBuffer(6);
    const view = new DataView(packet);
    view.setUint8(0, OP_MEDIA);
    view.setUint8(1, mediaActions[action]);
    view.setUint32(2, requestId, false);
    return packet;
}
export function parseMediaMessage(raw: unknown): MediaSnapshot | MediaResult | null {
    try {
        if (typeof raw !== 'string') return null;
        const value = JSON.parse(raw);
        if (!value || value.version !== 1) return null;
        const uint32 = (n: unknown) => typeof n === 'number' && Number.isInteger(n) && n >= 0 && n <= 0xffffffff;
        if (value.type === 'media_result' && uint32(value.requestId)
            && Object.hasOwn(mediaActions, value.action)
            && ['issued', 'verified', 'error'].includes(value.status)
            && (value.errorCode === undefined || typeof value.errorCode === 'string')) return value;
        const state = value.state;
        if (value.type === 'media_snapshot' && Number.isSafeInteger(value.revision) && value.revision >= 0
            && (value.requestId === undefined || uint32(value.requestId))
            && (value.queryId === undefined || (Number.isSafeInteger(value.queryId) && value.queryId > 0))
            && Array.isArray(value.capabilities) && value.capabilities.every((a: string) => Object.hasOwn(mediaActions, a))
            && value.unavailable && typeof value.unavailable === 'object' && !Array.isArray(value.unavailable)
            && Object.values(value.unavailable).every(v => typeof v === 'string')
            && state && (state.volume === null || (typeof state.volume === 'number' && Number.isFinite(state.volume) && state.volume >= 0))
            && (state.muted === null || typeof state.muted === 'boolean')
            && state.playing === null && state.fullscreen === null) return value;
    } catch { /* Ignore malformed or unrelated responses. */ }
    return null;
}
