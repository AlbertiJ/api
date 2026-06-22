"""
fetcher.py — Cliente HTTP robusto con auth, retry, rate limit, CORS fingerprint.

Reemplaza el uso directo de urllib.request.urlopen en core.py.
Soporta:
  - Bearer token / Basic auth / custom headers
  - Retry exponencial (3 intentos)
  - Rate limit handling (HTTP 429 → respeta Retry-After)
  - Captura headers CORS para fingerprint de la API
  - Timeout configurable
  - Proxy configurable (opcional)
"""
from __future__ import annotations

import base64
import json
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass
class FetcherConfig:
    """Configuración del fetcher."""
    timeout: int = 30
    max_retries: int = 3
    backoff_base: float = 0.5
    user_agent: str = "api-explorer/0.3.0 (compatible; reconnaissance)"
    follow_redirects: bool = True
    verify_cors: bool = True


@dataclass
class FetchResult:
    """Resultado de un fetch HTTP."""
    url: str
    method: str
    status: int
    body: Any                      # bytes, str, o dict si era JSON
    content_type: str
    headers: Dict[str, str] = field(default_factory=dict)
    cors: Dict[str, str] = field(default_factory=dict)  # CORS headers encontrados
    elapsed_ms: int = 0
    error: Optional[str] = None
    auth_used: Optional[str] = None  # bearer / basic / custom
    redirected: bool = False


class FetcherError(Exception):
    """Error del fetcher."""


def _build_headers(
    method: str,
    cfg: FetcherConfig,
    bearer: Optional[str] = None,
    basic_user: Optional[Tuple[str, str]] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    extra_body_headers: bool = True,
) -> Dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "User-Agent": cfg.user_agent,
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if basic_user:
        user, pwd = basic_user
        token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if custom_headers:
        headers.update(custom_headers)
    if method in ("POST", "PUT", "PATCH", "DELETE") and extra_body_headers:
        headers.setdefault("Content-Type", "application/json")
    return headers


def _parse_body(raw: bytes, content_type: str) -> Any:
    """Parsea el body según Content-Type."""
    if not raw:
        return None
    ct = content_type.lower()
    if "application/json" in ct or "text/json" in ct:
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return raw.decode("utf-8", errors="replace")
    if "text/" in ct:
        return raw.decode("utf-8", errors="replace")
    return raw


def _extract_cors(headers: Dict[str, str]) -> Dict[str, str]:
    cors_keys = [k for k in headers.keys() if k.lower().startswith("access-control-")]
    return {k: headers[k] for k in cors_keys}


