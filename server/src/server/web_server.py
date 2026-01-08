import logging
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from server.protocol import process_binary_command, reset_input_state

from loguru import logger

app = FastAPI()

# 静态资源路径配置
# 1. 开发环境: 指向源码目录 ../../../web-client/dist
# 2. 打包环境 (PyInstaller): 指向 sys._MEIPASS/web_dist
if getattr(sys, "frozen", False):
    bundle_dir = Path(sys._MEIPASS)
    STATIC_DIR = bundle_dir / "web_dist"
else:
    project_root = Path(__file__).resolve().parents[3]
    STATIC_DIR = project_root / "web-client" / "dist"

if not STATIC_DIR.exists():
    logger.warning(f"Static directory {STATIC_DIR} does not exist!")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"WebSocket client connected: {websocket.client}")
    try:
        while True:
            data = await websocket.receive_bytes()
            process_binary_command(data)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        reset_input_state()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        reset_input_state()


# 挂载静态文件（必须放在最后，否则可能覆盖 API 路由）
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
