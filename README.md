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

Remote Mouse turns your phone into a wireless mouse, keyboard and remote control for your computer. Install it on your computer, then open a page on your phone to get started.

Works with iPhone and Android phones, and Windows, macOS and Linux computers.

## What you can do

- **Control your computer**: Move the pointer, click, scroll and drag from your phone.
- **Type on your phone**: Enter text directly, or edit it first and send it all at once.
- **Watch videos comfortably**: Switch to TV mode for playback, fullscreen, volume and mute controls.
- **Make it your own**: Adjust sensitivity, switch between light and dark themes, or add the page to your phone’s Home Screen where supported.

## Install on your computer

Download the file for your computer from the [download page](https://github.com/rust17/remote-mouse/releases).

### Windows

1. Download the file ending in `-setup.exe` and install it.
2. Open **Remote Mouse** from the Start menu.
3. If the firewall asks, allow access on private networks.

For a version that needs no installation, download `-portable.zip`, extract the whole folder and run `RemoteMouse.exe`. Keep the files together.

### macOS

1. For an M-series Mac, choose `macos-arm64`; for an Intel Mac, choose `macos-x86_64`.
2. Open the downloaded file, drag **RemoteMouse** into Applications and launch it. Look for its icon in the menu bar.
3. Go to **System Settings > Privacy & Security > Accessibility** and enable RemoteMouse. This lets it control your mouse and keyboard.

If macOS blocks the app on first launch, confirm that you downloaded it from this project, then allow it to open in **Privacy & Security**.

### Linux

Extract `linux-x86_64.tar.gz` and run `RemoteMouse` from the extracted folder. Use an X11 desktop; Wayland is not supported. The included `README.txt` explains any extra components your system needs. To restart the app, close it and open it again.

## Connect your phone

1. Connect your phone and computer to the same Wi-Fi network.
2. Keep Remote Mouse running on your computer.
3. Open [http://remote-mouse.local:9997](http://remote-mouse.local:9997) in your phone’s browser.
4. If that address does not work, use your computer’s address instead, for example `http://192.168.1.10:9997`. Find it in the Remote Mouse tray menu on Windows/macOS or your computer’s network settings.

You can add the page to your Home Screen for easier access if your browser offers that option. Your computer still needs to be on and running Remote Mouse while you use it.

## Use your phone as a mouse and keyboard

Choose the **computer icon** at the top for everyday computer use, or the **TV icon** for watching videos.

| Gesture | What it does |
| --- | --- |
| Slide one finger | Move the pointer |
| Tap once | Left click |
| Tap with two fingers | Right click |
| Slide two fingers | Scroll |
| Slide on the side strip | Scroll with one finger |
| Slide three fingers | Drag; lift a finger to release |

Tap the **keyboard icon** to type. **Live input** appears on the computer as you type. **Edit then send** lets you prepare the text on your phone and tap Send when it is ready. In this mode, Enter confirms on the computer; use Send to transfer the text.

Switching modes or opening settings closes the keyboard panel. Your unsent draft stays available until you send it or reload the page.

The **settings icon** lets you change sensitivity, the side strip’s position, theme and language. A green ring around the mode buttons means connected, yellow means connecting, and red means disconnected.

## Watch videos in TV mode

- **Play / pause**: Uses the player’s Space shortcut.
- **Rewind / forward**: Uses the player’s left/right arrow shortcuts. How far it skips depends on the player.
- **Fullscreen**: Double-clicks where the computer pointer is. Press again to leave fullscreen if your player supports it.
- **Volume − / +**: Changes the computer’s volume by 5 points and turns sound back on if muted.
- **Mute**: Turns the computer’s sound off or back on.

## If something does not work

- **The page will not open**: Check that the app is running, both devices are on the same network, and the computer’s firewall allows access. Try the computer’s IP address instead of the `.local` address.
- **The pointer or keyboard does not respond**: On macOS, check the Accessibility permission. On Windows, controlling an app opened as administrator also requires opening Remote Mouse as administrator.
- **Video controls do nothing**: Click the player on the computer again. Check that Space, arrow keys and a double click work in that player.
- **Some buttons are greyed out**: That control is unavailable. For volume, check that the computer has an audio output; on Linux, follow the sound setup in the included `README.txt`. Updating the computer app may help if it is an older version.

## For developers

See the [project guide](AGENTS.md) for source setup and tests, and the [packaging guide](packaging/README.md) for building and releasing the app.
