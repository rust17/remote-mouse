// Saving preferences is optional; storage restrictions must not disable controls.
export function readPreference(key: string): string | null {
    try {
        return window.localStorage.getItem(key);
    } catch {
        return null;
    }
}

export function writePreference(key: string, value: string): void {
    try {
        window.localStorage.setItem(key, value);
    } catch {
        // The caller still applies the change for the current page session.
    }
}
