from pathlib import Path

from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

WEB_MEDIA_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".webmanifest": "application/manifest+json",
}


class WebStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse) or response.status_code == 304:
            # Windows registry associations can override Python's MIME guesses.
            resource = response.path if isinstance(response, FileResponse) else path
            media_type = WEB_MEDIA_TYPES.get(Path(resource).suffix.lower())
            if media_type:
                response.media_type = media_type
                response.headers["content-type"] = (
                    f"{media_type}; charset=utf-8" if media_type.startswith("text/") else media_type
                )
        return response
