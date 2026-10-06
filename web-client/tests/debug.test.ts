import { JSDOM } from 'jsdom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import bootstrap from '../src/core/debug-bootstrap.js?raw';

describe('mobile debug bootstrap', () => {
    let dom: JSDOM;
    let viewer: { init: ReturnType<typeof vi.fn>; destroy: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn> };
    let errors: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        dom = new JSDOM('<html><head></head><body></body></html>', {
            url: 'http://localhost:9997/?mode=tv#controls', runScripts: 'outside-only'
        });
        errors = vi.fn();
        viewer = { init: vi.fn(), destroy: vi.fn(), get: vi.fn(() => ({ error: errors, config: { set: vi.fn() } })) };
    });
    afterEach(() => { dom.window.close(); vi.restoreAllMocks(); });

    const start = () => dom.window.eval(bootstrap);
    const script = () => dom.window.document.querySelector<HTMLScriptElement>('script[src="/debug/eruda.js"]')!;
    const loaded = () => {
        dom.window.eruda = viewer;
        script().dispatchEvent(new dom.window.Event('load'));
    };

    it('does not load Eruda by default', () => {
        start();
        expect(dom.window.remoteMouseDebug.isEnabled()).toBe(false);
        expect(script()).toBeNull();
    });

    it('restores the saved switch and supports disabling it before loading finishes', () => {
        dom.window.localStorage.setItem('remote-mouse-debug', 'true');
        start();
        expect(script()).not.toBeNull();
        dom.window.remoteMouseDebug.setEnabled(false);
        loaded();
        expect(viewer.init).not.toHaveBeenCalled();
        expect(dom.window.localStorage.getItem('remote-mouse-debug')).toBe('false');
        dom.window.remoteMouseDebug.setEnabled(true);
        expect(viewer.init).toHaveBeenCalledOnce();
    });

    it('captures startup errors before the main app or Eruda loads even with storage blocked', () => {
        dom.window.history.replaceState(null, '', '/?debug=1');
        vi.spyOn(dom.window, 'localStorage', 'get').mockImplementation(() => {
            throw new DOMException('Access denied', 'SecurityError');
        });
        start();
        dom.window.dispatchEvent(new dom.window.ErrorEvent('error', { message: 'App initialization failed' }));
        loaded();
        expect(viewer.init).toHaveBeenCalledOnce();
        expect(errors.mock.calls[0][0]).toContain('App initialization failed');
        expect(() => dom.window.remoteMouseDebug.setEnabled(false)).not.toThrow();
        expect(viewer.destroy).toHaveBeenCalledOnce();
    });

    it('records resource errors and unhandled rejections', () => {
        dom.window.history.replaceState(null, '', '/?debug=1');
        start();
        const app = dom.window.document.createElement('script');
        app.src = '/assets/app.js';
        dom.window.document.head.appendChild(app);
        app.dispatchEvent(new dom.window.Event('error'));
        loaded();
        expect(errors.mock.calls[0][0]).toContain('/assets/app.js');
        const rejection = new dom.window.Event('unhandledrejection');
        Object.defineProperty(rejection, 'reason', { value: new Error('Async startup failed') });
        dom.window.dispatchEvent(rejection);
        expect(errors.mock.calls[1][0]).toContain('Async startup failed');
    });

    it('keeps WebSocket errors logged while Eruda is loading and restores the console on disable', () => {
        const originalError = vi.spyOn(dom.window.console, 'error').mockImplementation(() => {});
        start();
        dom.window.remoteMouseDebug.setEnabled(true);
        dom.window.console.error('WebSocket error:', new Error('Connection refused'));
        loaded();
        expect(errors.mock.calls[0][0]).toContain('WebSocket error:');
        expect(errors.mock.calls[0][0]).toContain('Connection refused');
        expect(originalError).toHaveBeenCalledOnce();
        dom.window.remoteMouseDebug.setEnabled(false);
        expect(dom.window.console.error).toBe(originalError);
    });

    it('loads once, persists changes and removes the URL override without losing other parameters', () => {
        dom.window.history.replaceState(null, '', '/?mode=tv&debug=1#controls');
        start();
        dom.window.remoteMouseDebug.setEnabled(true);
        expect(dom.window.document.querySelectorAll('script')).toHaveLength(1);
        loaded();
        expect(dom.window.localStorage.getItem('remote-mouse-debug')).toBe('true');
        expect(dom.window.location.href).toBe('http://localhost:9997/?mode=tv#controls');
        dom.window.remoteMouseDebug.setEnabled(false);
        expect(viewer.destroy).toHaveBeenCalledOnce();
        dom.window.remoteMouseDebug.setEnabled(true);
        expect(viewer.init).toHaveBeenCalledTimes(2);
    });

    it('lets debug=0 override a saved enabled switch', () => {
        dom.window.localStorage.setItem('remote-mouse-debug', 'true');
        dom.window.history.replaceState(null, '', '/?debug=0');
        start();
        expect(dom.window.remoteMouseDebug.isEnabled()).toBe(false);
        expect(script()).toBeNull();
    });

    it('shows a readable fallback and collected errors if Eruda cannot load', () => {
        dom.window.history.replaceState(null, '', '/?debug=1');
        start();
        script().dispatchEvent(new dom.window.Event('error'));
        dom.window.dispatchEvent(new dom.window.ErrorEvent('error', { message: 'App failed' }));
        expect(dom.window.document.getElementById('debug-fallback')!.textContent).toContain('App failed');
        dom.window.remoteMouseDebug.setEnabled(false);
        expect(dom.window.document.getElementById('debug-fallback')).toBeNull();
    });

    it('shows a fallback when Eruda itself fails to initialize', () => {
        dom.window.history.replaceState(null, '', '/?debug=1');
        start();
        viewer.init.mockImplementation(() => { throw new Error('Storage unavailable'); });
        loaded();
        expect(dom.window.document.getElementById('debug-fallback')!.textContent).toContain('Storage unavailable');
    });
});
