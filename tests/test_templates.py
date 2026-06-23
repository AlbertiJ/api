"""
test_templates.py — Tests del motor de templates dinámicas.

Cubre:
- Parseo y compilación de plantillas con variables
- Match de URLs reales contra plantillas
- Instanciación con valores concretos
- Iteración de combinaciones (producto cartesiano)
- Validación de errores de input
- Integración con discovery.py (con mock de fetch)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Permite importar el paquete sin instalarlo
sys.path.insert(0, str(Path(__file__).parent.parent))

from explorer.discovery import descubrir_por_template
from explorer.fetcher import FetchResult
from explorer.templates import (
    TemplateError,
    TemplateMatch,
    cargar_slot_values_desde_json,
)


# ─────────────────────── TemplateMatch: parseo y compilación ───────────────────────


def test_template_match_plantilla_simple():
    tm = TemplateMatch("/v1/:modulo/:accion")
    assert tm.vars == ["modulo", "accion"]
    assert tm.regex is not None


def test_template_match_plantilla_sin_variables():
    tm = TemplateMatch("/health")
    assert tm.vars == []
    m = tm.match("/health")
    assert m == {}


def test_template_match_plantilla_tres_variables():
    tm = TemplateMatch("/v1/:modulo/:accion/:recurso")
    assert tm.vars == ["modulo", "accion", "recurso"]


def test_template_match_rechaza_sin_slash_inicial():
    with pytest.raises(TemplateError):
        TemplateMatch("v1/:modulo")


def test_template_match_rechaza_variables_duplicadas():
    with pytest.raises(TemplateError, match="duplicadas"):
        TemplateMatch("/v1/:modulo/:modulo")


def test_template_match_nombres_validos():
    """Variables: letras, dígitos, guión bajo. Deben empezar con letra o _."""
    tm = TemplateMatch("/:user_id/:item_1")
    assert tm.vars == ["user_id", "item_1"]


# ─────────────────────── TemplateMatch.match() ───────────────────────


def test_match_exitoso_con_dos_variables():
    tm = TemplateMatch("/v1/:modulo/:accion")
    m = tm.match("/v1/users/list")
    assert m == {"modulo": "users", "accion": "list"}


def test_match_exitoso_con_tres_variables():
    tm = TemplateMatch("/api/:recurso/:id")
    m = tm.match("/api/users/123")
    assert m == {"recurso": "users", "id": "123"}


def test_match_falla_path_mas_largo():
    tm = TemplateMatch("/v1/:modulo")
    m = tm.match("/v1/users/list")
    assert m is None


def test_match_falla_path_mas_corto():
    tm = TemplateMatch("/v1/:modulo/:accion")
    m = tm.match("/v1/users")
    assert m is None


def test_match_acepta_con_o_sin_slash_final():
    tm = TemplateMatch("/v1/:modulo")
    assert tm.match("/v1/users") == {"modulo": "users"}
    assert tm.match("/v1/users/") == {"modulo": "users"}


def test_match_acepta_path_sin_slash_inicial():
    tm = TemplateMatch("/v1/:modulo")
    m = tm.match("v1/users")
    assert m == {"modulo": "users"}


def test_match_con_caracteres_especiales_en_valor():
    tm = TemplateMatch("/v1/:modulo")
    # El charset permite letras, dígitos, guión, guión bajo, punto, @
    m = tm.match("/v1/user-profile.v2")
    assert m == {"modulo": "user-profile.v2"}


# ─────────────────────── TemplateMatch.instanciar() ───────────────────────


def test_instanciar_con_todos_los_valores():
    tm = TemplateMatch("/v1/:modulo/:accion")
    path = tm.instanciar({"modulo": "users", "accion": "list"})
    assert path == "/v1/users/list"


def test_instanciar_sin_una_variable_falla():
    tm = TemplateMatch("/v1/:modulo/:accion")
    with pytest.raises(TemplateError, match="Faltan valores"):
        tm.instanciar({"modulo": "users"})


def test_instanciar_ignora_valores_sobrantes():
    tm = TemplateMatch("/v1/:modulo")
    # 'accion' no está en la plantilla → se ignora
    path = tm.instanciar({"modulo": "users", "accion": "list"})
    assert path == "/v1/users"


def test_instanciar_rechaza_valor_con_caracteres_invalidos():
    tm = TemplateMatch("/v1/:modulo")
    with pytest.raises(TemplateError, match="Valor inválido"):
        # slash no está en el charset
        tm.instanciar({"modulo": "us/ers"})


# ─────────────────────── TemplateMatch.iterar_combinaciones() ───────────────────────


def test_iterar_combinaciones_producto_cartesiano():
    tm = TemplateMatch("/v1/:modulo/:accion")
    slot_values = {
        "modulo": ["users", "products"],
        "accion": ["list", "get"],
    }
    combos = list(tm.iterar_combinaciones(slot_values))
    assert len(combos) == 4
    assert {"modulo": "users", "accion": "list"} in combos
    assert {"modulo": "users", "accion": "get"} in combos
    assert {"modulo": "products", "accion": "list"} in combos
    assert {"modulo": "products", "accion": "get"} in combos


def test_iterar_combinaciones_sin_valores_usa_string_vacio():
    tm = TemplateMatch("/v1/:modulo")
    combos = list(tm.iterar_combinaciones({}))
    assert combos == [{"modulo": ""}]


def test_iterar_combinaciones_con_tres_variables():
    tm = TemplateMatch("/:a/:b/:c")
    slot_values = {"a": ["1", "2"], "b": ["x"], "c": ["p", "q", "r"]}
    combos = list(tm.iterar_combinaciones(slot_values))
    assert len(combos) == 6  # 2 * 1 * 3


def test_combinaciones_total_coincide_con_iterar():
    tm = TemplateMatch("/v1/:modulo/:accion")
    slot_values = {"modulo": ["a", "b", "c"], "accion": ["1", "2"]}
    total = tm.combinaciones_total(slot_values)
    assert total == 6
    assert len(list(tm.iterar_combinaciones(slot_values))) == total


# ─────────────────────── cargar_slot_values_desde_json ───────────────────────


def test_cargar_slot_values_desde_json_basico():
    data = {"modulo": ["users", "products"], "id": ["1"]}
    out = cargar_slot_values_desde_json(data)
    assert out == {"modulo": ["users", "products"], "id": ["1"]}


def test_cargar_slot_values_string_se_envuelve_en_lista():
    data = {"version": "1"}
    out = cargar_slot_values_desde_json(data)
    assert out == {"version": ["1"]}


def test_cargar_slot_values_tipo_invalido_falla():
    data = {"modulo": 42}
    with pytest.raises(TemplateError):
        cargar_slot_values_desde_json(data)


# ─────────────────────── descubrir_por_template (con mock) ───────────────────────


def _mock_fetch_response(status, body, content_type="application/json"):
    """Helper: crea un FetchResult simulado."""
    raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return FetchResult(
        url="http://test", method="GET", status=status, body=raw,
        content_type=content_type, headers={}, cors={},
        elapsed_ms=10,
    )


def test_descubrir_por_template_separa_match_de_no_match():
    """
    4 combinaciones:
    - /v1/users/list    → 200 JSON con datos → MATCH
    - /v1/users/get     → 200 JSON con datos → MATCH
    - /v1/users/create  → 405 → no match
    - /v1/products/list → 404 → no match
    """
    slot_values = {
        "modulo": ["users", "products"],
        "accion": ["list", "get", "create"],
    }
    responses = {
        "/v1/users/list": _mock_fetch_response(200, {"data": [1, 2, 3]}),
        "/v1/users/get": _mock_fetch_response(200, {"id": 1, "name": "x"}),
        "/v1/users/create": _mock_fetch_response(405, {"error": "method not allowed"}),
        "/v1/products/list": _mock_fetch_response(404, {"error": "not found"}),
        "/v1/products/get": _mock_fetch_response(404, {"error": "not found"}),
        "/v1/products/create": _mock_fetch_response(404, {"error": "not found"}),
    }
    with patch("explorer.discovery.fetch") as mock_fetch:
        def side_effect(url, *args, **kwargs):
            # Extraer path de la URL
            from urllib.parse import urlparse
            path = urlparse(url).path
            return responses.get(path, _mock_fetch_response(404, {"error": "not found"}))
        mock_fetch.side_effect = side_effect
        result = descubrir_por_template(
            base_url="https://api.test.com",
            plantilla="/v1/:modulo/:accion",
            slot_values=slot_values,
        )
    assert len(result["matches"]) == 2
    assert result["matches"][0]["path"] in ("/v1/users/list", "/v1/users/get")
    assert len(result["no_matches"]) >= 3  # 405, 404s
    assert result["stats"]["total"] == 6
    assert result["stats"]["404"] == 3
    assert result["stats"]["405"] == 1


def test_descubrir_por_template_detecta_auth_required():
    """401/403 van a su propia lista, NO a no_matches."""
    slot_values = {"modulo": ["users"], "accion": ["list"]}
    with patch("explorer.discovery.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_fetch_response(401, {"error": "unauthorized"})
        result = descubrir_por_template(
            base_url="https://api.test.com",
            plantilla="/v1/:modulo/:accion",
            slot_values=slot_values,
        )
    assert len(result["auth_required"]) == 1
    assert len(result["matches"]) == 0
    assert len(result["no_matches"]) == 0
    assert result["auth_required"][0]["status"] == 401


def test_descubrir_por_template_rechaza_html_como_match():
    """Si el content-type es text/html, NO es match (aunque sea 200)."""
    slot_values = {"modulo": ["users"], "accion": ["list"]}
    with patch("explorer.discovery.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_fetch_response(
            200, "<html><body>Welcome</body></html>",
            content_type="text/html"
        )
        result = descubrir_por_template(
            base_url="https://api.test.com",
            plantilla="/v1/:modulo/:accion",
            slot_values=slot_values,
        )
    assert len(result["matches"]) == 0
    # 200 que devuelve HTML va a no_matches (no es 404, pero tampoco es match)
    assert len(result["no_matches"]) == 1


def test_descubrir_por_template_con_plantilla_invalida_devuelve_error():
    result = descubrir_por_template(
        base_url="https://api.test.com",
        plantilla="sin_slash_inicial/:modulo",
    )
    assert "error" in result
    assert result["matches"] == []


def test_descubrir_por_template_respeta_max_combinaciones():
    """max_combinaciones=2 trunca la búsqueda."""
    slot_values = {
        "modulo": ["a", "b"],
        "accion": ["1", "2"],
    }
    with patch("explorer.discovery.fetch") as mock_fetch:
        mock_fetch.return_value = _mock_fetch_response(404, {"err": "nf"})
        result = descubrir_por_template(
            base_url="https://api.test.com",
            plantilla="/v1/:modulo/:accion",
            slot_values=slot_values,
            max_combinaciones=2,
        )
    assert result["stats"]["total"] == 2


def test_descubrir_por_template_maneja_fetcher_error():
    """Si el fetcher levanta FetcherError, va a no_matches con status=0."""
    from explorer.fetcher import FetcherError
    slot_values = {"modulo": ["x"], "accion": ["y"]}
    with patch("explorer.discovery.fetch") as mock_fetch:
        mock_fetch.side_effect = FetcherError("connection refused")
        result = descubrir_por_template(
            base_url="https://api.test.com",
            plantilla="/v1/:modulo/:accion",
            slot_values=slot_values,
        )
    assert len(result["no_matches"]) == 1
    assert result["no_matches"][0]["status"] == 0
    assert "connection refused" in result["no_matches"][0]["error"]


# ─────────────────────── Integración con plantillas.json ───────────────────────


def test_cargar_plantillas_json_existe():
    """El JSON de reglas/plantillas.json existe y tiene la estructura esperada."""
    ruta = Path(__file__).parent.parent / "reglas" / "plantillas.json"
    assert ruta.exists(), f"Falta {ruta}"
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "plantillas_basicas" in data
    assert "valores_default" in data
    assert "criterios_match" in data
    assert isinstance(data["plantillas_basicas"], list)
    assert len(data["plantillas_basicas"]) >= 5
    # Las plantillas tienen formato :variable
    for p in data["plantillas_basicas"]:
        assert p.startswith("/"), f"Plantilla mal formada: {p}"
