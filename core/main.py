
from fastapi import FastAPI

app = FastAPI(
    title="Smart Home API",
    description="API for the Smart Home platform",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "Smart Home",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
