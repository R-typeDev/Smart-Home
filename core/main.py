
from fastapi import FastAPI

from routes import devices, network, pages

app = FastAPI(
    title="Smart Home API",
    description="API for the Smart Home platform",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(pages.router)
app.include_router(network.router)
app.include_router(devices.router)
