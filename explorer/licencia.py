"""
licencia.py — Validación de licencias para el tier Pro.

Una licencia es un archivo JSON que vive en `~/.api-explorer-license`
con esta estructura:

    {
      "email": "cliente@empresa.com",
      "tier": "pro",
      "issued": "2026-06-21",
      "sig": "<hex_hmac_sha256>"
    }

La firma `sig` se calcula como:

    HMAC-SHA256(SECRET_LICENCIA_PRO, email.lower()|tier|issued)

El SECRET NO vive en el código fuente — se lee de la variable de entorno
`APIEXPLORER_LICENSE_SECRET`. Motivo: este repo es público en GitHub, y
un secreto embebido en el código deja de ser secreto en el momento del
push. La versión anterior tenía el HMAC hardcodeado acá mismo; ese valor
quedó expuesto en el historial de git y debe tratarse como comprometido
para siempre — cualquiera que lo haya visto/clonado pudo generar
licencias Pro válidas gratis. Se rotó por uno nuevo que solo existe
fuera del repo.

Cómo configurarlo:
    export APIEXPLORER_LICENSE_SECRET="<valor generado con secrets.token_urlsafe(32)>"

En una próxima iteración se puede:
- Mover la validación a un servidor de licencias (modelo SaaS), así el
  secreto nunca toca la máquina del cliente.
- Usar criptografía asimétrica (RSA/Ed25519) en vez de HMAC simétrico,
  para que el validador no necesite conocer el mismo secreto que firma.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Tuple

# Validación de email — regex simple pero suficiente.
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SecretNoConfigurado(RuntimeError):
    """Se intentó firmar o validar una licencia sin APIEXPLORER_LICENSE_SECRET seteada."""


def _obtener_secret() -> str:
    secret = os.environ.get("APIEXPLORER_LICENSE_SECRET", "")
    if not secret:
        raise SecretNoConfigurado(
            "Falta la variable de entorno APIEXPLORER_LICENSE_SECRET. "
            "Generá un valor con `python -c \"import secrets; "
            "print(secrets.token_urlsafe(32))\"` y exportalo antes de "
            "generar o validar licencias. No lo hardcodees en el código."
        )
    return secret


def generar_firma(email: str, tier: str, issued: str) -> str:
    """
    HMAC-SHA256 sobre los campos canónicos de la licencia.
    El email se normaliza a minúsculas y sin espacios.
    """
    canonico = f"{email.lower().strip()}|{tier}|{issued}"
    return hmac.new(
        _obtener_secret().encode("utf-8"),
        canonico.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validar_licencia_en_archivo(ruta: Path) -> Tuple[bool, str]:
    """
    Lee un archivo de licencia y devuelve (valida, mensaje).
    """
    if not ruta.exists():
        return False, f"No existe archivo de licencia: {ruta}"

    try:
        texto = ruta.read_text(encoding="utf-8")
        data = json.loads(texto)
    except json.JSONDecodeError as e:
        return False, f"Archivo de licencia no es JSON válido: {e}"
    except OSError as e:
        return False, f"No se pudo leer el archivo: {e}"

    if not isinstance(data, dict):
        return False, "Licencia malformada (no es un objeto)"

    email = data.get("email", "")
    tier = data.get("tier", "")
    issued = data.get("issued", "")
    sig_recibido = data.get("sig", "")

    if not all([email, tier, issued, sig_recibido]):
        return False, "Licencia incompleta (faltan campos requeridos)"

    if tier != "pro":
        return False, f"Tier '{tier}' no es Pro"

    if not EMAIL_REGEX.match(email):
        return False, f"Email inválido en licencia: '{email}'"

    try:
        sig_esperado = generar_firma(email, tier, issued)
    except SecretNoConfigurado as e:
        return False, str(e)

    # compare_digest evita timing attacks
    if not hmac.compare_digest(sig_recibido, sig_esperado):
        return False, "Firma inválida — licencia manipulada o SECRET desactualizado"

    return True, f"Pro — licencia válida para {email} (emitida {issued})"


def validar_licencia_pro() -> Tuple[bool, str]:
    """
    Valida la licencia Pro del usuario en su HOME.
    Returns (es_valida, mensaje).
    """
    ruta = Path.home() / ".api-explorer-license"
    return validar_licencia_en_archivo(ruta)
