import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app import models  # noqa: F401  (registers the tables before initialization)
from app.config import configure_logging, get_session_settings
from app.database import engine, initialize_database
from app.routers import auth, chat

logger = logging.getLogger(__name__)


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
    configure_logging()
    initialize_database(engine)
    yield
    engine.dispose()


session_settings = get_session_settings()
app = FastAPI(lifespan=lifespan)

# 세션 쿠키 서명 및 14일 유지
app.add_middleware(
    SessionMiddleware,
    secret_key=session_settings.secret_key,
    max_age=14 * 24 * 60 * 60,
    same_site="lax",
    https_only=session_settings.https_only,
)


@app.middleware("http")
async def log_api_request(request: Request, call_next):
    # The id ties this request to the AI call and save logs that follow.
    request.state.request_id = uuid.uuid4().hex[:12]
    if request.url.path.startswith("/api/"):
        logger.info(
            "request_received request_id=%s method=%s path=%s",
            request.state.request_id, request.method, request.url.path,
        )
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


# API routers are registered above the frontend mount so they take precedence.
app.include_router(auth.router)
app.include_router(chat.router)

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (frontend_dist / "index.html").is_file():
    app.mount("/", FrontendFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "Hello, Codyssey!"}
