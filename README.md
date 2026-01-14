# Remote Mouse

[English](README.md) | [简体中文](README_ZH.md)

---

Remote Mouse is a lightweight, low-latency remote control tool that transforms your mobile device (iOS/Android) into a wireless touchpad and keyboard for your computer (Windows/macOS/Linux).

### Features

- **PWA Support**: Install the web client as a native app on your phone for a full-screen experience.
- **Auto Discovery**: Automatically finds servers in the local network using mDNS.
- **Responsive Touchpad**: Low-latency cursor movement with adjustable sensitivity.
- **Full Keyboard Input**: Supports text input, function keys (Esc, Tab, Enter), and modifier keys (Ctrl, Alt, Shift, Win).
- **Modern UI**: Dark mode interface with a sleek, translucent design.
- **Cross-Platform**: Server runs on Python, client works in any modern mobile browser.

### Download & Run (For Users)

Get the latest version from the [Releases](https://github.com/your-username/remote-mouse/releases) page.

#### Windows
1. Download `RemoteMouse.exe`.
2. **Right-click** and select **"Run as Administrator"** (Required for controlling certain applications).
3. Allow access if prompted by Windows Firewall.

#### macOS
1. Download the `RemoteMouse` binary.
2. Open Terminal and make it executable:
   ```bash
   chmod +x ~/Downloads/RemoteMouse
   ```
3. Right-click the file in Finder and select **"Open"**.
4. **Grant Permissions**: Go to `System Settings` > `Privacy & Security` > `Accessibility` and add/enable `RemoteMouse`. Without this, the server cannot move the cursor.

---

### Development

#### Tech Stack
- **Server**: Python 3.12+, FastAPI, PyAutoGUI, Zeroconf, uv
- **Web Client**: TypeScript, Vite, PWA

#### Setup
**1. Server**
```bash
cd server
uv sync
uv run python -m server.main
```

**2. Web Client**
```bash
cd web-client
npm install
npm run build
# The client is served by the Python server automatically.
# For dev mode with hot-reload:
npm run dev
```

### Usage
1. Start the server on your computer.
2. Ensure your phone and computer are on the **same local network (Wi-Fi)**.
3. Find the access address:
   - Recommended: **http://remote-mouse.local:9997**
   - Alternative: Right-click the **tray icon** on your computer to see the IP address (e.g., `http://192.168.1.10:9997`).
4. Open the address in your mobile browser.
5. (Optional) Add to Home Screen to install as a PWA.
6. Start controlling!
