"""
osint.py — Descubrimiento OSINT de dominios objetivo (v0.4.0).

Permite encontrar dominios públicos que usan un patrón de URL similar
al de un cliente conocido, sin necesidad de tener acceso a su API.

Estrategias implementadas:
- urlscan.io: indexa peticiones XHR/fetch interceptadas en navegaciones
  públicas. Útil para descubrir dominios que llaman a un endpoint
  específico (ej: "/v1/onboarding/resolvecustomers*").
- GitHub Search: indexa repositorios públicos. Útil para encontrar
  SDKs, controladores Postman/Swagger, o archivos de config con
  referencias hardcodeadas a un endpoint.

Nota ética: solo se consulta data pública indexada. No se accede a
ningún sistema privado. No se hace scraping detrás de login.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from .fetcher import FetcherConfig, FetcherError, fetch


# ─────────────────────── Estructuras de salida ───────────────────────


@dataclass
class OsintHit:
    """Un dominio o repo que matcheó la búsqueda."""
    fuente: str                       # "urlscan" | "github"
    titulo: str
    url: str                          # URL del recurso encontrado
    dominio: str = ""                 # dominio base extraído
    extra: Dict[str, Any] = field(default_factory=dict)


# ─────────────────────── urlscan.io ───────────────────────
# API pública: https://urlscan.io/docs/api/
# Endpoint: GET https://urlscan.io/api/v1/search/?q=<query>&size=<n>
# No requiere auth para queries básicas (rate-limit ~100/h).
# Guard: urlscan NO almacena bodies de POST por privacidad → solo
# descubrimos dominios base, no los payloads.


def urlscan_search(
    query: str,
    size: int = 100,
    cfg: Optional[FetcherConfig] = None,
) -> List[OsintHit]:
    """
    Busca en urlscan.io resultados para ``query``.

    Args:
        query: ej ``page.url:"/v1/onboarding/resolvecustomers*"`` o
               un término libre como ``"resolvecustomers"``.
        size: máximo de resultados (cap 10000 según docs).

    Returns:
        Lista de OsintHit con fuente="urlscan".
    """
    cfg = cfg or FetcherConfig()
    url = (
        f"https://urlscan.io/api/v1/search/?q={quote_plus(query)}&size={min(size, 1000)}"
    )
    try:
        r = fetch(url, method="GET", cfg=cfg)
    except FetcherError as e:
        return [OsintHit(
            fuente="urlscan",
            titulo="ERROR",
            url=url,
            extra={"error": str(e)},
        )]
    if not r.status == 200:
        return [OsintHit(
            fuente="urlscan",
            titulo=f"HTTP {r.status}",
            url=url,
            extra={"status": r.status, "body": r.body if isinstance(r.body, (str, bytes, dict)) else None},
        )]
    # r.body debería ser un dict (JSON parseado por el fetcher)
    if not isinstance(r.body, dict):
        return [OsintHit(
            fuente="urlscan",
            titulo="Respuesta no es JSON",
            url=url,
            extra={"body_type": type(r.body).__name__},
        )]
    hits: List[OsintHit] = []
    for item in r.body.get("results", []):
        page = item.get("page", {})
        task = item.get("task", {})
        dominio = page.get("domain", "")
        titulo = page.get("title", "")
        url_encontrada = page.get("url", "")
        hits.append(OsintHit(
            fuente="urlscan",
            titulo=titulo or url_encontrada,
            url=url_encontrada,
            dominio=dominio,
            extra={
                "task_uuid": task.get("uuid"),
                "time": item.get("time"),
                "country": page.get("country"),
                "asn": page.get("asn"),
            },
        ))
    return hits


# ─────────────────────── GitHub Search ───────────────────────
# API pública: https://docs.github.com/en/rest/search
# Endpoint: GET https://api.github.com/search/code?q=<query>
# No requiere auth para queries limitadas (rate-limit 10/min sin token,
# 30/min con token). Si hay GITHUB_TOKEN en env, lo usa.
# Guard: solo busca en código público. No se accede a repos privados.


def _github_headers() -> Dict[str, str]:
    import os
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "api-explorer/0.4 (osint)",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_search(
    query: str,
    size: int = 30,
    cfg: Optional[FetcherConfig] = None,
    languages: Optional[List[str]] = None,
) -> List[OsintHit]:
    """
    Busca en GitHub Code Search resultados para ``query``.

    Args:
        query: ej ``"/v1/onboarding/resolvecustomers"``.
        size: máximo de resultados (cap 100 según API).
        languages: filtro de lenguajes, ej ``["javascript", "typescript"]``.

    Returns:
        Lista de OsintHit con fuente="github".
    """
    cfg = cfg or FetcherConfig()
    q = query
    if languages:
        lang_filter = " OR ".join(f"language:{l}" for l in languages)
        q = f"{query} {lang_filter}"
    url = f"https://api.github.com/search/code?q={quote_plus(q)}&per_page={min(size, 100)}"
    try:
        r = fetch(url, method="GET", cfg=cfg, custom_headers=_github_headers())
    except FetcherError as e:
        return [OsintHit(
            fuente="github",
            titulo="ERROR",
            url=url,
            extra={"error": str(e)},
        )]
    if r.status == 403:
        # Rate-limited
        return [OsintHit(
            fuente="github",
            titulo="Rate limit alcanzado",
            url=url,
            extra={"status": 403, "sugerencia": "Esperá 1 min o configurá GITHUB_TOKEN"},
        )]
    if r.status != 200:
        return [OsintHit(
            fuente="github",
            titulo=f"HTTP {r.status}",
            url=url,
            extra={"status": r.status},
        )]
    if not isinstance(r.body, dict):
        return [OsintHit(
            fuente="github",
            titulo="Respuesta no es JSON",
            url=url,
        )]
    hits: List[OsintHit] = []
    for item in r.body.get("items", []):
        repo = item.get("repository", {})
        hits.append(OsintHit(
            fuente="github",
            titulo=item.get("name", ""),
            url=item.get("html_url", ""),
            dominio=repo.get("html_url", ""),
            extra={
                "repo": repo.get("full_name"),
                "path": item.get("path"),
                "lenguaje": repo.get("language"),
                "stars": repo.get("stargazers_count"),
            },
        ))
    return hits


# ─────────────────────── Orquestador ───────────────────────


def osint_search(
    query: str,
    fuentes: Optional[List[str]] = None,
    size: int = 50,
    languages: Optional[List[str]] = None,
    delay_between: float = 1.0,
    cfg: Optional[FetcherConfig] = None,
    progress: bool = False,
) -> Dict[str, Any]:
    """
    Ejecuta búsqueda OSINT en múltiples fuentes y consolida los resultados.

    Args:
        query: la query en crudo (sin sintaxis específica de cada fuente).
               Se pasa igual a urlscan y a GitHub.
        fuentes: lista de fuentes a usar. Default: ["urlscan", "github"].
        size: tope por fuente.
        languages: filtro de lenguajes para GitHub.
        delay_between: pausa entre fuentes (respetar rate-limits).
        progress: imprimir progreso.

    Returns:
        Dict con:
          - query
          - hits: lista consolidada de OsintHit
          - por_fuente: {"urlscan": [...], "github": [...]}
          - dominios_unicos: lista de dominios únicos
          - errores: lista de fuentes que fallaron
    """
    cfg = cfg or FetcherConfig()
    fuentes = fuentes or ["urlscan", "github"]
    hits_total: List[OsintHit] = []
    por_fuente: Dict[str, List[OsintHit]] = {}
    errores: List[Dict[str, str]] = []

    for fuente in fuentes:
        if progress:
            print(f"  [osint] Buscando en {fuente}...", flush=True)
        try:
            if fuente == "urlscan":
                hits = urlscan_search(query, size=size, cfg=cfg)
            elif fuente == "github":
                hits = github_search(query, size=size, cfg=cfg, languages=languages)
            else:
                continue
        except Exception as e:
            errores.append({"fuente": fuente, "error": str(e)})
            continue
        por_fuente[fuente] = hits
        hits_total.extend(hits)
        if progress:
            print(f"  [osint] {fuente}: {len(hits)} resultados", flush=True)
        if delay_between > 0 and fuente != fuentes[-1]:
            time.sleep(delay_between)

    dominios = sorted({h.dominio for h in hits_total if h.dominio})
    return {
        "query": query,
        "hits": [h.__dict__ for h in hits_total],
        "por_fuente": {k: [h.__dict__ for h in v] for k, v in por_fuente.items()},
        "dominios_unicos": dominios,
        "errores": errores,
        "total_hits": len(hits_total),
        "total_dominios_unicos": len(dominios),
    }


def format_osint_report(result: Dict[str, Any]) -> str:
    """Informe legible del resultado de osint_search()."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"  OSINT: {result.get('query', '?')}")
    lines.append("=" * 70)
    lines.append(f"Total hits:        {result.get('total_hits', 0)}")
    lines.append(f"Dominios únicos:   {result.get('total_dominios_unicos', 0)}")
    if result.get("errores"):
        lines.append(f"Errores:           {len(result['errores'])}")
    lines.append("")
    por_fuente = result.get("por_fuente", {})
    for fuente, hits in por_fuente.items():
        lines.append(f"── {fuente} ({len(hits)} hits) ──")
        for h in hits[:10]:
            extra_str = ""
            if h.get("extra", {}).get("status"):
                extra_str = f"  [status={h['extra']['status']}]"
            if h.get("extra", {}).get("error"):
                extra_str = f"  [error: {h['extra']['error'][:60]}]"
            lines.append(f"  {h['dominio'] or h['url']:<50}{extra_str}")
        if len(hits) > 10:
            lines.append(f"  ... y {len(hits) - 10} más")
        lines.append("")
    return "\n".join(lines)
