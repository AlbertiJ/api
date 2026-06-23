"""
migracion.py — MOD-9 premium: generación de esqueleto FastAPI/Pydantic
desde un JSON de análisis de api-explorer.

Toma un payload de análisis (estructura inferida por `core.py:explorar()`)
y genera código Python moderno que:
  - Define los modelos Pydantic basados en los campos detectados
  - Define los endpoints REST inferidos del path y método
  - Marca los campos PII con comentarios de compliance
  - Aplica validación de tipos (int, float, str, bool, date, email)

Caso de uso: el cliente te da un JSON con la estructura de su API legacy
y vos le devolvés un esqueleto FastAPI listo para completar la lógica
de negocio.

Inspirado en la sección 5 del prompt técnico compartido por el operador
("Mapeo Automático a Nueva Arquitectura FastAPI + Pydantic").
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────── Mapeo de tipos ───────────────────────
# Tabla simple: tipo inferido en api-explorer → tipo Python/Pydantic
TYPE_MAP_PYTHON = {
    "string": "str",
    "str": "str",
    "int": "int",
    "integer": "int",
    "float": "float",
    "number": "float",
    "bool": "bool",
    "boolean": "bool",
    "null": "Optional[str]",
    "date": "datetime",
    "datetime": "datetime",
    "email": "EmailStr",
    "object": "Dict[str, Any]",
    "array": "List[Any]",
    "list": "List[Any]",
}

# Patrones para detectar tipos por nombre de campo
PII_PATTERNS = {
    "email": r"mail|correo|e_mail",
    "telefono": r"tel|phone|celular|movil",
    "dni": r"dni|documento|cuil|cuit",
    "fecha_nac": r"fecha_nac|nacimiento|birth_date|birthdate",
    "nombre": r"^nombre$|^first_name$|^last_name$|^full_name$|^given_name$|^family_name$|apellido",
    "direccion": r"direccion|address|calle|street",
    "pass": r"password|^pass$|clave|secret",
}

# PII flags
PII_FIELDS = {"dni", "email", "telefono", "fecha_nac", "direccion", "pass"}


# ─────────────────────── Helpers ───────────────────────


def _snake_to_camel(name: str) -> str:
    """snake_case → camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _snake_to_pascal(name: str) -> str:
    """snake_case → PascalCase."""
    return "".join(p.title() for p in name.split("_"))


def _es_pii(nombre_campo: str) -> Tuple[bool, Optional[str]]:
    """Detecta si un campo es PII según su nombre. Devuelve (es_pii, tipo_pii)."""
    lower = nombre_campo.lower()
    for tipo_pii, patron in PII_PATTERNS.items():
        if re.search(patron, lower):
            return True, tipo_pii
    return False, None


def _tipo_python_desde_inferencia(tipo: str) -> str:
    """Traduce un tipo inferido por api-explorer a un tipo Python/Pydantic."""
    return TYPE_MAP_PYTHON.get(tipo.lower(), "Any")


# ─────────────────────── Generación ───────────────────────


