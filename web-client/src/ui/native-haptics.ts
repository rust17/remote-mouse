// Newer iOS requires a real tap on a native switch; script-generated clicks
// on the hidden switch used by web-haptics no longer produce feedback.
export function installNativeHapticTargets(root: HTMLElement) {
    const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent)
        || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (!isIOS || typeof navigator.vibrate === 'function') return;
    if (!('switch' in document.createElement('input'))) return;

    root.querySelectorAll<HTMLButtonElement>('button').forEach(button => {
        if (button.closest('.native-haptic-target')) return;

        // Keep the button for keyboard/accessibility activation. The native
        // control is its sibling, avoiding nested interactive elements.
        const wrapper = document.createElement('span');
        wrapper.className = 'native-haptic-target';
        wrapper.style.setProperty('--haptic-radius', getComputedStyle(button).borderRadius);
        button.before(wrapper);
        wrapper.append(button);

        const input = document.createElement('input');
        input.type = 'checkbox';
        input.setAttribute('switch', '');
        input.className = 'native-haptic-switch';
        input.tabIndex = -1;
        input.setAttribute('aria-hidden', 'true');
        input.addEventListener('click', event => {
            // Leave native activation uncancelled so WebKit can produce the
            // tick. Forward the action synchronously to retain user activation
            // for opening the software keyboard, and execute it only once.
            event.stopPropagation();
            if (!button.disabled) button.click();
        });
        wrapper.append(input);
    });

    // Existing settings switches already carry their own change handlers.
    root.querySelectorAll<HTMLInputElement>('.switch > input[type="checkbox"]').forEach(input => {
        input.setAttribute('switch', '');
        input.classList.add('native-haptic-switch');
    });
}
