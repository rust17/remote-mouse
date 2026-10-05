import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from loguru import logger
from server.config import get_static_dir
from server.core.metrics import metrics
from server.core.protocol import (
    OP_MEDIA,
    OP_MEDIA_QUERY,
    MediaCommand,
    decode_media_command,
    process_binary_command,
)
from server.services.media import MediaService
from server.ui.tray_icon import TrayIcon


def create_app(service_factory=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.media = (
            service_factory or (lambda: MediaService(lambda data: process_binary_command(data)))
        )()
        try:
            yield
        finally:
            await app.state.media.close()

    app = FastAPI(lifespan=lifespan)
    static_dir = get_static_dir()

    if not static_dir.exists():
        logger.warning(f"Static directory {static_dir} does not exist!")

    @app.post("/api/settings/tray/rate")
    async def toggle_server_rate(enabled: bool):
        if TrayIcon.instance:
            TrayIcon.instance.set_show_rate(enabled)
        return {"status": "ok"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        logger.info(f"WebSocket client connected: {websocket.client}")
        owner = object()
        service = websocket.app.state.media
        tasks = set()
        query_id = 0
        send_lock = asyncio.Lock()

        async def send(message):
            async with send_lock:
                await websocket.send_json(message)

        async def reply(command, query_id):
            try:
                if isinstance(command, MediaCommand):
                    _, snapshot = await service.execute_media(command, on_result=send)
                    await send(snapshot)
                else:
                    snapshot = await service.snapshot(reprobe=query_id == 1)
                    snapshot["queryId"] = query_id
                    await send(snapshot)
            except Exception as e:
                logger.warning("Media response failed: {}", e)

        try:
            while True:
                data = await websocket.receive_bytes()
                metrics.add(len(data))
                if data and data[0] in (OP_MEDIA, OP_MEDIA_QUERY):
                    try:
                        command = decode_media_command(data)
                    except ValueError:
                        await send(
                            {
                                "type": "media_protocol_error",
                                "version": 1,
                                "errorCode": "invalid_packet",
                            }
                        )
                        continue
                    if not isinstance(command, MediaCommand):
                        query_id += 1
                    task = asyncio.create_task(reply(command, query_id))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                    # Enqueue this media input before accepting the next input packet.
                    await asyncio.sleep(0)
                else:
                    await service.input_call(service.input.execute, owner, data)
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.shield(service.release(owner))

    # 挂载静态文件（必须放在最后，否则可能覆盖 API 路由）
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