def fetch(
    url: str,
    method: str = "GET",
    cfg: Optional[FetcherConfig] = None,
    bearer: Optional[str] = None,
    basic: Optional[Tuple[str, str]] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
) -> FetchResult:
    """
    Hace un request HTTP robusto.

    Args:
        url: URL a fetchear.
        method: GET / POST / PUT / PATCH / DELETE / OPTIONS / HEAD.
        cfg: FetcherConfig opcional.
        bearer: token Bearer (opcional).
        basic: tupla (user, password) para Basic auth.
        custom_headers: headers extra (ej: cookies, Origin spoofing).
        body: bytes para POST/PUT (opcional).

    Returns:
        FetchResult con status, body parseado, headers, CORS fingerprint.
    """
    if cfg is None:
        cfg = FetcherConfig()
    method = method.upper()
    auth_used = None
    if bearer:
        auth_used = "bearer"
    elif basic:
        auth_used = "basic"
    elif custom_headers and any(k.lower() == "authorization" for k in custom_headers):
        auth_used = "custom"

    headers = _build_headers(method, cfg, bearer, basic, custom_headers)

    last_error = None
    for attempt in range(cfg.max_retries):
        start = time.monotonic()
        try:
            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req, timeout=cfg.timeout) as resp:
                status = resp.status
                raw = resp.read()
                # Re-extraer headers a dict
                hdrs = {k: v for k, v in resp.headers.items()}
                ct = hdrs.get("Content-Type", "")
                elapsed = int((time.monotonic() - start) * 1000)
                # Detectar redirect (urllib lo sigue solo si no especificás method=POST, etc)
                redirected = resp.url != url
                return FetchResult(
                    url=url,
                    method=method,
                    status=status,
                    body=_parse_body(raw, ct),
                    content_type=ct,
                    headers=hdrs,
                    cors=_extract_cors(hdrs) if cfg.verify_cors else {},
                    elapsed_ms=elapsed,
                    auth_used=auth_used,
                    redirected=redirected,
                )
        except HTTPError as e:
            elapsed = int((time.monotonic() - start) * 1000)
            raw = e.read() if hasattr(e, "read") else b""
            hdrs = dict(e.headers.items()) if e.headers else {}
            ct = hdrs.get("Content-Type", "")
            last_error = f"HTTP {e.code}: {e.reason}"
            # 429: respetar Retry-After si existe
            if e.code == 429 and attempt < cfg.max_retries - 1:
                retry_after = float(e.headers.get("Retry-After", cfg.backoff_base * (2 ** attempt)))
                time.sleep(min(retry_after, 30))
                continue
            # 4xx no reintentar (excepto 408, 425, 429)
            if e.code in (408, 425) and attempt < cfg.max_retries - 1:
                time.sleep(cfg.backoff_base * (2 ** attempt))
                continue
            return FetchResult(
                url=url, method=method, status=e.code,
                body=_parse_body(raw, ct), content_type=ct,
                headers=hdrs,
                cors=_extract_cors(hdrs) if cfg.verify_cors else {},
                elapsed_ms=elapsed, error=last_error, auth_used=auth_used,
            )
        except (URLError, socket.timeout, ConnectionError) as e:
            last_error = str(e)
            if attempt < cfg.max_retries - 1:
                time.sleep(cfg.backoff_base * (2 ** attempt))
                continue
            raise FetcherError(f"No se pudo conectar a {url}: {last_error}") from e

    # Si agotó retries sin retornar, devolver error genérico
    return FetchResult(
        url=url, method=method, status=0, body=None,
        content_type="", error=last_error or "max retries agotados",
        auth_used=auth_used,
    )


def fetch_options(url: str, cfg: Optional[FetcherConfig] = None,
                  origin: Optional[str] = None) -> FetchResult:
    """Helper: hace OPTIONS para fingerprint CORS."""
    custom = {}
    if origin:
        custom["Origin"] = origin
        custom["Access-Control-Request-Method"] = "GET"
    return fetch(url, method="OPTIONS", cfg=cfg, custom_headers=custom or None)


def fingerprint_api(
    base_url: str,
    cfg: Optional[FetcherConfig] = None,
    bearer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hace un fingerprint rápido de una API: server, framework, auth_scheme, cors.

    Returns:
        Dict con los campos detectados.
    """
    cfg = cfg or FetcherConfig()
    out: Dict[str, Any] = {
        "base_url": base_url,
        "server": "desconocido",
        "backend_lang": "desconocido",
        "auth_scheme": "desconocido",
        "cors": {},
        "fingerprint_components": [],
    }
    # 1. GET a la raíz
    try:
        r = fetch(base_url, cfg=cfg, bearer=bearer)
        out["server"] = r.headers.get("Server", "desconocido")
        out["root_status"] = r.status
        out["root_content_type"] = r.content_type
        out["cors"] = r.cors
        # Fingerprints comunes
        if "tomcat" in out["server"].lower():
            out["backend_lang"] = "Java (Tomcat)"
            out["fingerprint_components"].append("Apache Tomcat")
        elif "nginx" in out["server"].lower():
            out["backend_lang"] = "nginx (frontend proxy probable)"
            out["fingerprint_components"].append("nginx")
        elif "cloudflare" in str(r.headers).lower():
            out["fingerprint_components"].append("CloudFront/Cloudflare")
        if r.cors:
            origin = r.cors.get("Access-Control-Allow-Origin", "")
            methods = r.cors.get("Access-Control-Allow-Methods", "")
            if "Bearer" in str(r.headers).lower() or bearer:
                out["auth_scheme"] = "Bearer (probable JWT o session)"
            elif methods:
                out["auth_scheme"] = f"Custom ({methods})"
    except FetcherError as e:
        out["error"] = str(e)
    return out
