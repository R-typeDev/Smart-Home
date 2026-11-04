from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import WEB_DIR
from database.schema import initialize_database
from integrations.bootstrap import register_integrations
from routes import devices, integrations, pages


app = FastAPI(
    title="Smart Home API",
    description="API for the Smart Home platform",
    version="0.1.0",
)

# Initialize SQLite before discovering adapters.
initialize_database()
register_integrations()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(pages.router)
app.include_router(devices.router)
app.include_router(integrations.router)


app.mount(
    "/assets",
    StaticFiles(directory=WEB_DIR / "assets"),
    name="assets",
)

app.mount(
    "/locales",
    StaticFiles(directory=WEB_DIR / "locales"),
    name="locales",
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
