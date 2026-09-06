"""Escritura del render bundle en disco: `<out>/<dominio__slug>/render.json`
(+ `rendered.html` opcional) y un `MANIFEST.json` por corrida.

Solo el `MANIFEST.json` se versiona (ver .gitignore). El nombre de carpeta
`<dominio>__<slug>` evita que dos páginas del mismo host se pisen (hará falta para
D4).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from maria_common.render_contract import (
    RENDER_SCHEMA_VERSION,
    RenderBundleEntry,
    RenderManifest,
    RenderManifestAccount,
)

from .capture import UA_STRING


def dir_name(url: str) -> str:
    u = urlparse(url)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (u.path or "/").strip("/")) or "home"
    dom = u.netloc.replace(":", "_")
    return f"{dom}__{slug}"


def write_entry(out_dir: Path, entry: RenderBundleEntry, rendered_html: str | None) -> str:
    folder = out_dir / dir_name(entry.url)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "render.json").write_text(entry.model_dump_json(indent=2), "utf-8")
    if rendered_html is not None and entry.rendered_html_file:
        (folder / entry.rendered_html_file).write_text(rendered_html, "utf-8")
    return folder.name


def write_manifest(out_dir: Path, accounts: list[RenderManifestAccount],
                   playwright_chromium: str | None) -> Path:
    manifest = RenderManifest(
        render_schema_version=RENDER_SCHEMA_VERSION,
        captured_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        user_agent=UA_STRING,
        capture_dom="networkidle",
        playwright_chromium=playwright_chromium,
        cuentas=accounts,
    )
    path = out_dir / "MANIFEST.json"
    path.write_text(manifest.model_dump_json(indent=2), "utf-8")
    return path
