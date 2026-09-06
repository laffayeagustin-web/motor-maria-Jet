"""Fetch estático del HTML servido, con caché de 24 h y UA propio.

RF-01 (obtiene el HTML crudo), RF-04 (UA identificable, 1 request concurrente por
dominio — el semáforo lo pone el batch, ver `maria.cli`), RF-05 (reutiliza caché
< 24 h salvo `--no-cache`).

El estado (`bloqueado` / `inaccesible`) lo decide `classify_response()` a partir
de lo que devuelve la red; el probe D2 y el orquestador lo consumen.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

UA_STRING = "MarIA-GEO-Audit/0.1 (+https://maria.ar/bot)"
CACHE_TTL_S = 24 * 3600
DEFAULT_CACHE_DIR = Path("out/cache")


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: Optional[int] = None
    final_url: Optional[str] = None
    body: str = ""
    headers: dict = field(default_factory=dict)
    ttfb_ms: Optional[int] = None
    from_cache: bool = False
    # clasificación (RF-03)
    estado: Optional[str] = None          # None | "bloqueado" | "inaccesible"
    motivo: Optional[str] = None
    error: Optional[str] = None
    redirect_chain: list[str] = field(default_factory=list)

    @property
    def https_sin_degradacion(self) -> bool:
        if not self.final_url:
            return False
        chain = self.redirect_chain + [self.final_url]
        return all(u.startswith("https://") for u in chain if u)


def _cache_path(cache_dir: Path, url: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    host = urlparse(url).netloc.replace(":", "_") or "nohost"
    return cache_dir / host / f"{key}.json"


def _load_cache(path: Path) -> Optional[FetchResult]:
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL_S:
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
    except Exception:
        return None
    data["from_cache"] = True
    return FetchResult(**data)


def _save_cache(path: Path, result: FetchResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in result.__dict__.items()}
    payload["from_cache"] = False
    path.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")


def classify_error(msg: str) -> tuple[str, str]:
    """(estado, motivo) a partir del texto de una excepción de httpx."""
    low = msg.lower()
    if "certificate_verify_failed" in low or "ssl" in low or "hostname mismatch" in low:
        return "inaccesible", "certificado TLS inválido para este dominio"
    if "redirect" in low:
        return "inaccesible", "bucle de redirecciones para un cliente que no es navegador"
    if "name or service not known" in low or "getaddrinfo" in low or "nodename" in low:
        return "inaccesible", "el DNS no resuelve"
    return "inaccesible", "no se pudo obtener el recurso"


def fetch(
    url: str,
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    no_cache: bool = False,
    timeout: float = 30.0,
    ua: str = UA_STRING,
) -> FetchResult:
    cache_dir = Path(cache_dir)
    cpath = _cache_path(cache_dir, url)
    if not no_cache:
        cached = _load_cache(cpath)
        if cached is not None:
            return cached

    t0 = time.perf_counter()
    try:
        with httpx.Client(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": ua}
        ) as client:
            resp = client.get(url)
        result = FetchResult(
            url=url,
            ok=True,
            status=resp.status_code,
            final_url=str(resp.url),
            body=resp.text,
            headers={k.lower(): v for k, v in resp.headers.items()},
            ttfb_ms=round((time.perf_counter() - t0) * 1000),
            redirect_chain=[str(h.url) for h in resp.history],
        )
        if resp.status_code in (403, 503):
            result.estado = "bloqueado"
            result.motivo = (
                f"el servidor respondió {resp.status_code} a un cliente "
                "identificado y no-navegador"
            )
    except Exception as exc:  # noqa: BLE001 — todo fallo de red es un dato a reportar
        msg = str(exc)
        estado, motivo = classify_error(msg)
        result = FetchResult(
            url=url, ok=False, estado=estado, motivo=motivo, error=f"fetch crudo: {msg}"
        )

    if not no_cache:
        _save_cache(cpath, result)
    return result


def fetch_text(url: str, **kw) -> Optional[str]:
    """Para `robots.txt`, `sitemap.xml`, `llms.txt`: 200 y content-type no-HTML."""
    r = fetch(url, **kw)
    if not r.ok or r.status != 200:
        return None
    if "html" in r.headers.get("content-type", "").lower():
        return None
    return r.body


def robots_url(page_url: str) -> str:
    p = urlparse(page_url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def same_origin_join(base: str, path: str) -> str:
    return urljoin(origin_of(base) + "/", path)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
