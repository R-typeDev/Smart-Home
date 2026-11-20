
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import WEB_DIR
from database.schema import initialize_database
from handlers.bootstrap import register_core_handlers
from integrations.bootstrap import register_integrations
from routes import devices, integrations, network, pages


app = FastAPI(
    title="Smart Home API",
    description="API for the Smart Home platform",
    version="0.1.0",
)

# Initialize SQLite.
initialize_database()
register_core_handlers()
register_integrations()


@app.get("/health")
def health():
    return {"status": "ok"}


# API routes.
app.include_router(pages.router)
app.include_router(devices.router)
app.include_router(integrations.router)
app.include_router(network.router)


# Static files.
app.mount(
    "/assets",
    StaticFiles(directory=WEB_DIR / "assets"),
    name="assets",
)

app.mount(
    "/languages",
    StaticFiles(directory=WEB_DIR / "languages"),
    name="languages",
)

app.mount(
    "/components",
    StaticFiles(directory=WEB_DIR / "components"),
    name="components",
)

app.mount(
    "/integrations",
    StaticFiles(directory=WEB_DIR / "integrations"),
    name="integration-static",
)

app.mount(
    "/pages",
    StaticFiles(directory=WEB_DIR / "pages"),
    name="pages-static",
)


# SPA fallback.
@app.get("/")
@app.get("/{full_path:path}")
def serve_spa(full_path: str = ""):
    # Do not return index.html for missing files.
    if full_path and "." in full_path.split("/")[-1]:
        raise HTTPException(status_code=404, detail="Not Found")

    return FileResponse(WEB_DIR / "index.html")
