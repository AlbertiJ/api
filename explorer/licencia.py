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

Si la firma no coincide, la licencia es inválida. No se puede falsificar
sin conocer el SECRET, que está embebido en el código fuente. Aceptable
como MVP para un producto one-time de $20.

En una próxima iteración se puede:
- Mover el SECRET a un servidor de licencias (modelo SaaS).
- Usar criptografía asimétrica (RSA) en vez de HMAC.
- Ofuscar el SECRET en el binario con maza.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Tuple

# SECRET compartido entre el generador y el validador.
# Generado aleatoriamente el 2026-06-21. Rotarlo cuando se publique v1.0.
SECRET_LICENCIA_PRO = (
    "api-explorer-pro-v1-2026-06-21-aXk9QzL3mN8pR2vT5yF7wJ4hG6bE1c"
)

# Validación de email — regex simple pero suficiente.
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def generar_firma(email: str, tier: str, issued: str) -> str:
    """
    HMAC-SHA256 sobre los campos canónicos de la licencia.
    El email se normaliza a minúsculas y sin espacios.
    """
    canonico = f"{email.lower().strip()}|{tier}|{issued}"
    return hmac.new(
        SECRET_LICENCIA_PRO.encode("utf-8"),
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

    sig_esperado = generar_firma(email, tier, issued)
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
