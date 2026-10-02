"""Use the supported X11 tray backend without requiring GI on Linux."""

import os
import sys

if sys.platform == "linux":
    os.environ.setdefault("PYSTRAY_BACKEND", "xorg")
