"""Parsing de `robots.txt` y de Content Signals (Cloudflare).

Portado de `docs/prototipo/geo_probe.py`. Todo puro: la obtención por red la hace
`maria.fetch.static`; acá solo se parsea texto.

Decisión de rúbrica (enmienda §5): una Content Signal EXPLÍCITA en `no` para
`ai-train` o `ai-input` cuenta como bloqueo. La AUSENCIA de señal es neutra. Un
`robots.txt` con solo el preámbulo de Cloudflare y ninguna directiva no declara
política (caso Modena, verificado 01-09-2026) y no se penaliza.
"""
from __future__ import annotations

import re

# Crawlers de motores generativos. Ninguno ejecuta JS (a 2026).
AI_CRAWLERS = {
    "GPTBot": "OpenAI - entrenamiento",
    "OAI-SearchBot": "OpenAI - índice de ChatGPT Search",
    "ChatGPT-User": "OpenAI - fetch en vivo por pedido del usuario",
    "ClaudeBot": "Anthropic - entrenamiento",
    "Claude-User": "Anthropic - fetch en vivo",
    "PerplexityBot": "Perplexity - índice",
    "Perplexity-User": "Perplexity - fetch en vivo",
    "Google-Extended": "Google - permiso de Gemini/AI Overviews",
    "CCBot": "Common Crawl - alimenta a casi todos",
    "Bytespider": "ByteDance/Doubao",
    "Applebot-Extended": "Apple Intelligence",
}

# Los cinco que la rúbrica D2.1 exige que no estén bloqueados.
D2_CORE_CRAWLERS = ["GPTBot", "ClaudeBot", "CCBot", "PerplexityBot", "Google-Extended"]

CONTENT_SIGNAL_RE = re.compile(r"content-signal\s*:\s*(.+)", re.I)
SIGNAL_PAIR_RE = re.compile(r"([a-z-]+)\s*=\s*(yes|no)", re.I)
SENALES_QUE_BLOQUEAN = ("ai-train", "ai-input")


def parse_robots(txt: str) -> dict[str, dict[str, list[str]]]:
    """`{user_agent_lower: {"allow": [...], "disallow": [...]}}`."""
    groups: dict[str, dict[str, list[str]]] = {}
    current: list[str] = []
    for raw in (txt or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            ua = value.lower()
            groups.setdefault(ua, {"allow": [], "disallow": []})
            current = [ua]
        elif field in ("allow", "disallow") and current:
            for ua in current:
                groups.setdefault(ua, {"allow": [], "disallow": []})[field].append(value)
    return groups


def parse_content_signals(txt: str) -> tuple[dict[str, str], bool]:
    """`({uso: 'yes'|'no'}, bloquea)`.

    `bloquea` es True solo con una señal EXPLÍCITA en `no` para ai-train/ai-input.
    """
    senales: dict[str, str] = {}
    for raw in (txt or "").splitlines():
        line = raw.lstrip("# \t")
        m = CONTENT_SIGNAL_RE.search(line)
        if not m:
            continue
        for uso, val in SIGNAL_PAIR_RE.findall(m.group(1)):
            senales[uso.lower()] = val.lower()
    bloquea = any(senales.get(u) == "no" for u in SENALES_QUE_BLOQUEAN)
    return senales, bloquea


def crawler_verdict(groups: dict, ua: str, path: str = "/") -> dict:
    """¿El grupo de `robots.txt` para `ua` (o `*`) permite `path`?"""
    g = groups.get(ua.lower()) or groups.get("*")
    source = ua if ua.lower() in groups else ("*" if "*" in groups else None)
    if not g:
        return {"allowed": True, "rule": None, "group": None}
    best = {"allowed": True, "rule": None}
    for kind in ("disallow", "allow"):
        for rule in g[kind]:
            if kind == "disallow" and rule == "":
                continue  # 'Disallow:' vacío = permitir todo
            if path.startswith(rule.rstrip("*")) and (
                best["rule"] is None or len(rule) > len(best["rule"])
            ):
                best = {"allowed": kind == "allow", "rule": rule}
    return {**best, "group": source}


def blocked_ai_crawlers(groups: dict, path: str = "/") -> list[str]:
    """De los cinco crawlers núcleo de D2.1, cuáles quedan con Disallow."""
    return sorted(
        c for c in D2_CORE_CRAWLERS if not crawler_verdict(groups, c, path)["allowed"]
    )


def sitemap_referenciado(txt: str) -> bool:
    return bool(re.search(r"^\s*sitemap\s*:", txt or "", re.I | re.M))


def declara_politica(txt: str) -> bool:
    """Hay al menos una directiva real o una Content Signal — no solo el preámbulo."""
    groups = parse_robots(txt)
    senales, _ = parse_content_signals(txt)
    return bool(groups) or bool(senales)
