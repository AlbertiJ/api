"""
test_osint.py — Tests del módulo OSINT.

Mockea las llamadas a urlscan.io y GitHub para no depender de internet
ni de rate-limits reales.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from explorer.fetcher import FetchResult
from explorer.osint import (
    OsintHit,
    format_osint_report,
    github_search,
    osint_search,
    urlscan_search,
)


def _mock_response(status, body, content_type="application/json"):
    """
    Simula una respuesta del fetcher. Si el body es dict/list, lo deja
    como tal (el fetcher real también lo parsea). Si es str/bytes, lo
    pasa crudo.
    """
    if isinstance(body, (dict, list)):
        # Lo pasamos como dict parseado (lo que el fetcher real haría)
        return FetchResult(
            url="http://test", method="GET", status=status, body=body,
            content_type=content_type, headers={}, cors={}, elapsed_ms=10,
        )
    raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return FetchResult(
        url="http://test", method="GET", status=status, body=raw,
        content_type=content_type, headers={}, cors={}, elapsed_ms=10,
    )


# ─────────────────────── urlscan_search ───────────────────────


def test_urlscan_search_devuelve_lista_de_hits():
    body = {
        "results": [
            {
                "task": {"uuid": "abc123"},
                "page": {
                    "domain": "ejemplo.com.ar",
                    "title": "Login",
                    "url": "https://ejemplo.com.ar/login",
                    "country": "AR",
                    "asn": "AS12345",
                },
                "time": "2026-06-01T00:00:00Z",
            },
            {
                "task": {"uuid": "def456"},
                "page": {
                    "domain": "otro.com",
                    "title": "Home",
                    "url": "https://otro.com/",
                    "country": "US",
                    "asn": "AS99999",
                },
                "time": "2026-06-02T00:00:00Z",
            },
        ]
    }
    with patch("explorer.osint.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_response(200, body)
        hits = urlscan_search("/v1/test*")
    assert len(hits) == 2
    assert hits[0].fuente == "urlscan"
    assert hits[0].dominio == "ejemplo.com.ar"
    assert hits[0].extra["country"] == "AR"
    assert hits[1].dominio == "otro.com"


def test_urlscan_search_maneja_error_de_red():
    from explorer.fetcher import FetcherError
    with patch("explorer.osint.fetch") as mock_fetch:
        mock_fetch.side_effect = FetcherError("timeout")
        hits = urlscan_search("/v1/test*")
    assert len(hits) == 1
    assert "ERROR" in hits[0].titulo
    assert "timeout" in hits[0].extra["error"]


def test_urlscan_search_maneja_status_no_200():
    with patch("explorer.osint.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_response(429, {"error": "rate limit"})
        hits = urlscan_search("/v1/test*")
    assert len(hits) == 1
    assert "429" in hits[0].titulo


def test_urlscan_search_maneja_body_no_json():
    with patch("explorer.osint.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_response(
            200, "<html>not json</html>", content_type="text/html"
        )
        hits = urlscan_search("/v1/test*")
    assert len(hits) == 1
    assert "JSON" in hits[0].titulo


# ─────────────────────── github_search ───────────────────────


def test_github_search_devuelve_lista_de_hits():
    body = {
        "items": [
            {
                "name": "api-client.js",
                "html_url": "https://github.com/foo/bar/blob/main/api-client.js",
                "path": "src/api-client.js",
                "repository": {
                    "full_name": "foo/bar",
                    "html_url": "https://github.com/foo/bar",
                    "language": "JavaScript",
                    "stargazers_count": 42,
                },
            },
        ]
    }
    with patch("explorer.osint.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_response(200, body)
        hits = github_search("/v1/onboarding", languages=["javascript"])
    assert len(hits) == 1
    assert hits[0].fuente == "github"
    assert hits[0].extra["lenguaje"] == "JavaScript"
    assert hits[0].extra["stars"] == 42
    assert hits[0].extra["repo"] == "foo/bar"


def test_github_search_maneja_rate_limit():
    with patch("explorer.osint.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_response(
            403, {"message": "API rate limit exceeded"}
        )
        hits = github_search("/v1/test")
    assert len(hits) == 1
    assert "Rate limit" in hits[0].titulo


def test_github_search_agrega_filtro_de_lenguajes():
    """Si languages está presente, se agrega 'language:X OR language:Y'."""
    with patch("explorer.osint.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_response(200, {"items": []})
        github_search("/v1/test", languages=["javascript", "typescript"])
        # Verificar que la URL incluyó el filtro
        called_url = mock_fetch.call_args[0][0]
        assert "language%3Ajavascript" in called_url or "language:javascript" in called_url
        assert "language%3Atypescript" in called_url or "language:typescript" in called_url


# ─────────────────────── osint_search (orquestador) ───────────────────────


def test_osint_search_consolida_ambas_fuentes():
    with patch("explorer.osint.urlscan_search") as mock_us, \
         patch("explorer.osint.github_search") as mock_gh:
        mock_us.return_value = [OsintHit(fuente="urlscan", titulo="x", url="https://a.com", dominio="a.com")]
        mock_gh.return_value = [OsintHit(fuente="github", titulo="y", url="https://github.com/x/y", dominio="github.com")]
        result = osint_search("/v1/test")
    assert result["total_hits"] == 2
    assert result["total_dominios_unicos"] == 2
    assert "a.com" in result["dominios_unicos"]
    assert "github.com" in result["dominios_unicos"]


def test_osint_search_deduplica_dominios():
    with patch("explorer.osint.urlscan_search") as mock_us, \
         patch("explorer.osint.github_search") as mock_gh:
        mock_us.return_value = [
            OsintHit(fuente="urlscan", titulo="x1", url="https://a.com/1", dominio="a.com"),
            OsintHit(fuente="urlscan", titulo="x2", url="https://a.com/2", dominio="a.com"),
        ]
        mock_gh.return_value = [
            OsintHit(fuente="github", titulo="y1", url="https://github.com/x/y", dominio="github.com"),
        ]
        result = osint_search("/v1/test")
    assert result["total_hits"] == 3
    assert result["total_dominios_unicos"] == 2  # a.com + github.com


def test_osint_search_solo_urlscan():
    with patch("explorer.osint.urlscan_search") as mock_us, \
         patch("explorer.osint.github_search") as mock_gh:
        mock_us.return_value = [OsintHit(fuente="urlscan", titulo="x", url="u", dominio="a.com")]
        mock_gh.return_value = []
        result = osint_search("/v1/test", fuentes=["urlscan"])
    assert mock_gh.call_count == 0
    assert "github" not in result["por_fuente"]


def test_osint_search_registra_errores_sin_caer():
    with patch("explorer.osint.urlscan_search") as mock_us, \
         patch("explorer.osint.github_search") as mock_gh:
        mock_us.side_effect = Exception("boom")
        mock_gh.return_value = [OsintHit(fuente="github", titulo="x", url="u", dominio="a.com")]
        result = osint_search("/v1/test")
    assert len(result["errores"]) == 1
    assert result["errores"][0]["fuente"] == "urlscan"
    assert result["total_hits"] == 1  # solo github


def test_format_osint_report_incluye_query_y_totales():
    result = {
        "query": "/v1/test",
        "hits": [],
        "por_fuente": {"urlscan": []},
        "dominios_unicos": [],
        "errores": [],
        "total_hits": 0,
        "total_dominios_unicos": 0,
    }
    out = format_osint_report(result)
    assert "/v1/test" in out
    assert "Total hits" in out
    assert "urlscan" in out
