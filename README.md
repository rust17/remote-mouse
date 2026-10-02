# <img src="docs/remote-mouse-icon.jpg" width="32" style="border-radius: 20%;" /> Remote Mouse

[English](README.md) | [简体中文](docs/README_ZH.md)

<p align="center">
  <img src="docs/remote-mouse.gif" width="1920" />
</p>

<p align="center">
  <img src="docs/dart.jpg" width="250" />
  <img src="docs/light.jpg" width="250" />
  <img src="docs/light-setting.jpg" width="250" />
</p>

---

Remote Mouse is a lightweight, low-latency remote control tool that transforms your mobile device (iOS/Android) into a wireless touchpad and keyboard for your computer (Windows/macOS/Linux).

### Features

- **PWA Support**: Install the web client as a native app on your phone for a full-screen experience.
- **Auto Discovery**: Automatically finds servers in the local network using mDNS.
- **Responsive Touchpad**: Low-latency cursor movement with adjustable sensitivity.
- **Full Keyboard Input**: Supports text input, function keys (Esc, Tab, Enter), and modifier keys (Ctrl, Alt, Shift, Win).
- **Modern UI**: Dark mode interface with a sleek, translucent design.
- **Cross-Platform**: Server runs on Python, client works in any modern mobile browser.

### Download & Run

Get the latest version from the [Releases](https://github.com/rust17/remote-mouse/releases) page.

#### Windows

1. Download the file ending in `-setup.exe`, install it, and open **Remote Mouse** from the Start menu.
2. For a portable version, download `-portable.zip`, extract the whole folder, and run `RemoteMouse.exe`. Keep all files together.
3. Allow private-network access if the firewall asks. Use **Run as Administrator** only to control apps that also run as administrator.

#### macOS

1. Download the DMG for your Mac: **Apple Silicon (M-series)** uses `macos-arm64`; **Intel** uses `macos-x86_64`.
2. Open the DMG, drag `RemoteMouse.app` into Applications, and launch it. Look for its icon in the menu bar.
3. In **System Settings > Privacy & Security > Accessibility**, add and enable RemoteMouse so it can control your mouse and keyboard.

The app is not Developer ID-signed or notarized. If macOS blocks it, check the download source and allow it to open in **Privacy & Security**.

#### Linux

1. Download the file ending in `linux-x86_64.tar.gz` and extract the whole folder.
2. Run `./RemoteMouse/RemoteMouse`. Use an **X11** desktop; Wayland is not supported. See the included `README.txt` for dependencies.
3. The Linux tray has no right-click menu. Restart the program to restart the service; use `--port` and `--log` to set the port and enable logs.

### Build & release

To build on your computer, install **Node.js 22, uv and Python 3.13**, then run from the repository root:

```bash
uv run --frozen --project server python packaging/build.py
```

Find the packages in `packaging/out/<platform>-<architecture>/products/`. See [the packaging guide](packaging/README.md) for platform requirements and release steps.

---

### Usage

1. Start the server on your computer.
2. Ensure your phone and computer are on the **same local network (Wi-Fi)**.
3. Find the access address:
   - Recommended: **http://remote-mouse.local:9997**
   - Alternative: Use your computer's IP address, for example `http://192.168.1.10:9997`. Find it in network settings or the tray menu on Windows/macOS.
4. Open the address in your mobile browser.
5. (Optional) Add to Home Screen to install as a PWA.
6. Start controlling!
