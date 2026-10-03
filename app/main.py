from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app import database, models
from app.routers.history import router as history_router
from app.services.chats import ChatSaveError


class FrontendFiles(StaticFiles):
    """Serve the Vite build with an HTML-only fallback for client routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        # Reserved backend paths must never fall back to React.
        first_part = next(iter(Path(path).parts), "")
        if first_part in {"api", "health"}:
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code == 404
                and scope["method"] in {"GET", "HEAD"}
                and "text/html" in Headers(scope=scope).get("accept", "")
                and not Path(path).suffix
                and first_part != "assets"
            ):
                return await super().get_response("index.html", scope)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not app.state.session_secret:
        raise RuntimeError("SECRET_KEY must be configured before startup")
    database.initialize_database(database.engine)
    try:
        yield
    finally:
        database.engine.dispose()


def health():
    return {"status": "ok"}


def root():
    return {"message": "Hello, Codyssey!"}


async def chat_save_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Failed to save chat"})


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    application = FastAPI(lifespan=lifespan)
    secret_key = os.getenv("SECRET_KEY", "").strip()
    application.state.session_secret = secret_key
    application.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        https_only=os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true",
    )
    application.add_exception_handler(ChatSaveError, chat_save_error_handler)
    application.add_api_route("/health", health, methods=["GET"])
    application.include_router(history_router)

    # Register future API routers above this mount so they take precedence.
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if (frontend_dist / "index.html").is_file():
        application.mount("/", FrontendFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        application.add_api_route("/", root, methods=["GET"])
    return application


app = create_app()
