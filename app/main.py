from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app import models  # noqa: F401  (registers the tables before initialization)
from app.config import configure_logging
from app.database import engine, initialize_database


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


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# Register future API routers above this mount so they take precedence.
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (frontend_dist / "index.html").is_file():
    app.mount("/", FrontendFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "Hello, Codyssey!"}
