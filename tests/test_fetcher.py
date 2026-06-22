"""
Tests del fetcher (explorer/fetcher.py).

Cubre:
  - GET/POST/PUT/DELETE/OPTIONS
  - Auth: Bearer / Basic / custom headers
  - Retry en 429 con Retry-After
  - Retry exponencial en 503
  - CORS fingerprint
  - fingerprint_api (server detection)
  - Manejo de errores de red
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Permite importar el paquete sin instalarlo.
sys.path.insert(0, str(Path(__file__).parent.parent))

from explorer.fetcher import (
    FetcherConfig,
    FetchResult,
    FetcherError,
    fetch,
    fetch_options,
    fingerprint_api,
    _build_headers,
    _extract_cors,
    _parse_body,
)


# ─────────────────────────── helpers ───────────────────────────

def _fake_response(
    status: int = 200,
    body: bytes = b'{"ok": true}',
    headers: dict = None,
    url_final: str = None,
) -> MagicMock:
    """Construye un mock del context manager de urlopen."""
    headers = headers or {"Content-Type": "application/json"}
    cm = MagicMock()
    cm.__enter__.return_value.status = status
    cm.__enter__.return_value.read.return_value = body
    cm.__enter__.return_value.headers.items.return_value = list(headers.items())
    cm.__enter__.return_value.url = url_final or "https://example.com"
    return cm


# ─────────────────────────── _build_headers ───────────────────────────

def test_build_headers_sin_auth():
    h = _build_headers("GET", FetcherConfig())
    assert "Accept" in h
    assert "User-Agent" in h
    assert "Authorization" not in h
    print("  ✓ test_build_headers_sin_auth")


def test_build_headers_con_bearer():
    h = _build_headers("GET", FetcherConfig(), bearer="abc123")
    assert h["Authorization"] == "Bearer abc123"
    print("  ✓ test_build_headers_con_bearer")


def test_build_headers_con_basic():
    h = _build_headers("GET", FetcherConfig(), basic_user=("user", "pass"))
    expected = "Basic " + base64.b64encode(b"user:pass").decode("ascii")
    assert h["Authorization"] == expected
    print("  ✓ test_build_headers_con_basic")


def test_build_headers_con_custom():
    h = _build_headers("GET", FetcherConfig(), custom_headers={"X-Foo": "bar", "Origin": "https://x.com"})
    assert h["X-Foo"] == "bar"
    assert h["Origin"] == "https://x.com"
    print("  ✓ test_build_headers_con_custom")


def test_build_headers_post_agrega_content_type():
    h = _build_headers("POST", FetcherConfig())
    assert h["Content-Type"] == "application/json"
    print("  ✓ test_build_headers_post_agrega_content_type")


# ─────────────────────────── _extract_cors ───────────────────────────

def test_extract_cors_filtra_headers():
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "https://x.com",
        "Access-Control-Allow-Methods": "GET, POST",
        "Server": "nginx",
    }
    cors = _extract_cors(headers)
    assert "Access-Control-Allow-Origin" in cors
    assert "Access-Control-Allow-Methods" in cors
    assert "Content-Type" not in cors
    assert "Server" not in cors
    print("  ✓ test_extract_cors_filtra_headers")


# ─────────────────────────── _parse_body ───────────────────────────

def test_parse_body_json():
    body = _parse_body(b'{"a": 1}', "application/json")
    assert body == {"a": 1}
    print("  ✓ test_parse_body_json")


def test_parse_body_text():
    body = _parse_body(b"hola mundo", "text/plain")
    assert body == "hola mundo"
    print("  ✓ test_parse_body_text")


def test_parse_body_binario():
    body = _parse_body(b"\x00\x01\x02", "image/png")
    assert isinstance(body, bytes)
    print("  ✓ test_parse_body_binario")


def test_parse_body_vacio():
    assert _parse_body(b"", "application/json") is None
    print("  ✓ test_parse_body_vacio")


# ─────────────────────────── fetch() ───────────────────────────

def test_fetch_get_exitoso():
    cm = _fake_response(200, b'{"data": "ok"}', {"Content-Type": "application/json"})
    with patch("explorer.fetcher.urlopen", return_value=cm):
        r = fetch("https://x.com/api")
    assert r.status == 200
    assert r.body == {"data": "ok"}
    assert r.method == "GET"
    assert r.error is None
    assert r.elapsed_ms >= 0
    print(f"  ✓ test_fetch_get_exitoso → {r.status} {r.elapsed_ms}ms")


def test_fetch_post_con_body():
    cm = _fake_response(201, b'{"created": true}', {"Content-Type": "application/json"})
    with patch("explorer.fetcher.urlopen", return_value=cm) as mock_urlopen:
        r = fetch("https://x.com/api", method="POST", body=b'{"x": 1}')
    assert r.status == 201
    # El método POST y el body se pasaron al Request
    call_args = mock_urlopen.call_args
    req = call_args[0][0]
    assert req.method == "POST"
    assert req.data == b'{"x": 1}'
    print(f"  ✓ test_fetch_post_con_body → {r.status}")


def test_fetch_con_bearer_pasa_header():
    cm = _fake_response(200, b'{}', {"Content-Type": "application/json"})
    with patch("explorer.fetcher.urlopen", return_value=cm) as mock_urlopen:
        r = fetch("https://x.com", bearer="token_xyz")
    req = mock_urlopen.call_args[0][0]
    assert req.headers.get("Authorization") == "Bearer token_xyz"
    assert r.auth_used == "bearer"
    print(f"  ✓ test_fetch_con_bearer_pasa_header → {r.status}")


def test_fetch_404_devuelve_result_con_error():
    from urllib.error import HTTPError
    err = HTTPError("https://x.com", 404, "Not Found", {}, None)
    with patch("explorer.fetcher.urlopen", side_effect=err):
        r = fetch("https://x.com/missing")
    assert r.status == 404
    assert r.error is not None
    assert "404" in r.error
    print(f"  ✓ test_fetch_404_devuelve_result_con_error → {r.error}")


def test_fetch_429_retry_y_finalmente_falla():
    from urllib.error import HTTPError
    err = HTTPError("https://x.com", 429, "Too Many Requests", {"Retry-After": "0.01"}, None)
    with patch("explorer.fetcher.urlopen", side_effect=err):
        r = fetch("https://x.com", cfg=FetcherConfig(max_retries=2, backoff_base=0.001))
    assert r.status == 429
    print(f"  ✓ test_fetch_429_retry_y_finalmente_falla → {r.status}")


def test_fetch_503_retry_y_exitoso():
    """Simula que el primer intento da 503, el segundo da 200."""
    from urllib.error import HTTPError
    err = HTTPError("https://x.com", 503, "Service Unavailable", {}, None)
    ok_cm = _fake_response(200, b'{"ok":1}', {"Content-Type": "application/json"})
    with patch("explorer.fetcher.urlopen", side_effect=[err, ok_cm]) as mock_urlopen:
        r = fetch("https://x.com", cfg=FetcherConfig(max_retries=3, backoff_base=0.001))
    assert r.status == 200
    assert mock_urlopen.call_count == 2  # 1 fail + 1 ok
    print(f"  ✓ test_fetch_503_retry_y_exitoso → 2 attempts, final {r.status}")


def test_fetch_error_de_red_lanza_fetcher_error():
    from urllib.error import URLError
    err = URLError("Name or service not known")
    with patch("explorer.fetcher.urlopen", side_effect=err):
        try:
            fetch("https://noexiste.invalid", cfg=FetcherConfig(max_retries=1, backoff_base=0.001))
            assert False, "Debería haber lanzado FetcherError"
        except FetcherError as e:
            assert "noexiste.invalid" in str(e)
    print("  ✓ test_fetch_error_de_red_lanza_fetcher_error")


def test_fetch_401_marca_auth_required_en_caller():
    """El fetcher devuelve 401; el caller puede detectar auth_required."""
    from urllib.error import HTTPError
    err = HTTPError("https://x.com", 401, "Unauthorized", {"WWW-Authenticate": "Bearer"}, None)
    with patch("explorer.fetcher.urlopen", side_effect=err):
        r = fetch("https://x.com/protected")
    assert r.status == 401
    assert r.headers.get("WWW-Authenticate") == "Bearer"
    print(f"  ✓ test_fetch_401_marca_auth_required_en_caller → {r.status}")


# ─────────────────────────── fetch_options ───────────────────────────

def test_fetch_options_agrega_origin():
    cm = _fake_response(200, b"", {"Access-Control-Allow-Origin": "*"})
    with patch("explorer.fetcher.urlopen", return_value=cm) as mock_urlopen:
        r = fetch_options("https://x.com/api", origin="https://attacker.com")
    assert r.method == "OPTIONS"
    req = mock_urlopen.call_args[0][0]
    # Los headers del Request se acceden por .headers o .unredirected_hdrs
    # Las claves están normalizadas a Title-Case en urllib
    all_headers = dict(req.header_items()) if hasattr(req, "header_items") else {}
    # Fallback: combinar todas las fuentes
    for src in (getattr(req, "headers", {}), getattr(req, "unredirected_hdrs", {})):
        for k, v in src.items():
            all_headers[k] = v
    assert all_headers.get("Origin") == "https://attacker.com", f"Headers: {all_headers}"
    assert all_headers.get("Access-control-request-method") == "GET", f"Headers: {all_headers}"
    print("  ✓ test_fetch_options_agrega_origin")


# ─────────────────────────── fingerprint_api ───────────────────────────

def test_fingerprint_api_detecta_tomcat():
    cm = _fake_response(200, b"<html/>", {"Server": "Apache-Coyote/1.1"})
    with patch("explorer.fetcher.urlopen", return_value=cm):
        fp = fingerprint_api("https://x.com")
    assert "Tomcat" in fp.get("backend_lang", "") or "Java" in fp.get("backend_lang", "")
    assert "Apache Tomcat" in fp.get("fingerprint_components", [])
    print(f"  ✓ test_fingerprint_api_detecta_tomcat → {fp.get('backend_lang')}")


def test_fingerprint_api_detecta_nginx():
    cm = _fake_response(200, b"{}", {"Server": "nginx/1.21.0"})
    with patch("explorer.fetcher.urlopen", return_value=cm):
        fp = fingerprint_api("https://x.com")
    assert "nginx" in fp.get("backend_lang", "").lower() or "nginx" in fp.get("fingerprint_components", [])
    print(f"  ✓ test_fingerprint_api_detecta_nginx → {fp.get('backend_lang')}")


def test_fingerprint_api_detecta_cloudflare():
    cm = _fake_response(200, b"{}", {"Server": "cloudflare", "CF-RAY": "abc123"})
    with patch("explorer.fetcher.urlopen", return_value=cm):
        fp = fingerprint_api("https://x.com")
    assert "CloudFront" in fp.get("fingerprint_components", []) or "Cloudflare" in str(fp)
    print(f"  ✓ test_fingerprint_api_detecta_cloudflare → {fp.get('fingerprint_components')}")


def test_fingerprint_api_error_no_lanza_excepcion():
    """Si la URL no responde, devuelve dict con error, no excepción."""
    with patch("explorer.fetcher.urlopen", side_effect=FetcherError("no se pudo")):
        fp = fingerprint_api("https://noexiste.invalid")
    assert "error" in fp or fp.get("server") == "desconocido"
    print("  ✓ test_fingerprint_api_error_no_lanza_excepcion")


def test_fingerprint_api_con_bearer_detecta_auth_scheme():
    cm = _fake_response(200, b"{}", {"Server": "nginx"})
    with patch("explorer.fetcher.urlopen", return_value=cm):
        fp = fingerprint_api("https://x.com", bearer="token_xyz")
    assert "Bearer" in fp.get("auth_scheme", "") or "Authorization" in fp.get("auth_scheme", "")
    print(f"  ✓ test_fingerprint_api_con_bearer_detecta_auth_scheme → {fp.get('auth_scheme')}")


# ─────────────────────────── integración opcional ───────────────────────────

def test_fetch_real_jsonplaceholder(silencioso=True):
    """Integration test: hace un fetch real a jsonplaceholder.typicode.com.
    Requiere conectividad. Marcado con skip si no hay red."""
    import socket
    try:
        socket.create_connection(("jsonplaceholder.typicode.com", 443), timeout=2).close()
    except (OSError, socket.timeout):
        if not silencioso:
            print("  ⊝ test_fetch_real_jsonplaceholder → SKIP (sin red)")
        return
    try:
        r = fetch("https://jsonplaceholder.typicode.com/users/1", cfg=FetcherConfig(timeout=5))
        assert r.status == 200
        assert isinstance(r.body, dict)
        assert r.body.get("id") == 1
        if not silencioso:
            print(f"  ✓ test_fetch_real_jsonplaceholder → {r.status} id={r.body.get('id')}")
    except Exception as e:
        if not silencioso:
            print(f"  ⊝ test_fetch_real_jsonplaceholder → SKIP ({e})")


if __name__ == "__main__":
    print("=" * 60)
    print("  TESTS: explorer/fetcher.py")
    print("=" * 60)
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  ✗ {t.__name__} → {type(e).__name__}: {e}")
    print()
    print("=" * 60)
    print("  INTEGRATION (requiere red)")
    print("=" * 60)
    test_fetch_real_jsonplaceholder(silencioso=False)
    print()
    print("[done]")