def generar_modelo_pydantic(
    nombre: str,
    campos: List[Dict[str, Any]],
    indent: str = "    ",
) -> str:
    """
    Genera una clase Pydantic BaseModel a partir de una lista de campos.

    Args:
        nombre: nombre de la clase en PascalCase (ej: "CustomerLookupRequest").
        campos: lista de dicts con keys: nombre, tipo, opcional, pii, descripcion.
        indent: prefijo de indentación.

    Returns:
        Código Python como string.
    """
    lines = []
    lines.append(f"class {nombre}(BaseModel):")
    if not campos:
        lines.append(f"{indent}pass")
        return "\n".join(lines)

    # Detectar si necesita imports especiales
    necesita_email = any(c.get("pii") == "email" for c in campos)
    necesita_datetime = any(c.get("tipo") in ("date", "datetime") for c in campos)
    necesita_optional = any(c.get("opcional") for c in campos)
    necesita_field = any(c.get("descripcion") or c.get("constraints") for c in campos)

    imports_extra = []
    if necesita_email:
        imports_extra.append("from pydantic import EmailStr")
    if necesita_datetime:
        imports_extra.append("from datetime import datetime")
    if necesita_optional:
        imports_extra.append("from typing import Optional")
    if necesita_field:
        imports_extra.append("from pydantic import Field")

    # Comentario PII al inicio si hay campos PII
    pii_campos = [c["nombre"] for c in campos if c.get("pii")]
    if pii_campos:
        lines.append(f"{indent}# ⚠ Contiene datos personales sensibles (PII): {', '.join(pii_campos)}")
        lines.append(f"{indent}# Compliance: GDPR Art. 4, Ley 25.326 (Argentina)")
        lines.append("")

    for c in campos:
        nombre_campo = c["nombre"]
        tipo_py = c.get("tipo_py", "Any")
        opcional = c.get("opcional", False)
        pii = c.get("pii")
        descripcion = c.get("descripcion", "")
        constraints = c.get("constraints", {})

        # Construir el default
        field_args = []
        if pii == "email":
            field_args.append(f"description=\"Email validado\"")
        elif pii:
            field_args.append(f"description=\"PII ({pii})\"")
        elif descripcion:
            field_args.append(f"description=\"{descripcion}\"")

        if not opcional:
            field_args.insert(0, "...")
        else:
            field_args.insert(0, "None")

        if constraints:
            for k, v in constraints.items():
                if k in ("min_length", "max_length", "ge", "le", "gt", "lt", "pattern"):
                    field_args.append(f"{k}={v!r}" if isinstance(v, str) else f"{k}={v}")

        # Nombre del campo en snake_case (Pydantic aliasing lo pasa a camel si se quiere)
        if field_args:
            lines.append(f"{indent}{nombre_campo}: {tipo_py} = Field({', '.join(field_args)})")
        else:
            lines.append(f"{indent}{nombre_campo}: {tipo_py}")

    return "\n".join(lines)


def generar_endpoint(
    path: str,
    metodo: str,
    request_model: Optional[str] = None,
    response_model: Optional[str] = None,
    indent: str = "    ",
) -> str:
    """
    Genera un decorador + función para un endpoint FastAPI.
    """
    decorator = f'@app.{metodo.lower()}("{path}", response_model={response_model or "Dict"})'
    if metodo.upper() in ("POST", "PUT", "PATCH"):
        signature = f"async def endpoint(data: {request_model or 'Dict'}) -> {response_model or 'Dict'}:"
    else:
        signature = f"async def endpoint() -> {response_model or 'Dict'}:"

    body = f'''{decorator}
{indent}{signature}
{indent}    \"\"\"
{indent}    Endpoint migrado automáticamente.
{indent}    TODO: implementar la lógica de negocio.
{indent}    \"\"\"
{indent}    raise HTTPException(status_code=501, detail="No implementado")
'''
    return body


def generar_app_fastapi(
    titulo: str,
    version: str,
    modelos: List[Tuple[str, str]],     # [(nombre_clase, codigo_modelo), ...]
    endpoints: List[Dict[str, str]],    # [{path, metodo, request_model, response_model}, ...]
    indent: str = "    ",
) -> str:
    """
    Genera un archivo FastAPI completo: imports + app + modelos + endpoints.
    """
    models_code = "\n\n\n".join(code for _, code in modelos)
    endpoints_code = "\n\n\n".join(
        generar_endpoint(
            ep["path"],
            ep["metodo"],
            ep.get("request_model"),
            ep.get("response_model"),
            indent=indent,
        )
        for ep in endpoints
    )

    # Detectar imports necesarios
    pii_needed = any("PII" in code for _, code in modelos)
    email_used = any("EmailStr" in code for _, code in modelos)
    datetime_used = any("datetime" in code for _, code in modelos)
    optional_used = any("Optional" in code for _, code in modelos)
    field_used = any("Field(" in code for _, code in modelos)
    http_used = bool(endpoints)

    imports = ["from fastapi import FastAPI, HTTPException, status"]
    if email_used:
        imports.append("from pydantic import BaseModel, EmailStr")
    else:
        imports.append("from pydantic import BaseModel")
    if datetime_used:
        imports.append("from datetime import datetime")
    if optional_used:
        imports.append("from typing import Optional, Dict, Any")
    elif http_used:
        imports.append("from typing import Dict, Any")
    if field_used and not email_used:
        imports.append("from pydantic import Field")

    header = f'''"""
API migrada automáticamente por api-explorer · MOD-9.
Generado: {datetime.now().isoformat(timespec="seconds")}
"""
{chr(10).join(imports)}


app = FastAPI(
    title="{titulo}",
    version="{version}",
    description="Esqueleto generado automáticamente desde análisis de api-explorer.",
)


# ─────────────────────── Modelos ───────────────────────

{models_code}


# ─────────────────────── Endpoints ───────────────────────

{endpoints_code}
'''
    return header


