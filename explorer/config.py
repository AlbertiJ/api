"""
config.py — Parámetros globales de conexión y ritmo.

Pensado para que el ritmo de las llamadas sea explícito y modificable.
Si la API de destino está protegida por WAF/CDN (Cloudflare, Akamai,
AWS WAF, DataDome) y detecta velocidad humana irreal, devuelve 403/429.
Por eso todas las llamadas a Internet pasan por _esperar() y respetan
los valores definidos acá.
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Pausa mínima entre requests al mismo host (segundos)
    pausa_minima: float = 1.2
    # Pausa máxima (se sortea un valor entre min y max para no ser predecible)
    pausa_maxima: float = 2.4
    # Timeout de lectura por request
    timeout: int = 15
    # Cuántos registros máximo analizamos en una pasada
    max_registros: int = 5000
    # Tope absoluto de páginas a seguir en paginación
    max_paginas: int = 50
    # User-Agent. Mantenemos uno neutro y explícito, no nos hacemos pasar por
    # otro software — la idea es ser identificables pero respetuosos.
    user_agent: str = "api-explorer/0.2 (+https://github.com/AlbertiJ/api)"
    # Si está en True, sorteamos jitter sobre la pausa base.
    jitter: bool = True


# Singleton accesible desde cualquier módulo.
CFG = Config(
    pausa_minima=float(os.environ.get("APIEXPLORER_PAUSA_MIN", "1.2")),
    pausa_maxima=float(os.environ.get("APIEXPLORER_PAUSA_MAX", "2.4")),
    timeout=int(os.environ.get("APIEXPLORER_TIMEOUT", "15")),
    max_registros=int(os.environ.get("APIEXPLORER_MAX_REGS", "5000")),
    max_paginas=int(os.environ.get("APIEXPLORER_MAX_PAGINAS", "50")),
    jitter=os.environ.get("APIEXPLORER_JITTER", "1") not in ("0", "false", "False"),
)


def esperar(host: str = "") -> None:
    """
    Pausa humana antes del próximo request.
    Si jitter=True, la pausa es aleatoria entre pausa_minima y pausa_maxima.
    Si se llama con el mismo host dentro de los últimos N segundos,
    igual respeta la pausa (no se puede saltar).
    """
    if CFG.jitter:
        pausa = random.uniform(CFG.pausa_minima, CFG.pausa_maxima)
    else:
        pausa = CFG.pausa_minima
    time.sleep(pausa)


def esperar_entre_paginas(numero_pagina: int) -> None:
    """
    Pausa más larga entre páginas de una API paginada, para no levantar
    sospechas cuando estamos siguiendo un cursor durante varios minutos.
    """
    base = CFG.pausa_maxima if CFG.jitter else CFG.pausa_minima
    # Cada 5 páginas, agregamos una pausa más larga.
    extra = 1.5 if numero_pagina % 5 == 0 else 0.0
    pausa = base + extra + random.uniform(0, 0.4) if CFG.jitter else base + extra
    time.sleep(pausa)