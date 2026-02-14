import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion_api import register_ingestion


def _allowed_origins():
    # Default to permissive "*" in dev so CORS headers are always present; tighten via CORS_ORIGINS env.
    raw = os.getenv("CORS_ORIGINS") or "*"
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="KEC Admin Ingestion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_origin_regex=None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount embedded auto-ingestion API under /ingestion to avoid route conflicts.
register_ingestion(app, prefix="/ingestion")


@app.get("/ingestion/health")
def ingestion_health_alias():
    # Alias to keep admin UI health checks stable even if router reload lags.
    pipeline = getattr(app.state, "pipeline", None)
    chroma_ok = False
    if pipeline:
        try:
            chroma_ok = True if pipeline.chroma_service.list_collections() is not None else False
        except Exception:
            chroma_ok = False
    return {"status": "ok" if chroma_ok else "degraded", "ingestion": True, "chroma": chroma_ok}


@app.get("/health")
def health():
    return {"status": "ok", "ingestion": True}
