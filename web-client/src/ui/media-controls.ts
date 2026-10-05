import { encodeMedia, OP_MEDIA_QUERY, parseMediaMessage } from '../core/protocol';
import type { MediaAction, MediaResult, MediaSnapshot } from '../core/protocol';
import type { ControlMode } from '../input/touchpad';
import { i18n } from '../core/i18n';
import { VolumeToast } from './volume-toast';
import { installNativeHapticTargets } from './native-haptics';

const TIMEOUT = 3000;
export class MediaControls {
    private root: HTMLElement;
    private send: (data: ArrayBuffer | Uint8Array) => boolean;
    private connected = false;
    private mode: ControlMode = 'computer';
    private snapshot: MediaSnapshot | null = null;
    private revision = -1;
    private nextId = 0;
    private pending = new Map<number, { action: MediaAction; started: number; timer: number }>();
    private completed = new Map<number, { started: number; showVolume: boolean }>();
    private volumeToast: VolumeToast;
    private poll: number | null = null;
    private nextQueryId = 0;
    private queries = new Map<number, { started: number; timer: number }>();
    private snapshotAt = 0;
    private expiryTimer: number | null = null;
    private feedback = 'media.unavailable';

    constructor(root: HTMLElement, send: (data: ArrayBuffer | Uint8Array) => boolean, keepFocus: () => void) {
        this.root = root;
        this.send = send;
        this.volumeToast = new VolumeToast(root.querySelector<HTMLElement>('#volume-toast')!);
        root.querySelector<HTMLButtonElement>('#btn-fullscreen')!.dataset.media = 'fullscreen';
        this.buttons().forEach(button => {
            button.addEventListener('pointerdown', event => {
                if (!(event.target as HTMLElement).classList.contains('native-haptic-switch')) event.preventDefault();
            });
            button.addEventListener('click', () => {
                if (!button.disabled) this.request(button.dataset.media as MediaAction);
                keepFocus();
            });
        });
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) this.volumeToast.hide();
            this.updatePolling();
        });
        window.addEventListener('pagehide', () => this.setConnected(false));
        this.render();
    }

    public setConnected(connected: boolean) {
        this.connected = connected;
        this.snapshot = null;
        this.revision = -1;
        this.pending.forEach(p => clearTimeout(p.timer));
        this.pending.clear();
        this.completed.clear();
        this.queries.forEach(query => clearTimeout(query.timer));
        this.queries.clear();
        this.nextQueryId = 0;
        this.snapshotAt = 0;
        if (this.expiryTimer !== null) clearTimeout(this.expiryTimer);
        this.feedback = connected ? 'media.detecting' : 'media.unavailable';
        this.render();
        if (connected) this.query();
        this.updatePolling();
    }

    public setMode(mode: ControlMode) {
        this.mode = mode;
        if (mode !== 'tv') this.volumeToast.hide();
        this.updatePolling();
    }

    private buttons() { return this.root.querySelectorAll<HTMLButtonElement>('button[data-media]'); }

    private query() {
        if (!this.connected || !this.send(new Uint8Array([OP_MEDIA_QUERY]))) return;
        const id = ++this.nextQueryId;
        const timer = window.setTimeout(() => {
            this.queries.delete(id);
            if (Date.now() - this.snapshotAt >= TIMEOUT) {
                this.snapshot = null;
                this.feedback = 'media.unavailable';
                this.render();
            }
        }, TIMEOUT);
        this.queries.set(id, { started: Date.now(), timer });
    }

    private updatePolling() {
        if (this.poll !== null) clearInterval(this.poll);
        this.poll = null;
        if (this.connected && this.mode === 'tv' && !document.hidden) {
            // The connection probe already queries once; entering TV queries immediately.
            if (this.queries.size === 0) this.query();
            this.poll = window.setInterval(() => this.query(), 1000);
        }
    }

    private request(action: MediaAction) {
        const id = this.nextId = (this.nextId + 1) >>> 0;
        if (!this.send(encodeMedia(action, id))) return;
        const started = Date.now();
        const timer = window.setTimeout(() => {
            this.pending.delete(id);
            this.feedback = 'media.timeout';
            this.render();
        }, TIMEOUT);
        this.pending.set(id, { action, started, timer });
        this.feedback = 'media.sending';
        this.render();
    }

    public receive(raw: unknown) {
        if (!this.connected) return;
        const message = parseMediaMessage(raw);
        if (!message) return;
        if (message.type === 'media_result') return this.result(message);
        const now = Date.now();
        let showVolume = false;
        if (message.requestId !== undefined) {
            const completed = this.completed.get(message.requestId);
            const started = completed?.started ?? this.pending.get(message.requestId)?.started;
            showVolume = completed?.showVolume ?? false;
            this.completed.delete(message.requestId);
            if (started === undefined || now - started >= TIMEOUT) return;
        } else {
            if (message.queryId === undefined) return;
            const query = this.queries.get(message.queryId);
            if (!query) return;
            clearTimeout(query.timer);
            this.queries.delete(message.queryId);
            if (now - query.started >= TIMEOUT) return;
        }
        if (message.revision <= this.revision) {
            if (showVolume && this.snapshot && this.mode === 'tv' && !document.hidden) this.volumeToast.show();
            return;
        }
        this.snapshot = message;
        this.snapshotAt = now;
        this.revision = message.revision;
        if (this.feedback === 'media.detecting' || this.feedback === 'media.unavailable') this.feedback = 'media.hint';
        if (this.expiryTimer !== null) clearTimeout(this.expiryTimer);
        // Visible TV controls must not retain enabled capabilities after a stalled socket.
        this.expiryTimer = window.setTimeout(() => {
            this.snapshot = null;
            this.feedback = 'media.unavailable';
            this.render();
        }, 4000);
        this.render();
        if (showVolume && this.mode === 'tv' && !document.hidden) this.volumeToast.show();
    }

    private result(result: MediaResult) {
        const pending = this.pending.get(result.requestId);
        if (!pending || pending.action !== result.action || Date.now() - pending.started >= TIMEOUT) return;
        const audio = ['volume_down', 'mute', 'volume_up'].includes(result.action);
        if ((result.status === 'verified' && !audio) || (result.status === 'issued' && audio)) return;
        clearTimeout(pending.timer);
        this.pending.delete(result.requestId);
        this.completed.set(result.requestId, { started: pending.started, showVolume: audio && result.status === 'verified' });
        // Bounded tracking, even if a peer omits the accompanying snapshot.
        if (this.completed.size > 32) this.completed.delete(this.completed.keys().next().value!);
        this.feedback = result.status === 'error' ? 'media.failed' : result.status === 'issued' ? 'media.issued' : 'media.verified';
        this.root.querySelector<HTMLElement>('#media-unavailable')!.title = this.reason(result.errorCode);
        this.render();
    }

    private reason(code?: string) {
        if (!code) return '';
        switch (code) {
            case 'input_permission': return i18n.t('media.input_permission');
            case 'input_unsupported': return i18n.t('media.input_unsupported');
            case 'drag_busy': return i18n.t('media.drag_busy');
            case 'audio_dependency': return i18n.t('media.audio_dependency');
            case 'audio_permission': return i18n.t('media.audio_permission');
            case 'audio_no_device': return i18n.t('media.audio_no_device');
            case 'audio_unavailable': return i18n.t('media.audio_unavailable');
            default: return i18n.t('media.execution_failed');
        }
    }

    private render() {
        const pendingActions = new Set([...this.pending.values()].map(p => p.action));
        this.buttons().forEach(button => {
            const action = button.dataset.media as MediaAction;
            button.disabled = !this.snapshot?.capabilities.includes(action) || pendingActions.has(action);
            button.title = this.reason(this.snapshot?.unavailable[action]);
            if (action === 'mute') {
                const muted = this.snapshot?.state.muted;
                button.classList.toggle('active', muted === true);
                if (muted === null || muted === undefined) button.removeAttribute('aria-pressed');
                else button.setAttribute('aria-pressed', String(muted));
            }
            const overlay = button.closest('.native-haptic-target')?.querySelector<HTMLInputElement>('.native-haptic-switch');
            if (overlay) overlay.disabled = button.disabled;
        });
        const status = this.root.querySelector<HTMLElement>('#media-unavailable')!;
        status.dataset.i18n = this.feedback;
        status.textContent = i18n.t(this.feedback as Parameters<typeof i18n.t>[0]);
        this.volumeToast.update(this.snapshot?.state ?? null);
        const reason = this.root.querySelector<HTMLElement>('#media-reason')!;
        const errors = [...new Set(Object.values(this.snapshot?.unavailable ?? {}).map(code => this.reason(code)))];
        reason.textContent = errors.join(' · ');
        reason.hidden = errors.length === 0;
        installNativeHapticTargets(this.root);
    }
}
