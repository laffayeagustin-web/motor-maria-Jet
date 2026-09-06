"""Contrato del *render bundle* — la frontera entre las dos herramientas.

`maria_render` (notebook) produce un `render.json` por URL siguiendo este esquema.
`maria` (servidor) lo consume vía `maria.render_bundle`. El campo
`render_schema_version` es el contrato: si el *major* no coincide con
`RENDER_SCHEMA_VERSION`, el servidor ignora el bundle entero y degrada a
`unverified` (RF-02).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RENDER_SCHEMA_VERSION = "1.0"

RenderStatus = Literal["ok", "timeout", "error"]


def schema_major(version: str) -> int:
    try:
        return int(str(version).split(".", 1)[0])
    except (ValueError, AttributeError):
        return -1


class FormInfo(BaseModel):
    fields: int = 0
    required: int = 0


class ModelContextInfo(BaseModel):
    present: bool = False
    tools: int = 0


class FooterLink(BaseModel):
    text: str = ""
    href: str = ""


class RenderBundleEntry(BaseModel):
    """Un `render.json`: el resultado de renderizar una URL en la notebook."""

    render_schema_version: str = RENDER_SCHEMA_VERSION
    url: str
    final_url: Optional[str] = None
    captured_utc: str
    capture_dom: str = "networkidle"
    capture_timeout_ms: int = 45000
    playwright_chromium: Optional[str] = None

    status: RenderStatus = "ok"
    error: Optional[str] = None

    rendered_html_file: Optional[str] = None
    rendered_words: Optional[int] = None
    rendered_text_sha256: Optional[str] = None

    ld_blocks: list[str] = Field(default_factory=list)
    forms: list[FormInfo] = Field(default_factory=list)
    nav_links_internal: Optional[int] = None
    quote_link: bool = False
    price_on_screen: bool = False
    model_context: ModelContextInfo = Field(default_factory=ModelContextInfo)
    footer_links: list[FooterLink] = Field(default_factory=list)

    @property
    def usable(self) -> bool:
        """El servidor puede leer las señales de DOM de este entry."""
        return self.status == "ok" and schema_major(
            self.render_schema_version
        ) == schema_major(RENDER_SCHEMA_VERSION)


class RenderManifestAccount(BaseModel):
    url: str
    status: RenderStatus | Literal["skipped"] = "ok"
    dir: Optional[str] = None
    error: Optional[str] = None


class RenderManifest(BaseModel):
    """`MANIFEST.json` de una corrida de `maria-render`. Es lo único que se versiona."""

    render_schema_version: str = RENDER_SCHEMA_VERSION
    captured_utc: str
    user_agent: str
    capture_dom: str = "networkidle"
    playwright_chromium: Optional[str] = None
    cuentas: list[RenderManifestAccount] = Field(default_factory=list)
