import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion_api import register_ingestion, create_ingestion_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve storage paths relative to the server/ directory
# ---------------------------------------------------------------------------
_SERVER_DIR = Path(__file__).resolve().parent.parent  # server/

_FACULTY_CHROMA = str(_SERVER_DIR / "faculty" / "faculty_db")
_FACULTY_UPLOADS = str(_SERVER_DIR / "faculty" / "uploads")
_FACULTY_METADATA = str(_SERVER_DIR / "faculty" / "ingestion_metadata.db")

_STUDENT_2024_CHROMA = str(_SERVER_DIR / "student_2024" / "student_db_2024")
_STUDENT_2024_UPLOADS = str(_SERVER_DIR / "student_2024" / "uploads")
_STUDENT_2024_METADATA = str(_SERVER_DIR / "student_2024" / "ingestion_metadata.db")

# ---------------------------------------------------------------------------
# INSTANCE_MODE controls which sub-apps are mounted.
# When run_all_ingestions.py launches separate processes for student_2024 and
# faculty, those processes set CHROMA_DATA_DIR to their own store.  They
# should NOT also mount sub-apps for every other store (wastes memory and
# opens the same SQLite files from multiple processes → corruption risk).
#
#   INSTANCE_MODE=main   → mount all sub-apps + default ingestion  (port 9000)
#   INSTANCE_MODE=standalone → only mount default ingestion using env paths
#
# If INSTANCE_MODE is unset we auto-detect: if CHROMA_DATA_DIR points
# somewhere other than the default storage/chroma path, assume standalone.
# ---------------------------------------------------------------------------
_INSTANCE_MODE = os.getenv("INSTANCE_MODE", "").strip().lower()
if not _INSTANCE_MODE:
    _env_chroma = os.getenv("CHROMA_DATA_DIR", "")
    _default_chroma = str(_SERVER_DIR / "storage" / "chroma")
    # If CHROMA_DATA_DIR is set and differs from the default, treat as standalone
    if _env_chroma and str(Path(_env_chroma).resolve() if Path(_env_chroma).is_absolute() else (_SERVER_DIR / _env_chroma).resolve()) != str(Path(_default_chroma).resolve()):
        _INSTANCE_MODE = "standalone"
    else:
        _INSTANCE_MODE = "main"


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

if _INSTANCE_MODE == "main":
    # ---------------------------------------------------------------------------
    # Mount sub-apps for faculty & student_2024 ChromaDB stores
    # NOTE: Sub-apps must be mounted BEFORE register_ingestion so that
    #       /ingestion/faculty and /ingestion/student_2024 are matched first.
    # ---------------------------------------------------------------------------
    faculty_app = create_ingestion_app(
        chroma_data_dir=_FACULTY_CHROMA,
        uploads_dir=_FACULTY_UPLOADS,
        metadata_db_path=_FACULTY_METADATA,
    )
    app.mount("/ingestion/faculty", faculty_app)

    student_2024_app = create_ingestion_app(
        chroma_data_dir=_STUDENT_2024_CHROMA,
        uploads_dir=_STUDENT_2024_UPLOADS,
        metadata_db_path=_STUDENT_2024_METADATA,
    )
    app.mount("/ingestion/student_2024", student_2024_app)

    logger.info("Main mode: mounted faculty + student_2024 sub-apps")
else:
    logger.info("Standalone mode: skipping sub-app mounts (CHROMA_DATA_DIR=%s)", os.getenv("CHROMA_DATA_DIR", "<default>"))

# ---------------------------------------------------------------------------
# Mount the default ingestion API (uses CHROMA_DATA_DIR or ./storage/chroma)
# ---------------------------------------------------------------------------
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
            logger.debug("Chroma health check failed")
            chroma_ok = False
    return {"status": "ok" if chroma_ok else "degraded", "ingestion": True, "chroma": chroma_ok}


@app.get("/health")
def health():
    return {"status": "ok", "ingestion": True}
