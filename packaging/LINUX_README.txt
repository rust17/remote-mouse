Remote Mouse for Linux (x86_64, X11)

Start the app
1. Extract the whole archive. Keep all files together.
2. Run ./RemoteMouse/RemoteMouse in an X11 desktop session.
3. On your phone, open http://remote-mouse.local:9997.
   Keep your phone and computer on the same Wi-Fi.
   If the address does not work, use http://YOUR_COMPUTER_IP:9997.
   Find the IP in terminal output or your computer's network settings.

Requirements
Built on Ubuntu 22.04. Requires glibc 2.35+, libX11 and libXtst.
For clipboard text input, install xclip or xsel (e.g. sudo apt install xclip).
For system volume controls, install pactl (e.g. sudo apt install pulseaudio-utils)
and run a PulseAudio server or PipeWire with pipewire-pulse. Missing audio
support disables only audio controls. Playback uses the focused player
(space / arrow keys); fullscreen double-clicks at the current mouse position.
Wayland is not supported. You do not need Python or Node.js.

Options
Use --port PORT to change the port, or --log to save logs.
The tray has no right-click menu. Stop and relaunch the app to restart it.
Logs are in ~/.remote-mouse/logs and remain after removing the app.

Optional shortcut
Edit the paths in RemoteMouse.desktop to match where you extracted the app,
then copy it to ~/.local/share/applications/.
