from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger

from server.core.protocol import process_binary_command
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
        except Exception as e:
            logger.error(f"WebSocket error: {e}")

    # SPA Fallback for 404 errors
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: StarletteHTTPException):
        index_path = static_dir / "index.html"
        if index_path.exists():
            logger.debug(f"404 for {request.url.path}, falling back to index.html")
            return FileResponse(index_path)
        
        logger.warning(f"404 for {request.url.path} and index.html not found in {static_dir}")
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    # 挂载静态文件（必须放在最后，否则可能覆盖 API 路由）
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
