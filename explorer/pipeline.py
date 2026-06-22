"""
pipeline.py — Pipeline unificado: discover → analyze → informe consolidado.

Este es el módulo que faltaba para cerrar la brecha entre @scraper y api-explorer.
Combina:
  - discovery: recon de superficie
  - core.explorar: análisis forense de un endpoint
  - informe: hash SHA-256 firmado
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .core import ErrorExploracion, explorar
from .discovery import discover, DEFAULT_RECON_PATHS
from .fetcher import FetcherConfig
from .informe import generar_informe


@dataclass
class PipelineResult:
    """Resultado consolidado del pipeline."""
    base_url: str
    timestamp_utc: str
    responsable: str
    cliente: str
    recon: Dict[str, Any] = field(default_factory=dict)        # output de discover()
    endpoints_analyzed: List[Dict[str, Any]] = field(default_factory=list)  # lista de payloads
    consolidado: Dict[str, Any] = field(default_factory=dict)
    hash_sha256: str = ""
    elapsed_total_ms: int = 0


def run_pipeline(
    base_url: str,
    responsable: str = "no_especificado",
    cliente: str = "no_especificado",
    cfg: Optional[FetcherConfig] = None,
    bearer: Optional[str] = None,
    origin: Optional[str] = None,
    max_endpoints_to_analyze: int = 5,
    delay_between: float = 0.5,
    do_discovery: bool = True,
    do_analyze: bool = True,
    progress: bool = False,
) -> PipelineResult:
    """
    Corre el pipeline completo: discover → analyze → informe.

    Args:
        base_url: URL base de la API.
        responsable/cliente: identificación (para el informe).
        cfg: FetcherConfig.
        bearer: token Bearer opcional.
        origin: Origin header para spoofing CORS.
        max_endpoints_to_analyze: máximo de endpoints a analizar (los más prometedores).
        delay_between: pausa entre requests.
        do_discovery: hacer recon de superficie (default True).
        do_analyze: analizar los endpoints descubiertos (default True).
        progress: mostrar progreso en stderr.

    Returns:
        PipelineResult con todo: recon + análisis de cada endpoint + consolidado firmado.
    """
    cfg = cfg or FetcherConfig()
    started_at = datetime.now(timezone.utc)
    timestamp = started_at.isoformat(timespec="microseconds")

    result = PipelineResult(
        base_url=base_url,
        timestamp_utc=timestamp,
        responsable=responsable,
        cliente=cliente,
    )

    # FASE 1: RECON
    if do_discovery:
        if progress:
            print(f"\n[pipeline] FASE 1: RECON sobre {base_url}", flush=True)
        result.recon = discover(
            base_url=base_url,
            cfg=cfg,
            bearer=bearer,
            origin=origin,
            delay_between=delay_between,
            do_options=True,
            progress=progress,
        )

    # FASE 2: ANALYZE (los endpoints más prometedores)
    if do_analyze and result.recon:
        if progress:
            print(f"\n[pipeline] FASE 2: ANALYZE sobre {len(result.recon.get('endpoints', []))} endpoints descubiertos", flush=True)
        # Filtrar los que existen y rankear por probabilidad de ser interesantes
        candidatos = _rank_endpoints(result.recon.get("endpoints", []))
        top_n = candidatos[:max_endpoints_to_analyze]
        if progress:
            print(f"  [pipeline] Top {len(top_n)} endpoints seleccionados para análisis profundo", flush=True)
        for i, ep in enumerate(top_n, 1):
            url = ep["full_url"]
            if progress:
                print(f"  [pipeline] ({i}/{len(top_n)}) Analizando {ep['path']} -> {url}", flush=True)
            try:
                payload = explorar(
                    url=url,
                    responsable=responsable,
                    cliente=cliente,
                    formato="json",  # para no generar archivos en cada endpoint
                    directorio_salida="salidas",
                )["exploracion"]
                result.endpoints_analyzed.append({
                    "path": ep["path"],
                    "full_url": url,
                    "status_descubierto": ep["status"],
                    "auth_required": ep["auth_required"],
                    "tipo_detectado": payload.get("tipo_detectado"),
                    "confianza": payload.get("confianza_deteccion"),
                    "total_registros": payload.get("resumen", {}).get("total_registros_reales", 0),
                    "total_campos": payload.get("resumen", {}).get("total_campos", 0),
                    "datos_sensibles": payload.get("resumen", {}).get("datos_sensibles_encontrados", 0),
                    "menores": payload.get("resumen", {}).get("menores_detectados", 0),
                    "hash_sha256": payload.get("hash_sha256", "")[:16] + "...",
                })
            except ErrorExploracion as e:
                result.endpoints_analyzed.append({
                    "path": ep["path"],
                    "full_url": url,
                    "error": str(e),
                })
            if delay_between > 0 and i < len(top_n):
                import time as _t
                _t.sleep(delay_between)

    # FASE 3: CONSOLIDADO
    result.consolidado = {
        "base_url": base_url,
        "timestamp_utc": timestamp,
        "responsable": responsable,
        "cliente": cliente,
        "recon_stats": result.recon.get("stats", {}) if result.recon else {},
        "recon_fingerprint": result.recon.get("fingerprint", {}) if result.recon else {},
        "endpoints_analyzed_count": len(result.endpoints_analyzed),
        "endpoints_analyzed": result.endpoints_analyzed,
        "endpoints_descubiertos_total": result.recon.get("stats", {}).get("total", 0) if result.recon else 0,
        "endpoints_descubiertos_existentes": sum(1 for ep in (result.recon.get("endpoints", []) if result.recon else []) if ep.get("exists")),
    }
    # Hash consolidado
    import hashlib
    canonico = json.dumps(result.consolidado, sort_keys=True, ensure_ascii=False, default=str)
    result.hash_sha256 = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    result.elapsed_total_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

    if progress:
        print(f"\n[pipeline] ✓ Pipeline completo en {result.elapsed_total_ms} ms", flush=True)
        print(f"[pipeline] Hash SHA-256: {result.hash_sha256[:16]}...", flush=True)
    return result


def _rank_endpoints(endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rankea endpoints por probabilidad de ser interesantes para análisis."""
    # Score: 200 (interesante público) > 401 (existe, auth) > 403 (existe, forbid) > otros
    score_map = {200: 10, 401: 8, 403: 6, 405: 4, 301: 2, 302: 2, 500: 1}
    ranked = sorted(
        [e for e in endpoints if e.get("exists")],
        key=lambda e: (score_map.get(e.get("status", 0), 0), e.get("status", 0) == 200, -e.get("size_bytes", 0)),
        reverse=True,
    )
    return ranked


