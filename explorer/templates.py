"""
templates.py — Motor de templates dinámicas para discovery de endpoints.

Convierte plantillas con variables como ``/v1/:modulo/:accion`` en
expresiones regulares con named groups, y permite instanciarlas con
valores concretos para que el motor de discovery pruebe cada combinación.

Inspirado en la observación de la sesión 2026-06-22 del DIARIO-TECNICO:
los endpoints de un cliente X no tienen por qué parecerse a los de un
cliente Y. La solución no es hardcodear paths, sino dejar que el usuario
declare la *forma* y que el motor itere los *valores* hasta encontrar
los que matchean.

Ejemplo de uso::

    tm = TemplateMatch("/v1/:modulo/:accion")
    tm.vars
    # -> ["modulo", "accion"]
    tm.match("/v1/users/list")
    # -> {"modulo": "users", "accion": "list"}
    tm.instanciar({"modulo": "users", "accion": "list"})
    # -> "/v1/users/list"
"""
from __future__ import annotations

import re
from itertools import product
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


# Marcador de variable: :nombre (letras, dígitos, guión bajo)
_VAR_RE = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")

# Caracteres válidos en un slot instanciado. Conservador a propósito:
# letras, dígitos, guión, guión bajo, punto, @. Cualquier otro se escapa.
_SLOT_CHARSET = r"[A-Za-z0-9._@-]+"


class TemplateError(ValueError):
    """La plantilla es inválida (formato, variables duplicadas, etc.)."""


class TemplateMatch:
    """
    Una plantilla con variables. Compilable a regex con named groups
    e instanciable con un dict de valores.
    """

    def __init__(self, plantilla: str) -> None:
        if not plantilla or not plantilla.startswith("/"):
            raise TemplateError(
                f"La plantilla debe empezar con '/'. Recibido: {plantilla!r}"
            )
        self.plantilla: str = plantilla
        self.vars: List[str] = _VAR_RE.findall(plantilla)
        # Detectar variables duplicadas
        if len(self.vars) != len(set(self.vars)):
            dupes = sorted({v for v in self.vars if self.vars.count(v) > 1})
            raise TemplateError(
                f"Variables duplicadas en la plantilla: {dupes}"
            )
        self._regex: re.Pattern = self._compilar(plantilla)

    def _compilar(self, plantilla: str) -> re.Pattern:
        """
        Transforma ``/v1/:modulo/:accion`` en
        ``^/v1/(?P<modulo>[A-Za-z0-9._@-]+)/(?P<accion>[A-Za-z0-9._@-]+)/?$``.
        """
        # Reemplazar :var por grupo con nombre. Hacemos un replace por
        # variable en orden de aparición para no escaparnos con sub-strings.
        patron_regex = ""
        i = 0
        for m in _VAR_RE.finditer(plantilla):
            patron_regex += re.escape(plantilla[i:m.start()])
            patron_regex += f"(?P<{m.group(1)}>{_SLOT_CHARSET})"
            i = m.end()
        patron_regex += re.escape(plantilla[i:])
        return re.compile(f"^{patron_regex}/?$")

    @property
    def regex(self) -> re.Pattern:
        return self._regex

    def match(self, path_real: str) -> Optional[Dict[str, str]]:
        """
        Devuelve ``{var: valor}`` si ``path_real`` matchea la plantilla.
        Devuelve ``None`` si no matchea.
        """
        # Aceptamos paths con o sin slash inicial
        path = path_real if path_real.startswith("/") else "/" + path_real
        m = self._regex.match(path)
        return m.groupdict() if m else None

    def instanciar(self, valores: Dict[str, str]) -> str:
        """
        Devuelve el path instanciado con los valores dados.
        Faltan variables → TemplateError. Sobran → se ignoran.
        """
        faltan = [v for v in self.vars if v not in valores]
        if faltan:
            raise TemplateError(
                f"Faltan valores para variables: {faltan}. "
                f"Esperadas: {self.vars}"
            )
        resultado = self.plantilla
        for var, val in valores.items():
            if f":{var}" in resultado:
                # Validar que el valor no rompa el charset
                if not re.fullmatch(_SLOT_CHARSET, str(val)):
                    raise TemplateError(
                        f"Valor inválido para :{var}: {val!r}. "
                        f"Charset permitido: {re.escape(_SLOT_CHARSET)}"
                    )
                resultado = resultado.replace(f":{var}", str(val))
        return resultado

    def iterar_combinaciones(
        self, slot_values: Dict[str, Sequence[str]]
    ) -> Iterator[Dict[str, str]]:
        """
        Genera el producto cartesiano de los valores por variable.
        Cada yield es un dict {var: valor_combinado}.

        Si una variable no tiene valores asignados, se usa ``[""]`` como
        fallback (path sin el slot poblado, que sirve para endpoints de
        un solo nivel como ``/v1/users`` que matchea ``/v1/:modulo``).
        """
        slots: List[Iterable[str]] = []
        for var in self.vars:
            valores = slot_values.get(var)
            if not valores:
                # Variable sin valores: probar con string vacío para
                # que la plantilla colapse (ej: /v1/:modulo → /v1/users)
                valores = [""]
            slots.append(valores)
        for combo in product(*slots):
            yield dict(zip(self.vars, combo))

    def combinaciones_total(self, slot_values: Dict[str, Sequence[str]]) -> int:
        """Cantidad total de combinaciones que generaría iterar_combinaciones()."""
        total = 1
        for var in self.vars:
            valores = slot_values.get(var) or [""]
            total *= len(valores)
        return total


def cargar_slot_values_desde_json(datos: Dict) -> Dict[str, List[str]]:
    """
    Normaliza el JSON de ``reglas/plantillas.json`` al formato
    ``{var: [valores]}``.
    Acepta tanto listas como strings sueltos (los envuelve en lista).
    """
    out: Dict[str, List[str]] = {}
    for k, v in datos.items():
        if isinstance(v, str):
            out[k] = [v]
        elif isinstance(v, list):
            out[k] = [str(x) for x in v]
        else:
            raise TemplateError(f"Slot {k!r}: se esperaba str o list, recibí {type(v).__name__}")
    return out


def parsear_plantilla_desde_slot(plantilla: str) -> TemplateMatch:
    """Helper: instancia un TemplateMatch o levanta TemplateError."""
    return TemplateMatch(plantilla)
