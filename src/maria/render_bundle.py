"""Carga y validación de un *render bundle* producido por `maria-render`.

RF-02 / RF-12: si no hay entry para una URL, o el `render_schema_version` es
incompatible, o el `status` no es `ok`, el servidor devuelve `None` para esa URL
y los probes degradan los sub-criterios dependientes del DOM a `unverified`. La
corrida nunca rompe por un bundle ausente o parcial.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from maria_common.render_contract import (
    RENDER_SCHEMA_VERSION,
    RenderBundleEntry,
    RenderManifest,
    schema_major,
)

log = logging.getLogger("maria.render_bundle")


def _norm_key(url: str) -> str:
    """Clave de match: host sin `www.` + path sin barra final."""
    p = urlparse(url.strip())
    host = (p.netloc or "").lower().removeprefix("www.")
    path = (p.path or "/").rstrip("/") or "/"
    return f"{host}{path}"


class RenderBundle:
    def __init__(self, directory: Optional[Path], entries: dict[str, RenderBundleEntry]):
        self.directory = directory
        self._entries = entries

    @property
    def loaded(self) -> bool:
        return self.directory is not None

    def entry_for(self, url: str) -> Optional[RenderBundleEntry]:
        entry = self._entries.get(_norm_key(url))
        if entry is None:
            return None
        if not entry.usable:
            log.warning("bundle entry para %s no usable (status=%s, version=%s)",
                        url, entry.status, entry.render_schema_version)
            return None
        return entry

    def rendered_html(self, url: str) -> Optional[str]:
        entry = self.entry_for(url)
        if not entry or not entry.rendered_html_file or not self.directory:
            return None
        for sub in self.directory.iterdir():
            if not sub.is_dir():
                continue
            cand = sub / entry.rendered_html_file
            if cand.exists() and _matches_dir(sub.name, url):
                return cand.read_text("utf-8", errors="replace")
        return None


def _matches_dir(dirname: str, url: str) -> bool:
    host = urlparse(url).netloc.replace(":", "_")
    return dirname.startswith(host)


EMPTY = RenderBundle(None, {})


def load_bundle(directory: Optional[Path | str]) -> RenderBundle:
    if directory is None:
        return EMPTY
    directory = Path(directory)
    if not directory.is_dir():
        log.warning("render bundle %s no existe; se corre sin render (RF-02)", directory)
        return EMPTY

    manifest_path = directory / "MANIFEST.json"
    if manifest_path.exists():
        try:
            manifest = RenderManifest.model_validate_json(manifest_path.read_text("utf-8"))
            if schema_major(manifest.render_schema_version) != schema_major(RENDER_SCHEMA_VERSION):
                log.warning(
                    "bundle %s: render_schema_version %s incompatible con %s — se ignora entero",
                    directory, manifest.render_schema_version, RENDER_SCHEMA_VERSION,
                )
                return RenderBundle(directory, {})
        except Exception as exc:  # noqa: BLE001
            log.warning("bundle %s: MANIFEST.json ilegible (%s)", directory, exc)

    entries: dict[str, RenderBundleEntry] = {}
    for render_json in directory.glob("*/render.json"):
        try:
            entry = RenderBundleEntry.model_validate_json(render_json.read_text("utf-8"))
        except Exception as exc:  # noqa: BLE001
            log.warning("bundle: %s ilegible (%s)", render_json, exc)
            continue
        entries[_norm_key(entry.url)] = entry
        if entry.final_url:
            entries.setdefault(_norm_key(entry.final_url), entry)

    log.info("render bundle %s: %d entradas", directory, len(entries))
    return RenderBundle(directory, entries)
