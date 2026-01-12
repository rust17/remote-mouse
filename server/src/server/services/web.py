from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from loguru import logger

from server.core.protocol import process_binary_command, reset_input_state
from server.config import get_static_dir


def create_app() -> FastAPI:
    app = FastAPI()
    static_dir = get_static_dir()

    if not static_dir.exists():
        logger.warning(f"Static directory {static_dir} does not exist!")

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
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
