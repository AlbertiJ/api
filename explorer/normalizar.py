"""
normalizar.py — Pre-procesa valores antes de aplicar regex de PII.

Por qué existe: una API maliciosa o mal escrita puede mandar DNI
"25.478.963" en vez de "25478963", o emails con caracteres invisibles
para evadir detectores ingenuos. Si no normalizamos, el detector
dice "no hay PII" y el informe queda técnicamente correcto pero
engañosamente incompleto.

Esto NO modifica el valor original: lo usa solo para comparar
contra la regex, y deja el valor crudo en el reporte forense.
"""
from __future__ import annotations

import html
import re
import unicodedata

# Caracteres invisibles o zero-width que pueden usarse para ofuscar.
_ZERO_WIDTH = re.compile(r"[\u200B-\u200D\uFEFF\u2024\u2025\u2060\u2061\u2062\u2063\u2064]")

# Separadores de miles "raros" que aparecen en algunos formularios
# (non-breaking space, narrow no-break space, etc.)
_SEPARADORES_ESPACIO = re.compile(r"[\u00A0\u2000-\u200A\u2028\u2029\u202F]")

# Separadores visuales entre dígitos: punto, coma, guión bajo, espacio.
# Solo se quitan si están ENTRE dígitos (no en otro lado).
_SEPARADORES_NUMERICOS = re.compile(r"(?<=\d)[\s.,\-_]+(?=\d)")


def normalizar_para_pii(valor: Any) -> str:
    """
    Devuelve una versión "limpia" del valor, apta para que las regex
    de PII matcheen. Si el valor ya estaba limpio, devuelve el mismo string.
    """
    if not isinstance(valor, str):
        return valor

    # 1) Decodificar entidades HTML (&#64; → @)
    s = html.unescape(valor)

    # 2) Quitar zero-width chars y otros invisibles
    s = _ZERO_WIDTH.sub("", s)

    # 3) Reemplazar separadores de espacio "raros" por espacio normal
    s = _SEPARADORES_ESPACIO.sub(" ", s)

    # 4) Quitar separadores numéricos visuales entre dígitos
    s = _SEPARADORES_NUMERICOS.sub("", s)

    # 5) Normalizar acentos (NFD → ASCII) para evitar evasión por Unicode.
    #    Solo si la versión con acentos no matchea nada y la versión sin acentos sí.
    #    No lo aplicamos por defecto para no romper emails con ñ/tildes.
    return s


def fue_normalizado(original: str, normalizado: str) -> bool:
    """True si la normalización cambió el string."""
    return original != normalizado


def variante_sin_acentos(valor: str) -> str:
    """Genera variante NFD sin acentos. Útil como segunda oportunidad."""
    if not isinstance(valor, str):
        return valor
    return "".join(
        c for c in unicodedata.normalize("NFD", valor)
        if unicodedata.category(c) != "Mn"
    )