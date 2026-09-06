"""Parsing y recorrido de bloques JSON-LD.

Portado de `docs/prototipo/prueba_indice.py` y `geo_probe.py`. Entrada: lista de
strings (el `textContent` de cada `<script type="application/ld+json">`), tal como
vienen en `render.json` (`ld_blocks`) o como los extrae el servidor del HTML
crudo. Recorre `@graph` y listas anidadas.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

ORG_TYPES = {"Organization", "LocalBusiness"}
CHARTER_TYPES = {"Service", "Offer", "Product"}
BOILERPLATE_TYPES = {
    "WebPage", "WebSite", "BreadcrumbList", "SearchAction",
    "ListItem", "ImageObject", "SiteNavigationElement", "CollectionPage",
}


def iter_ld_nodes(obj: Any) -> Iterator[dict]:
    """Todos los nodos dict de un árbol JSON-LD, entrando en `@graph` y listas."""
    if isinstance(obj, dict):
        graph = obj.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                yield from iter_ld_nodes(node)
            return
        yield obj
        for value in obj.values():
            if isinstance(value, (dict, list)):
                yield from iter_ld_nodes(value)
    elif isinstance(obj, list):
        for node in obj:
            yield from iter_ld_nodes(node)


def node_types(node: Any) -> set[str]:
    if not isinstance(node, dict):
        return set()
    t = node.get("@type")
    if isinstance(t, list):
        return {str(x) for x in t}
    if isinstance(t, str):
        return {t}
    return set()


def parse_blocks(blocks: list[str]) -> tuple[list[dict], int, int]:
    """Devuelve (nodos, bloques_parseables, bloques_totales)."""
    nodes: list[dict] = []
    ok = 0
    total = 0
    for blob in blocks or []:
        if not blob or not blob.strip():
            continue
        total += 1
        try:
            data = json.loads(blob)
        except Exception:
            continue
        ok += 1
        nodes.extend(iter_ld_nodes(data))
    return nodes, ok, total


def all_types(nodes: list[dict]) -> set[str]:
    return {t for n in nodes for t in node_types(n)}


def has_org_con_datos(nodes: list[dict]) -> bool:
    """Hay un Organization/LocalBusiness con al menos name, address o telephone.

    Es la condición que evita el tope por boilerplate de RF-13.
    """
    for node in nodes:
        if node_types(node) & ORG_TYPES and (
            node.get("name") or node.get("address") or node.get("telephone")
        ):
            return True
    return False
