# Changelog

All notable changes to this project will be documented in this file.

# [v1.0.3] - 2026-01-18

### Added
- **Server**: Added a "Restart" option to the system tray menu to restart the entire application.
- **Server**: Added a "Enable/Disable Logs" toggle to the system tray menu for real-time logging control.
- **Server**: Added command-line arguments (`--port`, `--log`) to configure the initial port and logging state.
- **Server**: Implemented graceful restart logic that preserves command-line arguments and releases system resources properly.

# [v1.0.2] - 2026-01-17

### Added
- **UI**: Added Light Mode toggle and theming support.
- **Settings**: Added scroll position toggle (left/right) for better accessibility.

### Changed
- **Docs**: Updated README with new screenshots showing different modes.
- **CI**: Updated release workflow artifact paths.

# [v1.0.1] - 2026-01-17

### Added
- **Settings**: Enhanced sensitivity settings and added a scroll sensitivity feature.
- **UI**: Added scroll slider to the settings zone.
- **Build**: Added support for macOS bundler (`.app` creation) and linux.
- **Docs**: Added `README` documentation and `PWA`.
- **UI**: Update function keys layout and improve navigation controls.

### Changed
- **Refactor**: General refactoring of both server and frontend codebases for better maintainability.
- **Optimization**: Optimized application size.

# [v1.0.0] - 2026-01-14
## Special Function Keys

### Added
- **UI**: Added a "Special Function Keys" panel containing Esc, Tab, Win/Cmd, Alt, Shift, Ctrl, and Arrow keys.
- **Interaction**: Implemented "Sticky Keys" logic for modifier keys (Ctrl, Alt, Shift, Win/Cmd), allowing for easier combination key presses (e.g., Ctrl+C).
- **Protocol**: Updated communication protocol to support modifier masks for `Click` and `KeyAction` events.

## Keyboard Input

### Added
- **Input**: Added support for using the mobile device's native keyboard to type on the remote computer.
- **UI**: Added a bottom toolbar with a keyboard toggle button.
- **Protocol**: Introduced `Text` (0x05) and `KeyAction` (0x06) opcodes for handling text strings and specific key presses (like Enter, Backspace).

## Web Client

### Changed
- **Architecture**: **Major Overhaul**. Replaced the native mobile app (Flutter) with a **Zero-Install Web Client**. No app installation required on the phone.
- **Protocol**: Switched to a custom **Binary WebSocket Protocol** for high-performance, low-latency communication.
- **Discovery**: Implemented **mDNS (Zeroconf)** for automatic service discovery. Users can now access the controller via `http://hostname.local:port`.

### Added
- **Server**: Migrated backend to **Python 3.13+** using **FastAPI** for serving the web client and handling WebSockets.
- **Client**: Built with **TypeScript** and **HTML5**, utilizing `requestAnimationFrame` for 60FPS smooth control.

## Fluid

### Changed
- **Server**: Refactored server into a GUI application with **System Tray** support (minimizes to tray, right-click to exit).
- **UX**: Replaced button-based UI with a **Full-Screen Touchpad** experience.
- **Gestures**:
    - **One finger**: Move cursor, tap to left-click.
    - **Two fingers**: Scroll (directionally), tap to right-click.
    - **Three fingers**: Drag and drop.

### Added
- **Layout**: Added support for Landscape mode.
- **Settings**: Added sensitivity controls for cursor movement.

## MVP

### Added
- Initial release of Remote Mouse.
- **Client**: Flutter-based mobile application (iOS/Android).
- **Server**: Python script using `socket` and `pyautogui`.
- **Features**:
    - Automatic device discovery via UDP broadcast.
    - Basic touchpad area for cursor movement.
    - Dedicated Left/Right click buttons.
    - Dedicated Scroll Strip for vertical scrolling.
    - Basic text transmission.

## Versioning
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).