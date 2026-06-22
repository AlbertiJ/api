"""
exportar.py — Genera los archivos JSON / CSV / HTML.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict


def _ruta(nombre: str, ext: str, directorio: str) -> Path:
    Path(directorio).mkdir(parents=True, exist_ok=True)
    return Path(directorio) / f"{nombre}.{ext}"


def _timestamp_corto() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def _nombre_archivo(exploracion: Dict) -> str:
    return f"exploracion-{_timestamp_corto()}-{exploracion['hash_sha256'][:8]}"


def exportar_json(exploracion: Dict, directorio: str = "salidas") -> str:
    ruta = _ruta(_nombre_archivo(exploracion), "json", directorio)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(exploracion, f, indent=2, ensure_ascii=False, default=str)
    return str(ruta)


def exportar_csv(exploracion: Dict, directorio: str = "salidas") -> str:
    ruta = _ruta(_nombre_archivo(exploracion), "csv", directorio)

    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["SECCIÓN", "CAMPO", "VALOR"])
        w.writerow(["metadatos", "url", exploracion["url"]])
        w.writerow(["metadatos", "timestamp_utc", exploracion["timestamp_utc"]])
        w.writerow(["metadatos", "responsable", exploracion["responsable"]])
        w.writerow(["metadatos", "cliente", exploracion["cliente"]])
        w.writerow(["metadatos", "tipo_detectado", exploracion["tipo_detectado"]])
        w.writerow(["metadatos", "confianza", exploracion["confianza_deteccion"]])
        w.writerow(["metadatos", "hash_sha256", exploracion["hash_sha256"]])
        if exploracion.get("cadena_auditoria_previa"):
            w.writerow(["metadatos", "cadena_auditoria_previa",
                        exploracion["cadena_auditoria_previa"]])
        w.writerow([])
        w.writerow(["RESUMEN"])
        for k, v in exploracion["resumen"].items():
            w.writerow(["resumen", k, v])
        w.writerow([])
        w.writerow(["METADATOS DE PAGINACIÓN"])
        for k, v in exploracion.get("metadata_paginacion", {}).items():
            w.writerow(["paginacion", k, v])
        w.writerow([])
        w.writerow(["FALTANTES"])
        for f_ in exploracion["faltantes_reportados"]:
            w.writerow(["faltante", f_["campo_esperado"],
                        f"{f_['seccion']} | obligatorio={f_['obligatorio']}"])
        w.writerow([])
        w.writerow(["PII"])
        for h in exploracion["pii_detectado"]["hallazgos"]:
            w.writerow(["pii", h["path"],
                        f"{h['tipo_pii']} | {h['nivel_sensibilidad']} | {h['metodo']}"])
        w.writerow([])
        w.writerow(["MENORES"])
        w.writerow(["menores", "total_menores",
                    exploracion["reglas_menores"]["total_menores"]])
        w.writerow(["menores", "alerta_menores",
                    exploracion["reglas_menores"]["alerta_menores"]])
        for c in exploracion["reglas_menores"]["campos_responsable_faltantes"]:
            w.writerow(["menores", "FALTA_responsable", c])
    return str(ruta)


def _html_escape(s) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def exportar_html(exploracion: Dict, directorio: str = "salidas") -> str:
    ruta = _ruta(_nombre_archivo(exploracion), "html", directorio)

    resumen = exploracion["resumen"]
    faltantes = exploracion["faltantes_reportados"]
    pii = exploracion["pii_detectado"]
    menores = exploracion["reglas_menores"]
    pag = exploracion.get("metadata_paginacion", {})

    filas_faltantes = "".join(
        f"<tr class='{'critico' if f_['obligatorio'] else 'suave'}'>"
        f"<td>{_html_escape(f_['campo_esperado'])}</td>"
        f"<td>{_html_escape(f_['seccion'])}</td>"
        f"<td>{'SÍ' if f_['obligatorio'] else 'no'}</td>"
        f"<td>NO TRAÍDO</td></tr>"
        for f_ in faltantes
    ) or "<tr><td colspan='4'>Sin faltantes</td></tr>"

    filas_pii = "".join(
        f"<tr class='{_html_escape(h['nivel_sensibilidad'])}'>"
        f"<td>{_html_escape(h['path'])}</td>"
        f"<td>{_html_escape(h['campo'])}</td>"
        f"<td>{_html_escape(h['tipo_pii'])}</td>"
        f"<td>{_html_escape(h['categoria'])}</td>"
        f"<td>{_html_escape(h['nivel_sensibilidad'])}</td>"
        f"<td>{_html_escape(h['metodo'])}</td></tr>"
        for h in pii["hallazgos"]
    ) or "<tr><td colspan='6'>Sin hallazgos de datos sensibles</td></tr>"

    alerta_menores = ""
    if menores.get("alerta_menores"):
        alerta_menores = f"""
        <div class='alerta'>
          ⚠ Se detectaron <b>{menores['total_menores']}</b> posible(s) menor(es) de edad,
          y faltan los siguientes campos de responsable obligatorio:
          <ul>{''.join(f'<li>{_html_escape(c)}</li>' for c in menores['campos_responsable_faltantes'])}</ul>
        </div>"""

    aviso_pag = ""
    if pag.get("max_alcanzado"):
        aviso_pag = (
            "<div class='alerta'>⚠ Se alcanzó el tope de registros "
            f"({resumen.get('total_registros_reales', '?')} reales, "
            f"{resumen.get('total_registros_analizados', '?')} analizados). "
            "Exploración parcial.</div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8">
<title>Exploración {_html_escape(exploracion['hash_sha256'][:16])}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 2rem; color: #1d1d1f; background: #fafafa; }}
  h1 {{ color: #1d1d1f; border-bottom: 2px solid #0071e3; padding-bottom: .3rem; }}
  h2 {{ margin-top: 2rem; color: #0071e3; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; background: white; }}
  th, td {{ border: 1px solid #e0e0e0; padding: .5rem .75rem; text-align: left; }}
  th {{ background: #f5f5f7; }}
  .critico, .alto {{ background: #ffe5e5; }}
  .medio {{ background: #fff4e0; }}
  .suave {{ background: #fff8d0; }}
  .hash {{ font-family: monospace; background: #1d1d1d; color: #5ac8fa;
           padding: .75rem 1rem; border-radius: 8px; word-break: break-all; }}
  .alerta {{ background: #ffe5e5; border-left: 4px solid #ff3b30;
             padding: 1rem; margin: 1rem 0; border-radius: 4px; }}
  .meta {{ background: white; padding: 1rem; border-radius: 8px;
           border: 1px solid #e0e0e0; }}
  .meta p {{ margin: .25rem 0; }}
  .resumen-grid {{ display: grid; grid-template-columns: repeat(3, 1fr);
                   gap: 1rem; margin: 1rem 0; }}
  .resumen-card {{ background: white; padding: 1rem; border-radius: 8px;
                   border: 1px solid #e0e0e0; }}
  .resumen-card .numero {{ font-size: 2rem; font-weight: 600; color: #0071e3; }}
  .resumen-card .etiqueta {{ font-size: .85rem; color: #6e6e73; margin-top: .25rem; }}
  .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e0e0e0;
             color: #6e6e73; font-size: .85rem; }}
</style>
</head><body>
<h1>Informe de Exploración de API</h1>

<div class='meta'>
  <p><b>URL explorada:</b> {_html_escape(exploracion['url'])}</p>
  <p><b>Fecha y hora (UTC):</b> {_html_escape(exploracion['timestamp_utc'])}</p>
  <p><b>Responsable:</b> {_html_escape(exploracion['responsable'])}</p>
  <p><b>Cliente:</b> {_html_escape(exploracion['cliente'])}</p>
  <p><b>Tipo detectado:</b> {_html_escape(exploracion['tipo_detectado'])}
     (confianza {exploracion['confianza_deteccion']})</p>
  <p><b>Pistas:</b> {_html_escape(', '.join(exploracion['pistas_deteccion']))}</p>
  <p><b>Fuente de paginación:</b> {_html_escape(resumen.get('fuente_paginacion', 'ninguna'))}</p>
  <p><b>Pausa entre requests:</b> {resumen.get('pausa_entre_requests', '?')}s</p>
</div>

<h2>Hash SHA-256</h2>
<div class='hash'>{exploracion['hash_sha256']}</div>

<h2>Resumen</h2>
<div class='resumen-grid'>
  <div class='resumen-card'><div class='numero'>{resumen.get('total_registros_reales', '?')}</div><div class='etiqueta'>registros reales</div></div>
  <div class='resumen-card'><div class='numero'>{resumen.get('total_registros_analizados', '?')}</div><div class='etiqueta'>analizados</div></div>
  <div class='resumen-card'><div class='numero'>{resumen['total_campos']}</div><div class='etiqueta'>campos únicos</div></div>
  <div class='resumen-card'><div class='numero'>{resumen['campos_faltantes']}</div><div class='etiqueta'>faltantes</div></div>
  <div class='resumen-card'><div class='numero'>{resumen['datos_sensibles_encontrados']}</div><div class='etiqueta'>datos sensibles</div></div>
  <div class='resumen-card'><div class='numero'>{resumen['menores_detectados']}</div><div class='etiqueta'>menores detectados</div></div>
</div>

{aviso_pag}
{alerta_menores}

<h2>Campos faltantes</h2>
<table>
  <thead><tr><th>Campo esperado</th><th>Sección</th><th>Obligatorio</th><th>Estado</th></tr></thead>
  <tbody>{filas_faltantes}</tbody>
</table>

<h2>Datos sensibles detectados</h2>
<table>
  <thead><tr><th>Path</th><th>Campo</th><th>Tipo</th><th>Categoría</th><th>Nivel</th><th>Método</th></tr></thead>
  <tbody>{filas_pii}</tbody>
</table>

<div class='footer'>
  Generado por api-explorer. El hash SHA-256 garantiza que ni el contenido
  ni el momento han sido alterados.
</div>
</body></html>"""

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    return str(ruta)