# ─────────────────────── Función principal ───────────────────────


def analizar_a_fastapi(
    payload_analisis: Dict[str, Any],
    titulo: str = "API Migrada",
    version: str = "1.0.0",
) -> str:
    """
    Punto de entrada principal del MOD-9.

    Args:
        payload_analisis: dict con la estructura inferida por api-explorer.
            Espera al menos las keys: 'estructura' (con 'campos' o 'muestra')
            y 'pii_detectado' (opcional).
        titulo: título para FastAPI(title=...).
        version: versión para FastAPI(version=...).

    Returns:
        Código Python completo como string, listo para escribir a .py.
    """
    estructura = payload_analisis.get("estructura", {})
    pii_info = payload_analisis.get("pii_detectado", {})
    url_origen = payload_analisis.get("url", "desconocida")

    # Extraer lista de campos
    campos_raw = estructura.get("campos") or estructura.get("muestra") or []

    # Si no hay campos explícitos, inferir de la muestra de registros
    if not campos_raw and estructura.get("registros_muestra"):
        muestra = estructura["registros_muestra"][0] if estructura["registros_muestra"] else {}
        campos_raw = [{"nombre": k, "tipo": "Any"} for k in muestra.keys()]

    # PII set
    pii_nombres = {h.get("campo") for h in pii_info.get("hallazgos", []) if h.get("campo")}

    # Construir lista de campos normalizada
    campos: List[Dict[str, Any]] = []
    for c in campos_raw:
        nombre = c.get("nombre") or c.get("key") or c.get("path", "")
        if not nombre:
            continue
        tipo_inferido = c.get("tipo", "Any")
        tipo_py = _tipo_python_desde_inferencia(tipo_inferido)
        es_pii, tipo_pii = _es_pii(nombre)
        # PII forzado si está en pii_detectado
        if nombre in pii_nombres:
            es_pii = True
            tipo_pii = tipo_pii or "detectado"
        campos.append({
            "nombre": nombre,
            "tipo": tipo_inferido,
            "tipo_py": tipo_py,
            "opcional": c.get("opcional", False) or tipo_inferido == "null",
            "pii": tipo_pii if es_pii else None,
            "descripcion": c.get("descripcion", ""),
        })

    # Generar modelos: 1 RequestModel + 1 ResponseModel básico
    request_model = generar_modelo_pydantic(
        nombre="LegacyRequest",
        campos=[{**c, "opcional": True} for c in campos],  # request todo opcional por seguridad
    )
    response_model = generar_modelo_pydantic(
        nombre="LegacyResponse",
        campos=campos,
    )

    # Endpoint inferido del path
    path_origen = url_origen.replace("https://", "").replace("http://", "").split("/")
    endpoint_path = "/" + "/".join(p for p in path_origen[1:] if p) or "/legacy"

    endpoints = [
        {
            "path": endpoint_path,
            "metodo": "POST",
            "request_model": "LegacyRequest",
            "response_model": "LegacyResponse",
        },
        {
            "path": endpoint_path,
            "metodo": "GET",
            "request_model": None,
            "response_model": "LegacyResponse",
        },
    ]

    # Generar app completa
    return generar_app_fastapi(
        titulo=titulo,
        version=version,
        modelos=[("LegacyRequest", request_model), ("LegacyResponse", response_model)],
        endpoints=endpoints,
    )
