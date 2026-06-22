"""
discovery.py — Recon de superficie de una API.

Prueba paths comunes, detecta métodos permitidos, captura CORS, fingerprint.
Inspirado en @scraper (Katana + flowsint) pero integrable directo en api-explorer.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from .fetcher import (
    FetchResult,
    FetcherConfig,
    FetcherError,
    fetch,
    fetch_options,
    fingerprint_api,
)


# Paths comunes que vale la pena probar en una API
# (ordenados por probabilidad, corto a largo)
DEFAULT_RECON_PATHS: List[str] = [
    # Root
    "/",
    # Health
    "/health", "/health/", "/healthz", "/ping", "/ready", "/readyz", "/live", "/livez",
    # Versioning
    "/version", "/v", "/api", "/api/v1", "/v1", "/v2", "/v3",
    # OpenAPI / Swagger
    "/swagger", "/swagger/", "/swagger.json", "/swagger.yaml", "/swagger/index.html",
    "/openapi", "/openapi.json", "/openapi.yaml", "/openapi/v1", "/openapi/v2",
    "/api-docs", "/api-docs/", "/docs", "/docs/", "/redoc", "/swagger-ui",
    "/spec", "/spec.json", "/spec.yaml",
    # Auth
    "/auth", "/login", "/oauth", "/oauth2", "/token", "/auth/token",
    "/api/auth", "/api/login", "/api/token",
    # Customer / User endpoints (común en APIs modernas)
    "/me", "/user", "/users", "/user/", "/users/", "/api/users", "/api/user",
    "/profile", "/account", "/accounts", "/customer", "/customers",
    # Onboarding / Resolve (que estabas buscando)
    "/onboarding", "/onboarding/", "/resolve", "/resolve/",
    "/api/onboarding", "/api/resolve", "/api/onboarding/resolve",
    "/onboarding/resolve", "/onboarding/customers", "/customers/resolve",
    # Resources comunes
    "/products", "/items", "/orders", "/invoices", "/payments",
    # Legacy / Health de Spring Boot
    "/actuator", "/actuator/health", "/actuator/info", "/actuator/env",
    "/management", "/management/health",
    # GraphQL
    "/graphql", "/graphiql", "/playground",
    # Common files
    "/robots.txt", "/sitemap.xml", "/.well-known/openid-configuration",
    "/favicon.ico", "/.env", "/config.json", "/config.yaml",
]


@dataclass
class EndpointHit:
    """Resultado de probar un path."""
    path: str
    full_url: str
    status: int
    method: str = "GET"
    exists: bool = False           # True si el path responde (no 404)
    auth_required: bool = False    # True si responde 401/403
    content_type: str = ""
    size_bytes: int = 0
    elapsed_ms: int = 0
    error: Optional[str] = None
    cors: Dict[str, str] = field(default_factory=dict)


def discover(
    base_url: str,
    paths: Optional[List[str]] = None,
    cfg: Optional[FetcherConfig] = None,
    bearer: Optional[str] = None,
    basic: Optional[Tuple[str, str]] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    origin: Optional[str] = None,
    delay_between: float = 0.0,
    do_options: bool = True,
    progress: bool = False,
) -> Dict[str, Any]:
    """
    Hace recon de superficie de una API.

    Args:
        base_url: URL base (ej: https://api.target.com).
        paths: lista de paths a probar (default: DEFAULT_RECON_PATHS).
        cfg: FetcherConfig opcional.
        bearer/basic/custom_headers: auth opcional.
        origin: Origin header para spoofing (útil para CORS whitelist).
        delay_between: pausa en segundos entre requests.
        do_options: hacer OPTIONS para fingerprint CORS.
        progress: mostrar progreso en stderr.

    Returns:
        Dict con:
          - base_url
          - fingerprint: server, lang, auth_scheme, cors
          - endpoints: lista de EndpointHit
          - stats: contadores (200, 401, 403, 404, 5xx, error)
          - elapsed_total_ms
    """
    cfg = cfg or FetcherConfig()
    paths = paths or DEFAULT_RECON_PATHS
    base_url = base_url.rstrip("/")
    endpoints: List[EndpointHit] = []
    stats = {"200": 0, "201": 0, "204": 0, "301": 0, "302": 0, "400": 0, "401": 0, "403": 0, "404": 0, "405": 0, "429": 0, "5xx": 0, "error": 0, "total": 0}
    start = time.monotonic()

    # 1. Fingerprint del server (un solo request a la raíz)
    if progress:
        print(f"  [recon] Fingerprinting {base_url} ...", flush=True)
    fingerprint = fingerprint_api(base_url, cfg=cfg, bearer=bearer)
    if progress:
        print(f"  [recon] Server: {fingerprint.get('server', '?')} | Lang: {fingerprint.get('backend_lang', '?')}", flush=True)

    # 2. Probar cada path
    for i, path in enumerate(paths):
        url = urljoin(base_url + "/", path.lstrip("/"))
        try:
            r = fetch(url, method="GET", cfg=cfg, bearer=bearer, basic=basic, custom_headers=custom_headers)
        except FetcherError as e:
            endpoints.append(EndpointHit(path=path, full_url=url, status=0, method="GET", error=str(e)))
            stats["error"] += 1
            stats["total"] += 1
            continue
        exists = r.status not in (0, 404, 410)
        auth_req = r.status in (401, 403)
        cors = r.cors
        ct = r.content_type
        size = len(r.body) if isinstance(r.body, (bytes, str)) else 0
        endpoints.append(EndpointHit(
            path=path, full_url=url, status=r.status, method="GET",
            exists=exists, auth_required=auth_req, content_type=ct,
            size_bytes=size, elapsed_ms=r.elapsed_ms, error=r.error, cors=cors,
        ))
        # Stats
        s = str(r.status)
        if s in stats:
            stats[s] += 1
        elif s.startswith("5"):
            stats["5xx"] += 1
        stats["total"] += 1
        if progress and ((i + 1) % 10 == 0 or i == len(paths) - 1):
            print(f"  [recon] {i+1}/{len(paths)} paths probados | {sum(v for k,v in stats.items() if k!='total')} con respuesta", flush=True)
        if delay_between > 0 and i < len(paths) - 1:
            time.sleep(delay_between)

    # 3. OPTIONS en paths que devolvieron 401/403/200 (CORS fingerprint)
    if do_options:
        for hit in endpoints:
            if hit.status in (200, 401, 403):
                try:
                    r = fetch_options(hit.full_url, cfg=cfg, origin=origin)
                    if r.cors:
                        hit.cors.update(r.cors)
                except FetcherError:
                    pass
                if delay_between > 0:
                    time.sleep(delay_between)

    elapsed = int((time.monotonic() - start) * 1000)

    # Resumen
    return {
        "base_url": base_url,
        "fingerprint": fingerprint,
        "endpoints": [hit.__dict__ for hit in endpoints],
        "stats": stats,
        "elapsed_total_ms": elapsed,
    }


def format_discovery_report(result: Dict[str, Any]) -> str:
    """Formatea un informe de discovery como texto."""
    lines = []
    fp = result.get("fingerprint", {})
    lines.append("=" * 70)
    lines.append(f"  RECON: {result['base_url']}")
    lines.append("=" * 70)
    lines.append(f"Server:      {fp.get('server', '?')}")
    lines.append(f"Backend:     {fp.get('backend_lang', '?')}")
    lines.append(f"Auth scheme: {fp.get('auth_scheme', '?')}")
    lines.append(f"CORS:        {fp.get('cors', {})}")
    lines.append(f"Elapsed:     {result['elapsed_total_ms']} ms")
    lines.append("")
    lines.append(f"{'Path':<45} {'Status':<8} {'Existe':<8} {'Auth':<6} {'Size':<8}")
    lines.append("-" * 70)
    for ep in result["endpoints"]:
        existe = "SI" if ep["exists"] else "NO"
        auth = "SI" if ep["auth_required"] else "-"
        size = ep["size_bytes"]
        lines.append(f"{ep['path']:<45} {ep['status']:<8} {existe:<8} {auth:<6} {size:<8}")
    lines.append("")
    s = result["stats"]
    lines.append(f"Stats: {s.get('200',0)}x 200 | {s.get('401',0)}x 401 | {s.get('403',0)}x 403 | {s.get('404',0)}x 404 | {s.get('5xx',0)}x 5xx | {s.get('error',0)}x error | total {s.get('total',0)}")
    return "\n".join(lines)
