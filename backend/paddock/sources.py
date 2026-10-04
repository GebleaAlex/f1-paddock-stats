"""Downloads the source datasets into data/raw and records which versions were used.

- f1db: the SQLite release asset (CC BY 4.0), checked against the release's SHA-256 list, plus the circuit layout
  SVGs from the same tag.
- Jolpica: the delayed CSV database dump (CC BY-NC-SA 4.0), checked against the hash the API publishes.

Every download is skipped when the file on disk already has the expected hash, so running fetch twice is cheap.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

from . import config

MANIFEST = "sources.json"


def _client() -> httpx.Client:
    headers = {"User-Agent": "paddock-stats (https://github.com/GebleaAlex/Formula-1-F1-Paddock-Stats)"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(headers=headers, follow_redirects=True, timeout=120)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(client: httpx.Client, url: str, dest: Path, sha256: str | None = None) -> bool:
    """Download url to dest unless dest already matches sha256. Returns True when something was downloaded."""
    if sha256 and dest.exists() and _sha256(dest) == sha256:
        return False
    tmp = dest.with_suffix(dest.suffix + ".part")
    with client.stream("GET", url) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    if sha256 and (actual := _sha256(tmp)) != sha256:
        tmp.unlink()
        raise RuntimeError(f"Checksum mismatch for {url}: expected {sha256}, got {actual}")
    tmp.replace(dest)
    return True


def fetch_f1db(client: httpx.Client, raw: Path, tag: str | None = None) -> dict:
    api = f"https://api.github.com/repos/{config.F1DB_REPO}/releases/" + (f"tags/{tag}" if tag else "latest")
    release = client.get(api).raise_for_status().json()
    tag = release["tag_name"]
    assets = {a["name"]: a["browser_download_url"] for a in release["assets"]}

    checksums = client.get(assets["checksums_sha256.txt"]).raise_for_status().text
    expected = dict(reversed(line.split()) for line in checksums.splitlines() if line.strip())
    zip_path = raw / "f1db-sqlite.zip"
    if (
        _download(client, assets["f1db-sqlite.zip"], zip_path, expected["f1db-sqlite.zip"])
        or not (raw / "f1db.db").exists()
    ):
        with zipfile.ZipFile(zip_path) as z:
            z.extract("f1db.db", raw)

    # Circuit layouts: one SVG per layout id, white stroke on transparent. We only keep the path data.
    svg_dir = raw / "circuits"
    svg_dir.mkdir(exist_ok=True)
    tree = client.get(f"https://api.github.com/repos/{config.F1DB_REPO}/git/trees/{tag}?recursive=1").json()
    names = [
        p["path"].rsplit("/", 1)[1]
        for p in tree["tree"]
        if p["path"].startswith("src/assets/circuits/white/") and p["path"].endswith(".svg")
    ]
    for name in names:
        dest = svg_dir / name
        if not dest.exists():
            url = f"https://raw.githubusercontent.com/{config.F1DB_REPO}/{tag}/src/assets/circuits/white/{name}"
            _download(client, url, dest)
    return {"name": "f1db", "version": tag, "licence": "CC BY 4.0", "url": f"https://github.com/{config.F1DB_REPO}"}


def fetch_jolpica(client: httpx.Client, raw: Path) -> dict:
    info = client.get(config.JOLPICA_DUMPS_URL).raise_for_status().json()
    dump = info["delayed_dumps"]["csv"]
    zip_path = raw / "jolpica-csv.zip"
    target = raw / "jolpica"
    if _download(client, dump["download_url"], zip_path, dump["file_hash"]) or not target.exists():
        shutil.rmtree(target, ignore_errors=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(target)
    return {
        "name": "Jolpica-F1",
        "version": dump["uploaded_at"][:10],
        "licence": "CC BY-NC-SA 4.0",
        "url": "https://github.com/jolpica/jolpica-f1",
    }


def fetch_all(raw: Path | None = None, f1db_tag: str | None = None) -> list[dict]:
    raw = raw or config.RAW_DIR
    raw.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        sources = [fetch_f1db(client, raw, f1db_tag), fetch_jolpica(client, raw)]
    manifest = {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), "sources": sources}
    (raw / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return sources


def read_manifest(raw: Path | None = None) -> dict:
    path = (raw or config.RAW_DIR) / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"sources": []}


def svg_path_data(svg: str) -> str | None:
    """The `d` attribute of the first path in an f1db layout SVG."""
    m = re.search(r'\sd="([^"]+)"', svg)
    return m.group(1) if m else None
