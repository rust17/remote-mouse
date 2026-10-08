# Changelog

All notable changes to this project will be documented in this file.

# [v1.1.3] - 2026-10-08

### Added

- **Web Client**: Added an optional Eruda debug console for viewing errors on a phone. Enable Debug Mode in Settings, or append `?debug=1` to the page URL if the interface cannot start.
- **Web Client**: Capture startup errors and provide a fallback error viewer when the debug console cannot initialize.

### Changed

- **Docs**: Refreshed English and Chinese guides with new product visuals and mobile troubleshooting instructions.

### Fixed

- **Web Client**: Fixed startup failures when browser storage is unavailable. The interface now works with default preferences when settings cannot be saved.
- **Server**: Fixed incorrect JavaScript and stylesheet response types caused by system MIME settings, which could prevent the controller from loading on Windows.

# [v1.1.2] - 2026-10-05

### Added

- **Web Client**: Added computer and TV modes with a shared touchpad and keyboard. TV mode provides playback, seeking, fullscreen, volume and mute controls.
- **Web Client**: Added live input and edit-then-send text entry, preserving unsent drafts when closing the panel or switching modes.
- **Server**: Added system volume and mute control for macOS, Windows and Linux, with actual audio state reported to the phone.
- **Server**: Added media capability detection and execution results. Unavailable controls are disabled, and timed-out or disconnected media actions are not automatically retried.

### Changed

- **Web Client**: Unified touchpad gestures across computer and TV modes, removing the TV single-tap delay and double-tap right click.
- **Web Client**: Refined mode tabs, keyboard selection and connection feedback, and added a slim volume indicator without a numeric percentage.
- **Web Client**: Switching modes or opening settings now closes the keyboard panel.
- **Server**: Input and audio operations now run on separate serial worker threads to keep connections responsive.
- **Docs**: Updated English and Chinese usage guides, project guidance and interaction design notes.

### Fixed

- **Server**: Fixed macOS fullscreen double clicks being interpreted as separate clicks.
- **Server**: Release dragged mouse buttons on disconnect or shutdown, and prevent conflicting operations from other connections.
- **Web Client**: Ignore messages from obsolete connections and expired media updates.
- **Web Client**: Fixed the settings button retaining a focus outline after dismissing the dialog by touch, and restored button haptics on newer iOS versions.
- **Web Client**: Fixed the top-edge display in the iOS 27 Home Screen app.

# [v1.1.1] - 2026-10-03

### Added

- **Build**: Added macOS DMGs, a Windows installer and portable ZIP, and a Linux archive, with bundled web assets.
- **Release**: Added multi-platform build and smoke checks, plus artifact checksums and build identity verification before publishing.

### Changed

- **Release**: Releases now build from an existing version tag through a manually started workflow.
- **Docs**: Added platform installation, packaging and release instructions.

### Fixed

- **Build**: Fixed cross-platform packaging checks.

# [v1.1.0] - 2026-04-06

### Added
- **Web Client**: Implemented internationalization (i18n) support with Chinese and English translations.
- **Web Client**: Integrated haptic feedback using `web-haptics` for button interactions and slider adjustments.
- **Web Client**: Added visual click feedback for non-modifier functional keys.

### Changed
- **Web Client**: Optimized iOS compatibility and keyboard layout, ensuring functional keys remain accessible when the system keyboard is open.
- **Web Client**: Refactored theme switching to apply classes to the root `<html>` element for improved CSS targeting.
- **Web Client**: Refactored `ConnectionStatus` to use constant objects for better type safety.

### Fixed
- **Web Client**: Fixed UI glitches in FAB (Floating Action Button) positioning relative to the function panel.

# [v1.0.5] - 2026-03-15

### Added
- **Server**: Added real-time rate monitoring (Packets Per Second and Bytes Per Second) to the system tray icon.
- **Server**: Added a "Show Rate" toggle to the system tray menu for real-time performance tracking.
- **Server**: Implemented dynamic tray icon rendering with text overlay and automatic font fallback for cross-platform compatibility.
- **Docs**: Added `AGENTS.md` to provide specialized instructions for AI coding assistants.

### Fixed
- **Server**: Resolved mDNS service name conflicts when running multiple instances in development environments.
- **Web Client**: Improved connection status display and transport layer metrics collection.

# [v1.0.4] - 2026-03-14

### Fixed
- **Server**: Resolved a critical 404 error affecting long-term application uptime by ensuring static files are correctly persisted and served from the application package.

# [v1.0.3] - 2026-01-18

### Added
- **Server**: Added a "Restart" option to the system tray menu. Now uses service-level soft restart to instantly reload the web server and mDNS without restarting the process.
- **Server**: Added a "Enable/Disable Logs" toggle to the system tray menu for real-time logging control.
- **Server**: Added command-line arguments (`--port`, `--log`) to configure the initial port and logging state.

### Fixed
- **Server**: Fixed a crash on Windows when restarting the application in packaged (PyInstaller) builds by replacing process spawning with internal service reloading.
- **Server**: Fixed a crash in non-console environments (like Windows GUI mode) caused by logging configuration.
- **Server**: Fixed an issue where toggling logs off did not correctly release file handlers.

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
