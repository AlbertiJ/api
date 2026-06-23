"""
test_migracion.py — Tests del MOD-9: generación de FastAPI/Pydantic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from explorer.migracion import (
    _es_pii,
    _snake_to_camel,
    _snake_to_pascal,
    _tipo_python_desde_inferencia,
    analizar_a_fastapi,
    generar_app_fastapi,
    generar_endpoint,
    generar_modelo_pydantic,
)


# ─────────────────────── Helpers ───────────────────────


def test_snake_to_camel_basico():
    assert _snake_to_camel("customer_id") == "customerId"
    assert _snake_to_camel("dni") == "dni"
    assert _snake_to_camel("first_name") == "firstName"


def test_snake_to_pascal_basico():
    assert _snake_to_pascal("customer_lookup") == "CustomerLookup"
    assert _snake_to_pascal("dni") == "Dni"


def test_es_pii_detecta_email():
    es, tipo = _es_pii("email")
    assert es is True
    assert tipo == "email"


def test_es_pii_detecta_dni():
    es, tipo = _es_pii("dni")
    assert es is True
    assert tipo == "dni"


def test_es_pii_detecta_telefono():
    es, tipo = _es_pii("phone_number")
    assert es is True
    assert tipo == "telefono"


def test_es_pii_detecta_nombre():
    es, _ = _es_pii("first_name")
    assert es is True


def test_es_pii_rechaza_id_generico():
    es, _ = _es_pii("order_id")
    assert es is False


def test_tipo_python_desde_inferencia():
    assert _tipo_python_desde_inferencia("string") == "str"
    assert _tipo_python_desde_inferencia("int") == "int"
    assert _tipo_python_desde_inferencia("email") == "EmailStr"
    assert _tipo_python_desde_inferencia("date") == "datetime"
    assert _tipo_python_desde_inferencia("desconocido") == "Any"


# ─────────────────────── generar_modelo_pydantic ───────────────────────


def test_generar_modelo_pydantic_basico():
    campos = [
        {"nombre": "dni", "tipo": "string", "tipo_py": "str"},
        {"nombre": "email", "tipo": "email", "tipo_py": "EmailStr", "pii": "email"},
    ]
    out = generar_modelo_pydantic("CustomerRequest", campos)
    assert "class CustomerRequest(BaseModel):" in out
    assert "dni: str" in out
    assert "email: EmailStr" in out
    assert "PII" in out  # comentario de compliance
    # Nota: el import EmailStr se genera en generar_app_fastapi, no acá


def test_generar_modelo_pydantic_vacio():
    out = generar_modelo_pydantic("Empty", [])
    assert "class Empty(BaseModel):" in out
    assert "pass" in out


def test_generar_modelo_pydantic_sin_pii_no_agrega_comentario():
    campos = [{"nombre": "id", "tipo": "int", "tipo_py": "int"}]
    out = generar_modelo_pydantic("Order", campos)
    assert "class Order(BaseModel):" in out
    assert "PII" not in out


def test_generar_modelo_pydantic_campos_opcionales():
    campos = [
        {"nombre": "a", "tipo": "str", "tipo_py": "str", "opcional": True},
        {"nombre": "b", "tipo": "str", "tipo_py": "str", "opcional": False},
    ]
    out = generar_modelo_pydantic("Mixed", campos)
    # Opcional: 'a: str = Field(None, ...)'. No opcional: 'b: str = Field(...)'
    assert "a: str = Field(" in out and "None" in out
    assert "b: str = Field(" in out and "..." in out
    # El import de Field se genera en generar_app_fastapi
    assert "from pydantic import Field" in out or "Field" in out


# ─────────────────────── generar_endpoint ───────────────────────


def test_generar_endpoint_get():
    out = generar_endpoint("/v1/customers", "GET", response_model="Customer")
    assert '@app.get("/v1/customers", response_model=Customer)' in out
    assert "async def endpoint()" in out
    assert "HTTPException" in out


def test_generar_endpoint_post():
    out = generar_endpoint("/v1/customers", "POST", request_model="CustomerIn", response_model="CustomerOut")
    assert "async def endpoint(data: CustomerIn) -> CustomerOut:" in out


# ─────────────────────── generar_app_fastapi ───────────────────────


def test_generar_app_fastapi_completa():
    modelo_req = generar_modelo_pydantic("Req", [{"nombre": "x", "tipo": "str", "tipo_py": "str"}])
    modelo_res = generar_modelo_pydantic("Res", [{"nombre": "y", "tipo": "int", "tipo_py": "int"}])
    endpoint = generar_endpoint("/v1/x", "POST", "Req", "Res")
    out = generar_app_fastapi(
        titulo="Test API",
        version="1.0.0",
        modelos=[("Req", modelo_req), ("Res", modelo_res)],
        endpoints=[{"path": "/v1/x", "metodo": "POST", "request_model": "Req", "response_model": "Res"}],
    )
    assert "app = FastAPI(" in out
    assert 'title="Test API"' in out
    assert 'version="1.0.0"' in out
    assert "class Req(BaseModel):" in out
    assert "class Res(BaseModel):" in out
    assert '@app.post("/v1/x"' in out


# ─────────────────────── analizar_a_fastapi (función principal) ───────────────────────


def test_analizar_a_fastapi_genera_codigo_valido():
    payload = {
        "url": "https://api.cliente.com/v1/onboarding/resolvecustomers",
        "estructura": {
            "campos": [
                {"nombre": "dni", "tipo": "string"},
                {"nombre": "email", "tipo": "email"},
                {"nombre": "customer_id", "tipo": "string"},
            ]
        },
        "pii_detectado": {
            "hallazgos": [
                {"campo": "dni", "tipo_pii": "dni", "nivel_sensibilidad": "alto"},
                {"campo": "email", "tipo_pii": "email", "nivel_sensibilidad": "alto"},
            ]
        },
    }
    codigo = analizar_a_fastapi(payload, titulo="API Migrada", version="2.0.0")
    assert "app = FastAPI(" in codigo
    assert 'title="API Migrada"' in codigo
    assert 'version="2.0.0"' in codigo
    # Los campos están
    assert "dni" in codigo
    assert "email" in codigo
    assert "customer_id" in codigo
    # Email usa EmailStr
    assert "EmailStr" in codigo
    # El path se infiere
    assert "/v1/onboarding/resolvecustomers" in codigo
    # Marca PII
    assert "PII" in codigo
    # Tiene endpoint POST y GET
    assert '@app.post' in codigo
    assert '@app.get' in codigo


def test_analizar_a_fastapi_sin_pii():
    payload = {
        "url": "https://api.cliente.com/products",
        "estructura": {
            "campos": [
                {"nombre": "product_id", "tipo": "int"},
                {"nombre": "title", "tipo": "string"},  # no matchea patrones PII
            ]
        },
        "pii_detectado": {"hallazgos": []},
    }
    codigo = analizar_a_fastapi(payload)
    assert "product_id" in codigo
    assert "title" in codigo
    assert "PII" not in codigo  # no debe haber comentario de PII


def test_analizar_a_fastapi_con_muestra_de_registros():
    """Si no hay 'campos' explícitos, se infieren de registros_muestra[0]."""
    payload = {
        "url": "https://api.test.com/x",
        "estructura": {
            "registros_muestra": [
                {"id": 1, "name": "Test", "active": True},
            ],
        },
        "pii_detectado": {"hallazgos": []},
    }
    codigo = analizar_a_fastapi(payload)
    assert "id" in codigo
    assert "name" in codigo
    assert "active" in codigo
