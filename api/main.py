from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.middleware import setup_cors
from api.deps import get_db, get_registry
from api.routes import articles, entities, graph, search, resolve
from api.routes import markets
from api import ws
from db.database import Database
from pipeline.entity_registry import EntityRegistry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    db = Database()
    await db.init()
    app.state.db = db
    app.state.registry = EntityRegistry(db)
    yield
    # shutdown
    await db.close()

app = FastAPI(title="Sugar Protocol API", version="0.1.0", lifespan=lifespan)
setup_cors(app)

app.include_router(articles.router, prefix="/api")
app.include_router(entities.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(resolve.router)  # CRE-B: /api/resolve (no prefix — router has its own)
app.include_router(markets.router, prefix="/api")  # S10: Truth Markets
app.include_router(ws.router)

# ---- Static Frontend (Docker production) ----
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve frontend SPA — fallback to index.html for client-side routing."""
        file = _static_dir / path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_static_dir / "index.html"))