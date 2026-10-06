declare global {
    interface Window {
        remoteMouseDebug?: {
            isEnabled(): boolean;
            setEnabled(enabled: boolean): void;
        };
    }
}

export function installDebugToggle(toggle: HTMLInputElement) {
    toggle.checked = window.remoteMouseDebug?.isEnabled() ?? false;
    toggle.addEventListener('change', () => window.remoteMouseDebug?.setEnabled(toggle.checked));
}
