"""
discovery.py — Recon de superficie de una API.

Prueba paths comunes, detecta métodos permitidos, captura CORS, fingerprint.
Inspirado en @scraper (Katana + flowsint) pero integrable directo en api-explorer.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
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
from .templates import (
    TemplateError,
    TemplateMatch,
    cargar_slot_values_desde_json,
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


# ───────────────────── Template-driven discovery (v0.4.0) ─────────────────────
# Sesión 2026-06-23 del DIARIO-TECNICO: en vez de hardcodear paths,
# dejamos que el usuario declare la *forma* de sus endpoints con
# variables (``/v1/:modulo/:accion``) y el motor itera los *valores*
# hasta encontrar combinaciones que matcheen (200 con JSON).
# Ventaja: discovery se vuelve reutilizable entre clientes sin importar
# cuál sea su estructura interna.


@dataclass
class TemplateHit:
    """Resultado de probar una combinación de una plantilla."""
    path: str                      # path instanciado, ej: /v1/users/list
    full_url: str                  # URL completa
    values: Dict[str, str]         # {modulo: 'users', accion: 'list'}
    status: int
    method: str = "GET"
    exists: bool = False           # True si pasó el filtro de "match"
    auth_required: bool = False
    content_type: str = ""
    size_bytes: int = 0
    elapsed_ms: int = 0
    error: Optional[str] = None


def _load_plantillas_default() -> Tuple[List[str], Dict[str, List[str]]]:
    """Carga plantillas.json desde reglas/. Falla silenciosa si no existe."""
    ruta = Path(__file__).parent.parent / "reglas" / "plantillas.json"
    if not ruta.exists():
        return ([], {})
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    plantillas = data.get("plantillas_basicas", [])
    valores = cargar_slot_values_desde_json(data.get("valores_default", {}))
    return (plantillas, valores)


def _es_match(r: FetchResult, criterios: Dict[str, Any]) -> bool:
    """
    Decide si una respuesta califica como "match" según los criterios
    del JSON de configuración. Por default: status 2xx + JSON + size > 0.
    """
    if r.status in criterios.get("status_not_found", [404, 410]):
        return False
    if r.status in criterios.get("status_ok", [200, 201, 202, 204]):
        ct = (r.content_type or "").lower()
        # Si acepta_json: requiere application/json. Si no, cualquier text/*
        if criterios.get("acepta_json", True):
            if "application/json" not in ct and "text/json" not in ct:
                return False
        elif criterios.get("acepta_text", False):
            if not ct.startswith("text/"):
                return False
        elif criterios.get("acepta_html", False):
            if "text/html" not in ct:
                return False
        # Tamaño mínimo. El body puede ser bytes, str, o un dict/list ya
        # parseado por el fetcher. Calculamos el equivalente en bytes
        # serializando a JSON si es objeto, sino len() directo.
        body = r.body
        if isinstance(body, (dict, list)):
            # JSON parseado: tiene datos si no está vacío
            size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
            non_empty = len(body) > 0 if hasattr(body, "__len__") else True
        elif isinstance(body, (bytes, str)):
            size = len(body)
            non_empty = size > 0
        else:
            size = 0
            non_empty = body is not None
        if not non_empty:
            return False
        if size < criterios.get("min_size_bytes_match", 1):
            return False
        return True
    return False


def descubrir_por_template(
    base_url: str,
    plantilla: str,
    slot_values: Optional[Dict[str, List[str]]] = None,
    cfg: Optional[FetcherConfig] = None,
    bearer: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    delay_between: float = 0.0,
    criterios: Optional[Dict[str, Any]] = None,
    max_combinaciones: Optional[int] = None,
    progress: bool = False,
) -> Dict[str, Any]:
    """
    Discovery usando una plantilla con variables.

    Itera todas las combinaciones de valores para las variables de la
    plantilla y devuelve los paths que matchean (status 2xx + content
    válido).

    Args:
        base_url: URL base (ej: https://api.target.com).
        plantilla: ej: "/v1/:modulo/:accion".
        slot_values: dict {variable: [valores]}. Si falta una variable,
                     se prueba con string vacío.
        cfg: FetcherConfig opcional.
        bearer/custom_headers: auth opcional.
        delay_between: pausa entre requests.
        criterios: filtros de "match" (status, content_type, size).
        max_combinaciones: tope de seguridad. Si None, se permiten todas.
        progress: imprimir progreso en stderr.

    Returns:
        Dict con:
          - base_url
          - plantilla
          - combinaciones_probadas: total
          - matches: lista de TemplateHit (los que pasaron el filtro)
          - no_matches: lista de TemplateHit (los que devolvieron 404/410/error)
          - auth_required: lista de TemplateHit (los 401/403)
          - elapsed_total_ms
    """
    cfg = cfg or FetcherConfig()
    slot_values = slot_values or {}
    criterios = criterios or {
        "status_ok": [200, 201, 202, 204],
        "status_not_found": [404, 410],
        "min_size_bytes_match": 1,
        "acepta_json": True,
    }

    try:
        tm = TemplateMatch(plantilla)
    except TemplateError as e:
        return {
            "base_url": base_url,
            "plantilla": plantilla,
            "error": str(e),
            "matches": [],
            "no_matches": [],
            "auth_required": [],
        }

    base_url = base_url.rstrip("/")
    matches: List[TemplateHit] = []
    no_matches: List[TemplateHit] = []
    auth_required: List[TemplateHit] = []
    stats = {"200": 0, "201": 0, "204": 0, "401": 0, "403": 0, "404": 0, "405": 0, "410": 0, "5xx": 0, "error": 0, "total": 0}
    start = time.monotonic()

    total_combinaciones = tm.combinaciones_total(slot_values)
    if max_combinaciones and total_combinaciones > max_combinaciones:
        if progress:
            print(
                f"  [template] {total_combinaciones} combinaciones > max={max_combinaciones}, recortando",
                flush=True,
            )
        total_combinaciones = max_combinaciones

    if progress:
        print(
            f"  [template] Plantilla: {plantilla} | {total_combinaciones} combinaciones",
            flush=True,
        )

    i = 0
    for combo in tm.iterar_combinaciones(slot_values):
        if max_combinaciones and i >= max_combinaciones:
            break
        # Filtrar combinaciones donde el path quedó con // o vacío
        try:
            path = tm.instanciar(combo)
        except TemplateError as e:
            if progress:
                print(f"  [template] skip {combo}: {e}", flush=True)
            continue
        if not path or "//" in path:
            continue
        url = urljoin(base_url + "/", path.lstrip("/"))

        try:
            r = fetch(
                url, method="GET", cfg=cfg, bearer=bearer, custom_headers=custom_headers
            )
        except FetcherError as e:
            no_matches.append(TemplateHit(
                path=path, full_url=url, values=combo,
                status=0, exists=False, error=str(e),
            ))
            stats["error"] += 1
            stats["total"] += 1
            i += 1
            continue

        # Tamaño: serializar a bytes si es dict/list, sino len() directo
        if isinstance(r.body, (dict, list)):
            size = len(json.dumps(r.body, ensure_ascii=False).encode("utf-8"))
        elif isinstance(r.body, (bytes, str)):
            size = len(r.body)
        else:
            size = 0
        elapsed = r.elapsed_ms
        ct = r.content_type or ""
        auth_req = r.status in (401, 403)
        es_match = _es_match(r, criterios)

        hit = TemplateHit(
            path=path, full_url=url, values=combo,
            status=r.status, method="GET",
            exists=es_match, auth_required=auth_req,
            content_type=ct, size_bytes=size, elapsed_ms=elapsed,
            error=r.error,
        )
        if es_match:
            matches.append(hit)
        elif auth_req:
            auth_required.append(hit)
        else:
            no_matches.append(hit)

        s = str(r.status)
        if s in stats:
            stats[s] += 1
        elif s.startswith("5"):
            stats["5xx"] += 1
        stats["total"] += 1

        if progress and ((i + 1) % 20 == 0 or i + 1 == total_combinaciones):
            print(
                f"  [template] {i+1}/{total_combinaciones} | {len(matches)} matches | {len(auth_required)} auth | {len(no_matches)} no-match",
                flush=True,
            )
        if delay_between > 0:
            time.sleep(delay_between)
        i += 1

    elapsed = int((time.monotonic() - start) * 1000)
    return {
        "base_url": base_url,
        "plantilla": plantilla,
        "variables": tm.vars,
        "combinaciones_probadas": stats["total"],
        "matches": [h.__dict__ for h in matches],
        "auth_required": [h.__dict__ for h in auth_required],
        "no_matches": [h.__dict__ for h in no_matches],
        "stats": stats,
        "elapsed_total_ms": elapsed,
    }


def format_template_report(result: Dict[str, Any]) -> str:
    """Formatea el resultado de descubrir_por_template() como texto legible."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"  TEMPLATE DISCOVERY: {result.get('plantilla', '?')}")
    lines.append(f"  Base URL: {result.get('base_url', '?')}")
    lines.append("=" * 70)
    if "error" in result:
        lines.append(f"  ERROR: {result['error']}")
        return "\n".join(lines)
    lines.append(f"Variables:          {', '.join(result.get('variables', []))}")
    lines.append(f"Combinaciones:      {result.get('combinaciones_probadas', 0)}")
    lines.append(f"Matches:            {len(result.get('matches', []))}")
    lines.append(f"Auth required:      {len(result.get('auth_required', []))}")
    lines.append(f"No match:           {len(result.get('no_matches', []))}")
    lines.append(f"Elapsed:            {result.get('elapsed_total_ms', 0)} ms")
    lines.append("")
    if result.get("matches"):
        lines.append("✓ MATCHES (endpoints que respondieron con datos)")
        lines.append("-" * 70)
        for h in result["matches"]:
            valores = ", ".join(f"{k}={v}" for k, v in h["values"].items() if v)
            extra = f"  {{{valores}}}" if valores else ""
            lines.append(
                f"  {h['path']:<40} {h['status']}  {h['size_bytes']}B  {h['content_type'][:30]}{extra}"
            )
        lines.append("")
    if result.get("auth_required"):
        lines.append("🔒 AUTH REQUIRED (existe pero pide credenciales)")
        lines.append("-" * 70)
        for h in result["auth_required"]:
            valores = ", ".join(f"{k}={v}" for k, v in h["values"].items() if v)
            extra = f"  {{{valores}}}" if valores else ""
            lines.append(f"  {h['path']:<40} {h['status']}{extra}")
        lines.append("")
    if result.get("no_matches"):
        no_match_sample = result["no_matches"][:5]
        lines.append(f"✗ NO MATCH ({len(result['no_matches'])} total, mostrando primeros 5)")
        lines.append("-" * 70)
        for h in no_match_sample:
            valores = ", ".join(f"{k}={v}" for k, v in h["values"].items() if v)
            extra = f"  {{{valores}}}" if valores else ""
            err = f"  ERR: {h['error'][:40]}" if h.get("error") else ""
            lines.append(f"  {h['path']:<40} {h['status']}{extra}{err}")
        if len(result["no_matches"]) > 5:
            lines.append(f"  ... y {len(result['no_matches']) - 5} más")
    return "\n".join(lines)