def format_pipeline_informe(result: PipelineResult) -> str:
    """Formatea el informe consolidado como texto."""
    lines = []
    lines.append("=" * 80)
    lines.append("  PIPELINE DE AUDITORÍA DE API — DESCUBRIMIENTO + ANÁLISIS")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Target       : {result.base_url}")
    lines.append(f"Fecha (UTC)  : {result.timestamp_utc}")
    lines.append(f"Responsable  : {result.responsable}")
    lines.append(f"Cliente      : {result.cliente}")
    lines.append(f"Elapsed      : {result.elapsed_total_ms} ms")
    lines.append(f"Hash SHA-256 : {result.hash_sha256}")
    lines.append("")
    if result.recon:
        lines.append("─" * 60)
        lines.append("FASE 1: RECON (descubrimiento de superficie)")
        lines.append("─" * 60)
        fp = result.recon.get("fingerprint", {})
        lines.append(f"  Server:      {fp.get('server', '?')}")
        lines.append(f"  Backend:     {fp.get('backend_lang', '?')}")
        lines.append(f"  Auth:        {fp.get('auth_scheme', '?')}")
        s = result.recon.get("stats", {})
        lines.append(f"  Stats:       {s.get('200',0)}x 200 | {s.get('401',0)}x 401 | {s.get('403',0)}x 403 | {s.get('404',0)}x 404 | {s.get('5xx',0)}x 5xx")
        lines.append(f"  Total probados: {s.get('total',0)}")
        lines.append("")
    if result.endpoints_analyzed:
        lines.append("─" * 60)
        lines.append(f"FASE 2: ANÁLISIS FORENSE ({len(result.endpoints_analyzed)} endpoints)")
        lines.append("─" * 60)
        for i, ep in enumerate(result.endpoints_analyzed, 1):
            lines.append(f"  [{i}] {ep['path']}")
            if "error" in ep:
                lines.append(f"      ERROR: {ep['error']}")
            else:
                lines.append(f"      tipo={ep.get('tipo_detectado')} | registros={ep.get('total_registros', 0)} | campos={ep.get('total_campos', 0)} | PII={ep.get('datos_sensibles', 0)} | menores={ep.get('menores', 0)} | hash={ep.get('hash_sha256', '')}")
            lines.append("")
    lines.append("─" * 60)
    lines.append("FIRMA DE AUDITORÍA")
    lines.append("─" * 60)
    lines.append(f"  Hash SHA-256: {result.hash_sha256}")
    lines.append(f"  Algoritmo:    SHA-256 sobre JSON canónico (claves ordenadas)")
    lines.append(f"  Generado por: api-explorer v0.3.0 + discovery + pipeline")
    return "\n".join(lines)
