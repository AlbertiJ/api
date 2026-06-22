"""
Tests del discovery (explorer/discovery.py).

Cubre:
  - discover() sobre una URL con paths pre-armados
  - Detección de endpoints que existen (200) vs no (404)
  - Detección de auth required (401/403)
  - CORS fingerprint via OPTIONS
  - Paths custom
  - Delay entre requests
  - Stats y formato del informe
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Permite importar el paquete sin instalarlo.
sys.path.insert(0, str(Path(__file__).parent.parent))

from explorer.discovery import (
    DEFAULT_RECON_PATHS,
    EndpointHit,
    discover,
    format_discovery_report,
)
from explorer.fetcher import FetchResult, FetcherConfig
from explorer.pipeline import _rank_endpoints


# ─────────────────────────── helpers ───────────────────────────

def make_fetch_result(url, status, body=b"", content_type="text/plain", cors=None, auth=None):
    """Construye un FetchResult mock."""
    return FetchResult(
        url=url,
        method="GET",
        status=status,
        body=body,
        content_type=content_type,
        headers={"Server": "test"},
        cors=cors or {},
        elapsed_ms=10,
        auth_used=auth,
    )


# ─────────────────────────── _rank_endpoints ───────────────────────────

def test_rank_endpoints_prioriza_200():
    eps = [
        {"path": "/404", "status": 404, "exists": False},  # 404 = no existe
        {"path": "/200", "status": 200, "exists": True, "size_bytes": 1000},
        {"path": "/401", "status": 401, "exists": True, "size_bytes": 0},
        {"path": "/403", "status": 403, "exists": True, "size_bytes": 0},
    ]
    ranked = _rank_endpoints(eps)
    # 200 primero (score 10)
    assert ranked[0]["status"] == 200
    # Después 401 (score 8)
    assert ranked[1]["status"] == 401
    # 403 último (score 6)
    assert ranked[-1]["status"] == 403
    print(f"  ✓ test_rank_endpoints_prioriza_200 → {[e['path'] for e in ranked]}")


def test_rank_endpoints_ordena_por_size_dentro_de_200():
    """Dentro de los 200, los de mayor size_bytes primero (más contenido = más interesante)."""
    eps = [
        {"path": "/small", "status": 200, "exists": True, "size_bytes": 100},
        {"path": "/big", "status": 200, "exists": True, "size_bytes": 5000},
        {"path": "/medium", "status": 200, "exists": True, "size_bytes": 1000},
    ]
    ranked = _rank_endpoints(eps)
    assert ranked[0]["path"] == "/big"
    assert ranked[1]["path"] == "/medium"
    assert ranked[2]["path"] == "/small"
    print(f"  ✓ test_rank_endpoints_ordena_por_size_dentro_de_200 → {[e['path'] for e in ranked]}")


def test_rank_endpoints_solo_existentes():
    """Los 404 NO se incluyen (porque exists=False)."""
    eps = [
        {"path": "/nope", "status": 404, "exists": False},
        {"path": "/yes", "status": 200, "exists": True, "size_bytes": 100},
    ]
    ranked = _rank_endpoints(eps)
    assert len(ranked) == 1
    assert ranked[0]["path"] == "/yes"
    print("  ✓ test_rank_endpoints_solo_existentes")


# ─────────────────────────── discover() mockeado ───────────────────────────

def _patched_discover(base_url, fetch_responses_by_url=None, **kwargs):
    """Helper: parchea fetch y fetch_options para devolver respuestas predefinidas."""
    fetch_responses_by_url = fetch_responses_by_url or {}

    def fake_fetch(url, method="GET", cfg=None, **kw):
        # Match por suffix del path (estricto: el path debe ser el final del URL)
        # Sort por longitud descendente para que paths más específicos matcheen primero
        for path in sorted(fetch_responses_by_url.keys(), key=len, reverse=True):
            if url.endswith(path):
                return fetch_responses_by_url[path]
        # Default: 404
        return make_fetch_result(url, status=404, body=b"", content_type="")
    return fake_fetch


def test_discover_detecta_endpoints_que_existen():
    base = "https://api.test.com"
    responses = {
        "/users": make_fetch_result(base + "/users", 200, b'[{"id":1}]', "application/json"),
        "/health": make_fetch_result(base + "/health", 200, b"OK", "text/plain"),
        "/missing": make_fetch_result(base + "/missing", 404, b""),
    }
    custom_paths = ["/users", "/health", "/missing"]
    with patch("explorer.discovery.fetch", side_effect=_patched_discover(base, responses)), \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}):
        cfg = FetcherConfig()
        result = discover(base_url=base, cfg=cfg, paths=custom_paths, do_options=False, delay_between=0)
    assert result["stats"]["200"] == 2
    assert result["stats"]["404"] == 1
    assert result["stats"]["total"] == 3
    print(f"  ✓ test_discover_detecta_endpoints_que_existen → {result['stats']}")


def test_discover_detecta_auth_required():
    base = "https://api.test.com"
    responses = {
        "/protected": make_fetch_result(base + "/protected", 401, b""),
        "/forbidden": make_fetch_result(base + "/forbidden", 403, b""),
    }
    with patch("explorer.discovery.fetch", side_effect=_patched_discover(base, responses)), \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}):
        cfg = FetcherConfig()
        result = discover(base_url=base, cfg=cfg, do_options=False, paths=["/protected", "/forbidden"], delay_between=0)
    eps = result["endpoints"]
    protected = next(e for e in eps if e["path"] == "/protected")
    forbidden = next(e for e in eps if e["path"] == "/forbidden")
    assert protected["auth_required"] is True
    assert forbidden["auth_required"] is True
    print(f"  ✓ test_discover_detecta_auth_required → {result['stats']}")


def test_discover_pasa_bearer_a_fetch():
    base = "https://api.test.com"
    with patch("explorer.discovery.fetch", return_value=make_fetch_result(base + "/", 200)) as mock_fetch, \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}):
        cfg = FetcherConfig()
        discover(base_url=base, cfg=cfg, bearer="my_token", paths=["/test"], do_options=False, delay_between=0)
    # Verificar que bearer se pasó
    call_kwargs = mock_fetch.call_args.kwargs
    assert call_kwargs.get("bearer") == "my_token"
    print("  ✓ test_discover_pasa_bearer_a_fetch")


def test_discover_cors_via_options():
    base = "https://api.test.com"
    cors_headers = {
        "Access-Control-Allow-Origin": "https://www.ejemplo.com",
        "Access-Control-Allow-Methods": "GET, POST",
    }
    main_resp = make_fetch_result(base + "/api", 200, b"{}", "application/json")
    opt_resp = FetchResult(
        url=base + "/api", method="OPTIONS", status=200, body=b"", content_type="", headers={},
        cors=cors_headers,
    )
    with patch("explorer.discovery.fetch", return_value=main_resp) as mock_fetch, \
         patch("explorer.discovery.fetch_options", return_value=opt_resp) as mock_opts, \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}):
        cfg = FetcherConfig()
        result = discover(base_url=base, cfg=cfg, paths=["/api"], do_options=True, delay_between=0)
    # El endpoint /api ahora debería tener CORS
    api_ep = next(e for e in result["endpoints"] if e["path"] == "/api")
    assert "Access-Control-Allow-Origin" in api_ep["cors"]
    assert mock_opts.called
    print(f"  ✓ test_discover_cors_via_options → {api_ep['cors']}")


def test_discover_paths_custom():
    base = "https://api.test.com"
    custom_paths = ["/mi-endpoint-1", "/mi-endpoint-2", "/mi-endpoint-3"]
    with patch("explorer.discovery.fetch", return_value=make_fetch_result(base, 200)) as mock_fetch, \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}):
        cfg = FetcherConfig()
        result = discover(base_url=base, cfg=cfg, paths=custom_paths, do_options=False, delay_between=0)
    # Solo se probaron los 3 custom, no los 87 default
    assert result["stats"]["total"] == 3
    assert all(e["path"] in custom_paths for e in result["endpoints"])
    print(f"  ✓ test_discover_paths_custom → {result['stats']['total']} paths probados")


def test_discover_delay_entre_requests():
    base = "https://api.test.com"
    paths = [f"/p{i}" for i in range(3)]
    with patch("explorer.discovery.fetch", return_value=make_fetch_result(base, 200)) as mock_fetch, \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}), \
         patch("time.sleep") as mock_sleep:
        cfg = FetcherConfig()
        discover(base_url=base, cfg=cfg, paths=paths, do_options=False, delay_between=0.5)
    # delay_between=0.5, 3 paths → 2 sleep calls
    assert mock_sleep.call_count == 2
    # Todas las llamadas con 0.5
    for call in mock_sleep.call_args_list:
        assert call.args[0] == 0.5
    print(f"  ✓ test_discover_delay_entre_requests → {mock_sleep.call_count} sleeps de 0.5s")


def test_discover_stats_son_correctas():
    base = "https://api.test.com"
    responses = {
        "/a": make_fetch_result(base + "/a", 200, b"ok"),
        "/b": make_fetch_result(base + "/b", 200, b"ok"),
        "/c": make_fetch_result(base + "/c", 404, b""),
        "/d": make_fetch_result(base + "/d", 404, b""),
        "/e": make_fetch_result(base + "/e", 404, b""),
    }
    with patch("explorer.discovery.fetch", side_effect=_patched_discover(base, responses)), \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}):
        cfg = FetcherConfig()
        result = discover(base_url=base, cfg=cfg, paths=["/a", "/b", "/c", "/d", "/e"], do_options=False, delay_between=0)
    s = result["stats"]
    assert s["200"] == 2
    assert s["404"] == 3
    assert s["total"] == 5
    print(f"  ✓ test_discover_stats_son_correctas → {s}")


def test_discover_manejando_fetcher_error():
    base = "https://api.test.com"
    from explorer.fetcher import FetcherError

    def fake_fetch(url, **kw):
        raise FetcherError("red caída")

    with patch("explorer.discovery.fetch", side_effect=fake_fetch), \
         patch("explorer.discovery.fingerprint_api", return_value={"server": "test"}):
        cfg = FetcherConfig()
        result = discover(base_url=base, cfg=cfg, paths=["/x"], do_options=False, delay_between=0)
    assert result["stats"]["error"] == 1
    assert result["endpoints"][0]["error"] is not None
    print("  ✓ test_discover_manejando_fetcher_error")


# ─────────────────────────── format_discovery_report ───────────────────────────

def test_format_discovery_report_incluye_path_status():
    result = {
        "base_url": "https://api.test.com",
        "fingerprint": {"server": "nginx", "backend_lang": "nginx", "auth_scheme": "?", "cors": {}},
        "endpoints": [
            {"path": "/users", "full_url": "https://api.test.com/users", "status": 200, "exists": True, "auth_required": False, "size_bytes": 100, "content_type": "application/json"},
        ],
        "stats": {"200": 1, "401": 0, "403": 0, "404": 0, "5xx": 0, "error": 0, "total": 1},
        "elapsed_total_ms": 1234,
    }
    txt = format_discovery_report(result)
    assert "https://api.test.com" in txt
    assert "/users" in txt
    assert "200" in txt
    assert "nginx" in txt
    assert "1234" in txt
    print("  ✓ test_format_discovery_report_incluye_path_status")


# ─────────────────────────── DEFAULT_RECON_PATHS ───────────────────────────

def test_default_recon_paths_incluye_esenciales():
    assert "/swagger.json" in DEFAULT_RECON_PATHS
    assert "/openapi" in DEFAULT_RECON_PATHS
    assert "/health" in DEFAULT_RECON_PATHS
    assert "/users" in DEFAULT_RECON_PATHS
    assert "/actuator" in DEFAULT_RECON_PATHS
    assert "/onboarding" in DEFAULT_RECON_PATHS
    assert "/customers" in DEFAULT_RECON_PATHS
    print(f"  ✓ test_default_recon_paths_incluye_esenciales → {len(DEFAULT_RECON_PATHS)} paths")


if __name__ == "__main__":
    print("=" * 60)
    print("  TESTS: explorer/discovery.py")
    print("=" * 60)
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__} → {type(e).__name__}: {e}")
    print()
    print(f"[done] {len(tests) - failed}/{len(tests)} tests pasaron")
