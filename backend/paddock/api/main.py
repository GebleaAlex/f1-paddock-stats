"""FastAPI application. All routes live under /api and only read from the database."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .. import config
from .routes import (
    analysis,
    circuits,
    conditions,
    constructors,
    drivers,
    explore,
    insights,
    meta,
    og,
    races,
    records,
    seasons,
    simulate,
    teammates,
    telemetry,
)

app = FastAPI(
    title="Paddock Stats API",
    description=(
        "Formula 1 history from 1950 with lap-by-lap data from 1996. Unofficial, not associated with the Formula 1 "
        "companies. Data: f1db (CC BY 4.0) and Jolpica-F1 (CC BY-NC-SA 4.0)."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET"], allow_headers=["*"])


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    # The data only changes when the pipeline runs (after each race weekend), so short public caching is safe.
    if request.method == "GET" and response.status_code == 200 and request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "public, max-age=300, stale-while-revalidate=3600")
    return response


@app.get("/api/health", tags=["meta"])
def health():
    return {"ok": True}


for module in (meta, seasons, races, drivers, constructors, circuits, teammates, records):
    app.include_router(module.router, prefix="/api")
app.include_router(seasons.points_router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(analysis.circuit_router, prefix="/api")
app.include_router(drivers.compare_router, prefix="/api")
app.include_router(telemetry.router, prefix="/api")
app.include_router(telemetry.driver_router, prefix="/api")
app.include_router(telemetry.season_router, prefix="/api")
app.include_router(explore.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(og.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(conditions.router, prefix="/api")
