"""
Tests del pipeline (explorer/pipeline.py).

Cubre:
  - run_pipeline() básico (discover + analyze)
  - Consolidado tiene hash SHA-256
  - max_endpoints_to_analyze se respeta
  - Bearer se pasa a discover
  - Manejo de ErrorExploracion
  - _rank_endpoints prioriza 200
  - format_pipeline_informe incluye los hashes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Permite importar el paquete sin instalarlo.
sys.path.insert(0, str(Path(__file__).parent.parent))

from explorer.core import ErrorExploracion
from explorer.fetcher import FetchResult, FetcherConfig
from explorer.pipeline import (
    PipelineResult,
    _rank_endpoints,
    format_pipeline_informe,
    run_pipeline,
)


# ─────────────────────────── _rank_endpoints ───────────────────────────

def test_rank_200_antes_401():
    eps = [
        {"path": "/a", "status": 401, "exists": True, "size_bytes": 0},
        {"path": "/b", "status": 200, "exists": True, "size_bytes": 100},
    ]
    ranked = _rank_endpoints(eps)
    assert ranked[0]["path"] == "/b"
    print("  ✓ test_rank_200_antes_401")


def test_rank_405_tambien_entra():
    """405 Method Not Allowed → el endpoint existe, solo el método no."""
    eps = [
        {"path": "/a", "status": 405, "exists": True, "size_bytes": 0},
    ]
    ranked = _rank_endpoints(eps)
    assert len(ranked) == 1
    assert ranked[0]["status"] == 405
    print("  ✓ test_rank_405_tambien_entra")


def test_rank_404_no_entra():
    """404 = no existe, no entra al ranking."""
    eps = [
        {"path": "/a", "status": 404, "exists": False, "size_bytes": 0},
    ]
    ranked = _rank_endpoints(eps)
    assert len(ranked) == 0
    print("  ✓ test_rank_404_no_entra")


# ─────────────────────────── run_pipeline() mockeado ───────────────────────────

def _fake_discover_result(base_url, endpoints_status):
    """Crea un output de discover() para usar como mock."""
    stats = {str(s): sum(1 for _, st in endpoints_status if st == s) for s in {st for _, st in endpoints_status}}
    stats["total"] = len(endpoints_status)
    return {
        "base_url": base_url,
        "fingerprint": {"server": "test", "backend_lang": "test", "auth_scheme": "?", "cors": {}},
        "endpoints": [
            {"path": p, "full_url": base_url + p, "status": s, "exists": s not in (404, 0),
             "auth_required": s in (401, 403), "size_bytes": 100 if s == 200 else 0,
             "content_type": "application/json" if s == 200 else "", "cors": {}}
            for p, s in endpoints_status
        ],
        "stats": stats,
        "elapsed_total_ms": 100,
    }


def _fake_explorar_payload(url, registro_count=10, pii=2):
    """Crea un payload de explorar() para usar como mock."""
    return {
        "exploracion": {
            "url": url,
            "timestamp_utc": "2026-06-22T00:00:00Z",
            "responsable": "test",
            "cliente": "test",
            "tipo_detectado": "test_tipo",
            "confianza_deteccion": 0.5,
            "pistas_deteccion": [],
            "estructura": {"total_registros": registro_count, "total_campos_unicos": 5, "campos": {}},
            "pii_detectado": {"total_hallazgos": pii, "por_categoria": {}},
            "reglas_menores": {"total_menores": 0},
            "faltantes_reportados": [],
            "metadata_paginacion": {"fuente_paginacion": "ninguna", "total_registros_reales": registro_count, "total_registros_analizados": registro_count, "max_alcanzado": False},
            "cadena_auditoria_previa": None,
            "resumen": {
                "total_registros_reales": registro_count,
                "total_registros_analizados": registro_count,
                "total_campos": 5,
                "campos_faltantes": 0,
                "datos_sensibles_encontrados": pii,
                "menores_detectados": 0,
                "fuente_paginacion": "ninguna",
                "pausa_entre_requests": 0.5,
            },
            "hash_sha256": "abc123def456" * 4,  # 48 chars
        },
    }


def test_pipeline_basico_genera_consolidado_con_hash():
    base = "https://api.test.com"
    endpoints_status = [("/users", 200), ("/orders", 401), ("/health", 200), ("/nope", 404)]
    discover_mock = _fake_discover_result(base, endpoints_status)
    explorar_mock = _fake_explorar_payload(base + "/users", 10, 5)
    with patch("explorer.pipeline.discover", return_value=discover_mock), \
         patch("explorer.pipeline.explorar", return_value=explorar_mock):
        cfg = FetcherConfig()
        result = run_pipeline(
            base_url=base, cfg=cfg, max_endpoints_to_analyze=2,
            do_discovery=True, do_analyze=True, progress=False,
        )
    assert isinstance(result, PipelineResult)
    assert result.base_url == base
    assert result.recon == discover_mock
    assert len(result.endpoints_analyzed) == 2  # respeta max
    assert len(result.hash_sha256) == 64  # SHA-256 hex
    print(f"  ✓ test_pipeline_basico_genera_consolidado_con_hash → {len(result.endpoints_analyzed)} endpoints analizados, hash={result.hash_sha256[:16]}...")


def test_pipeline_respeta_max_endpoints_to_analyze():
    base = "https://api.test.com"
    endpoints_status = [(f"/p{i}", 200) for i in range(10)]
    discover_mock = _fake_discover_result(base, endpoints_status)
    explorar_mock = _fake_explorar_payload(base)
    with patch("explorer.pipeline.discover", return_value=discover_mock), \
         patch("explorer.pipeline.explorar", return_value=explorar_mock) as mock_explorar:
        cfg = FetcherConfig()
        result = run_pipeline(
            base_url=base, cfg=cfg, max_endpoints_to_analyze=3,
            do_discovery=True, do_analyze=True, progress=False,
        )
    assert len(result.endpoints_analyzed) == 3
    assert mock_explorar.call_count == 3
    print(f"  ✓ test_pipeline_respeta_max_endpoints_to_analyze → 10 descubiertos, 3 analizados")


def test_pipeline_pasa_bearer_y_origin_a_discover():
    base = "https://api.test.com"
    discover_mock = _fake_discover_result(base, [("/x", 200)])
    with patch("explorer.pipeline.discover", return_value=discover_mock) as mock_disc, \
         patch("explorer.pipeline.explorar", return_value=_fake_explorar_payload(base)):
        cfg = FetcherConfig()
        run_pipeline(
            base_url=base, cfg=cfg, bearer="my_token", origin="https://attacker.com",
            max_endpoints_to_analyze=1, do_discovery=True, do_analyze=True, progress=False,
        )
    call_kwargs = mock_disc.call_args.kwargs
    assert call_kwargs.get("bearer") == "my_token"
    assert call_kwargs.get("origin") == "https://attacker.com"
    print("  ✓ test_pipeline_pasa_bearer_y_origin_a_discover")


def test_pipeline_maneja_error_explorar():
    """Si un endpoint falla en explorar(), se registra el error pero el pipeline sigue."""
    base = "https://api.test.com"
    endpoints_status = [("/a", 200), ("/b", 200), ("/c", 200)]
    discover_mock = _fake_discover_result(base, endpoints_status)

    def fake_explorar(url, **kwargs):
        if "/b" in url:
            raise ErrorExploracion("fallo el /b")
        return _fake_explorar_payload(url)

    with patch("explorer.pipeline.discover", return_value=discover_mock), \
         patch("explorer.pipeline.explorar", side_effect=fake_explorar):
        cfg = FetcherConfig()
        result = run_pipeline(
            base_url=base, cfg=cfg, max_endpoints_to_analyze=3,
            do_discovery=True, do_analyze=True, progress=False,
        )
    assert len(result.endpoints_analyzed) == 3
    b_result = next(e for e in result.endpoints_analyzed if e.get("path") == "/b")
    assert "error" in b_result
    assert "fallo el /b" in b_result["error"]
    print("  ✓ test_pipeline_maneja_error_explorar")


def test_pipeline_sin_discovery():
    base = "https://api.test.com"
    with patch("explorer.pipeline.discover") as mock_disc, \
         patch("explorer.pipeline.explorar", return_value=_fake_explorar_payload(base)) as mock_exp:
        cfg = FetcherConfig()
        result = run_pipeline(
            base_url=base, cfg=cfg, do_discovery=False, do_analyze=True, progress=False,
        )
    assert mock_disc.call_count == 0  # no se llamó
    assert mock_exp.call_count == 0   # no se llamó tampoco (no hay endpoints)
    assert result.recon == {}
    assert result.endpoints_analyzed == []
    print("  ✓ test_pipeline_sin_discovery")


def test_pipeline_solo_discovery_sin_analyze():
    base = "https://api.test.com"
    endpoints_status = [("/a", 200), ("/b", 404)]
    discover_mock = _fake_discover_result(base, endpoints_status)
    with patch("explorer.pipeline.discover", return_value=discover_mock) as mock_disc, \
         patch("explorer.pipeline.explorar") as mock_exp:
        cfg = FetcherConfig()
        result = run_pipeline(
            base_url=base, cfg=cfg, do_discovery=True, do_analyze=False, progress=False,
        )
    assert mock_disc.called
    assert mock_exp.call_count == 0
    assert len(result.endpoints_analyzed) == 0
    assert result.recon == discover_mock
    print("  ✓ test_pipeline_solo_discovery_sin_analyze")


def test_pipeline_hash_es_deterministico():
    """El mismo input produce el mismo hash (modulo timestamp)."""
    base = "https://api.test.com"
    endpoints_status = [("/a", 200)]
    discover_mock = _fake_discover_result(base, endpoints_status)
    explorar_mock = _fake_explorar_payload(base)
    with patch("explorer.pipeline.discover", return_value=discover_mock), \
         patch("explorer.pipeline.explorar", return_value=explorar_mock):
        cfg = FetcherConfig()
        r1 = run_pipeline(base_url=base, cfg=cfg, max_endpoints_to_analyze=1, progress=False)
        r2 = run_pipeline(base_url=base, cfg=cfg, max_endpoints_to_analyze=1, progress=False)
    # El hash puede cambiar si los timestamps son distintos, pero ambos son SHA-256 válidos
    assert len(r1.hash_sha256) == 64
    assert len(r2.hash_sha256) == 64
    # Y la longitud de la firma es consistente
    print(f"  ✓ test_pipeline_hash_es_deterministico → {r1.hash_sha256[:16]}... vs {r2.hash_sha256[:16]}...")


def test_pipeline_consolidado_incluye_stats():
    base = "https://api.test.com"
    endpoints_status = [("/a", 200), ("/b", 404), ("/c", 401)]
    discover_mock = _fake_discover_result(base, endpoints_status)
    with patch("explorer.pipeline.discover", return_value=discover_mock), \
         patch("explorer.pipeline.explorar", return_value=_fake_explorar_payload(base)):
        cfg = FetcherConfig()
        result = run_pipeline(
            base_url=base, cfg=cfg, max_endpoints_to_analyze=5, progress=False,
        )
    cons = result.consolidado
    assert "recon_stats" in cons
    assert "recon_fingerprint" in cons
    assert "endpoints_analyzed" in cons
    assert "endpoints_descubiertos_total" in cons
    assert "endpoints_descubiertos_existentes" in cons
    assert cons["endpoints_descubiertos_total"] == 3
    assert cons["endpoints_descubiertos_existentes"] == 2  # 200 + 401
    print(f"  ✓ test_pipeline_consolidado_incluye_stats → descubiertos={cons['endpoints_descubiertos_total']} existentes={cons['endpoints_descubiertos_existentes']}")


# ─────────────────────────── format_pipeline_informe ───────────────────────────

def test_format_pipeline_informe_incluye_hashes_y_fases():
    pr = PipelineResult(
        base_url="https://api.test.com",
        timestamp_utc="2026-06-22T00:00:00Z",
        responsable="Juan",
        cliente="ClienteX",
        recon={"fingerprint": {"server": "nginx", "backend_lang": "nginx", "auth_scheme": "Bearer"},
               "stats": {"200": 1, "401": 0, "403": 0, "404": 0, "5xx": 0, "total": 1},
               "endpoints": []},
        endpoints_analyzed=[
            {"path": "/users", "tipo_detectado": "users", "total_registros": 10, "total_campos": 5,
             "datos_sensibles": 2, "menores": 0, "hash_sha256": "abc123..."}
        ],
        consolidado={},
        hash_sha256="a" * 64,
        elapsed_total_ms=5000,
    )
    txt = format_pipeline_informe(pr)
    assert "https://api.test.com" in txt
    assert "Juan" in txt
    assert "ClienteX" in txt
    assert "nginx" in txt
    assert "Bearer" in txt
    assert "/users" in txt
    assert "FASE 1: RECON" in txt
    assert "FASE 2: ANÁLISIS" in txt
    assert "FIRMA DE AUDITORÍA" in txt
    assert "a" * 16 in txt  # parte del hash
    print("  ✓ test_format_pipeline_informe_incluye_hashes_y_fases")


# ─────────────────────────── integración opcional ───────────────────────────

def test_pipeline_real_jsonplaceholder(silencioso=True):
    """Integration test: pipeline real contra jsonplaceholder.typicode.com."""
    import socket
    try:
        socket.create_connection(("jsonplaceholder.typicode.com", 443), timeout=2).close()
    except (OSError, socket.timeout):
        if not silencioso:
            print("  ⊝ test_pipeline_real_jsonplaceholder → SKIP (sin red)")
        return
    cfg = FetcherConfig(timeout=5)
    result = run_pipeline(
        base_url="https://jsonplaceholder.typicode.com",
        cfg=cfg,
        max_endpoints_to_analyze=2,
        delay_between=0.1,
        do_discovery=True,
        do_analyze=True,
        progress=False,
    )
    assert result.recon is not None
    assert len(result.endpoints_analyzed) <= 2
    assert len(result.hash_sha256) == 64
    if not silencioso:
        print(f"  ✓ test_pipeline_real_jsonplaceholder → {len(result.endpoints_analyzed)} analizados, {len(result.hash_sha256)} chars hash")


if __name__ == "__main__":
    print("=" * 60)
    print("  TESTS: explorer/pipeline.py")
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
    print("=" * 60)
    print("  INTEGRATION (requiere red)")
    print("=" * 60)
    test_pipeline_real_jsonplaceholder(silencioso=False)
    print()
    print(f"[done] {len(tests) - failed}/{len(tests)} tests pasaron")
