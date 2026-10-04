"""Paths and settings, overridable through environment variables."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("PADDOCK_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("PADDOCK_DB", DATA_DIR / "paddock.duckdb"))
# `paddock build` writes a new versioned file each time and points to it from this file, so a running API (which
# keeps the old file open; Windows cannot replace an open file) switches over on its next query.
DB_POINTER = DATA_DIR / "paddock.current"


def current_db_path() -> Path:
    """The database to read: PADDOCK_DB if set, else the build named in data/paddock.current, else the default."""
    if "PADDOCK_DB" in os.environ:
        return DB_PATH
    try:
        name = DB_POINTER.read_text(encoding="utf-8").strip()
        if name and (DATA_DIR / name).exists():
            return DATA_DIR / name
    except FileNotFoundError:
        pass
    return DB_PATH


F1DB_REPO = "f1db/f1db"
JOLPICA_DUMPS_URL = "https://api.jolpi.ca/data/dumps/download/"

# Allowed browser origins for the API (comma separated). The Nuxt server calls the API directly, so this only
# matters when the API is called from a browser on another origin.
CORS_ORIGINS = [o for o in os.environ.get("PADDOCK_CORS_ORIGINS", "http://localhost:3000").split(",") if o]
