"""FastAPI application entrypoint.

Composition-root only: wires the app and its routers. No business logic
lives here — that belongs in each domain's `application`/`domain` layers.
"""

from fastapi import FastAPI

from gcell.api.health import router as health_router

app = FastAPI(title="GCELL API")
app.include_router(health_router)
