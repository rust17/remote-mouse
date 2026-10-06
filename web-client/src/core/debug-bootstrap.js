// Injected inline before the application module so startup failures remain visible.
(function () {
    var key = 'remote-mouse-debug';
    var query = new URLSearchParams(window.location.search).get('debug');
    var saved = false;
    try { saved = window.localStorage.getItem(key) === 'true'; } catch (_) {}
    var enabled = query === null ? saved : query === '1';
    var loading = false;
    var initialized = false;
    var pending = [];
    var fallback = null;
    var originalConsoleError = null;
    var captureConsoleError = null;

    function showFallback(message) {
        if (!enabled) return;
        if (!fallback) {
            fallback = document.createElement('details');
            fallback.id = 'debug-fallback';
            fallback.open = true;
            fallback.style.cssText = 'position:fixed;bottom:12px;left:12px;right:12px;z-index:2147483647;padding:12px;background:#171717;color:#fff;border-radius:8px;font:12px monospace;max-height:40vh;overflow:auto';
            var title = document.createElement('summary');
            title.textContent = 'Debug / 调试信息';
            fallback.appendChild(title);
            var output = document.createElement('pre');
            output.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere';
            fallback.appendChild(output);
            document.documentElement.appendChild(fallback);
        }
        fallback.lastChild.textContent = message + '\n\n' + pending.join('\n\n');
    }

    function record(message) {
        if (!enabled) return;
        if (initialized) {
            window.eruda.get('console').error(message);
        } else {
            pending.push(message);
            if (pending.length > 50) pending.shift();
            if (fallback) showFallback('Eruda unavailable / 调试控制台不可用');
        }
    }

    window.addEventListener('error', function (event) {
        if (event.target && event.target !== window) {
            var resource = event.target.src || event.target.href;
            if (resource) record('Resource failed to load: ' + resource);
        } else {
            record(event.error && event.error.stack || event.message + '\n' + event.filename + ':' + event.lineno);
        }
    }, true);
    window.addEventListener('unhandledrejection', function (event) {
        record(event.reason && event.reason.stack || String(event.reason));
    });

    function initialize() {
        if (!enabled || initialized) return;
        try {
            window.eruda.init({ tool: ['console', 'network', 'info'], useShadowDom: true });
            window.eruda.get('console').config.set('catchGlobalErr', false);
            initialized = true;
            if (fallback) { fallback.remove(); fallback = null; }
            pending.forEach(function (message) { window.eruda.get('console').error(message); });
            pending = [];
        } catch (error) {
            try { window.eruda.destroy(); } catch (_) {}
            showFallback('Eruda failed to start: ' + (error && error.stack || String(error)));
        }
    }

    function load() {
        if (!captureConsoleError) {
            originalConsoleError = window.console.error;
            var originalError = originalConsoleError;
            captureConsoleError = function () {
                if (enabled && !initialized) {
                    var message = Array.prototype.map.call(arguments, function (value) {
                        return value && value.stack || String(value);
                    }).join(' ');
                    record(message);
                }
                return originalError.apply(window.console, arguments);
            };
            window.console.error = captureConsoleError;
        }
        if (window.eruda) { initialize(); return; }
        if (loading) return;
        loading = true;
        var script = document.createElement('script');
        script.src = '/debug/eruda.js';
        script.onload = function () {
            loading = false;
            if (window.eruda) initialize();
            else { script.remove(); showFallback('Eruda failed to load / 调试控制台加载失败'); }
        };
        script.onerror = function () {
            loading = false;
            script.remove();
            showFallback('Eruda failed to load / 调试控制台加载失败');
        };
        document.head.appendChild(script);
    }

    window.remoteMouseDebug = {
        isEnabled: function () { return enabled; },
        setEnabled: function (value) {
            enabled = value;
            try { window.localStorage.setItem(key, String(value)); } catch (_) {}
            // The setting takes precedence over a debug link on subsequent reloads.
            try {
                var url = new URL(window.location.href);
                url.searchParams.delete('debug');
                window.history.replaceState(window.history.state, '', url);
            } catch (_) {}
            if (enabled) load();
            else {
                if (initialized) window.eruda.destroy();
                if (window.console.error === captureConsoleError) window.console.error = originalConsoleError;
                captureConsoleError = null;
                originalConsoleError = null;
                initialized = false;
                pending = [];
                if (fallback) { fallback.remove(); fallback = null; }
            }
        }
    };
    if (enabled) load();
})();
