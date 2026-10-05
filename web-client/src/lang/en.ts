import type { TranslationKeys } from './zh';

export const en: TranslationKeys = {
    status: {
        connecting: 'Connecting...',
        connected: 'Connected',
        disconnected: 'Disconnected',
        error: 'Connection Error',
        failed: 'Connection Failed',
    },
    settings: {
        title: 'Settings',
        mouse_sensitivity: 'Mouse Sensitivity',
        scroll_sensitivity: 'Scroll Sensitivity',
        input_mode: 'Input Method',
        light_mode: 'Light Mode',
        scroll_bar_right: 'Scroll Bar Right',
        rate_monitor: 'Rate Monitor',
        language: 'Language',
    },
    ui: {
        close: 'Close',
    },
    mode: { label: 'Control mode', computer: 'Computer mode', tv: 'TV mode' },
    mouse: { touchpad: 'Touchpad', scroll: 'Single-finger scrolling' },
    input: {
        open: 'Open keyboard', close: 'Close keyboard', realtime: 'Live input', draft: 'Edit then send',
        draft_text: 'Text to send', send: 'Send text', not_sent: 'Disconnected. Draft was not sent.',
        function_keys: 'Computer function keys', select_all: 'Select all', enter: 'Confirm (Enter)',
        backspace: 'Backspace', tab: 'Tab', up: 'Up', down: 'Down', left: 'Left', right: 'Right',
    },
    media: {
        audio_dependency: 'Audio dependency missing (Windows: pycaw; Linux: pactl)', audio_permission: 'System audio permission required', audio_no_device: 'No default audio output device',
        detecting: 'Detecting media capabilities…', system_volume: 'System volume',
        hint: 'Focus the player; move the computer cursor onto the video before fullscreen',
        sending: 'Executing…', issued: 'Input sent; player state unknown',
        verified: 'System volume / mute verified', failed: 'Execution failed; check unavailable controls',
        timeout: 'No receipt; outcome unknown. No automatic retry',
        input_permission: 'Computer accessibility permission required', input_unsupported: 'Input unsupported on this desktop',
        drag_busy: 'Double-click unavailable during drag', audio_unavailable: 'Audio unavailable: check dependencies, permissions and default output',
        execution_failed: 'Operation failed or system did not confirm the change',
        label: 'TV media controls', unavailable: 'Media controls need server support',
        rewind: 'Rewind', play_pause: 'Play / Pause', forward: 'Fast forward',
        volume_down: 'Lower volume', mute: 'Toggle mute', volume_up: 'Raise volume', fullscreen: 'Computer player fullscreen',
    },
};
