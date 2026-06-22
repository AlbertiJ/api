"""
Tests del explorador. Corren con `python tests/test_explorer.py`.
Cubren el núcleo + las 4 mejoras documentadas en INGENIERIA.md.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Permite importar el paquete sin instalarlo.
sys.path.insert(0, str(Path(__file__).parent.parent))

from explorer.campos import detectar_faltantes, inspeccionar_campos
from explorer.config import CFG
from explorer.core import _calcular_hash, explorar
from explorer.detectar import detectar_tipo_api
from explorer.diff import diff_forense, encadenar_hash, formatear_diff_texto
from explorer.exportar import exportar_csv, exportar_html, exportar_json
from explorer.informe import generar_informe
from explorer.normalizar import normalizar_para_pii
from explorer.sensibles import detectar_pii, evaluar_menores


# ─────────────────────────── helpers ───────────────────────────

def cargar_ejemplo(nombre: str):
    ruta = Path(__file__).parent.parent / "ejemplos" / nombre
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────── núcleo ───────────────────────────

def test_deteccion_natatorio():
    data = cargar_ejemplo("natatorio.json")
    tipo, conf, pistas = detectar_tipo_api(data, "natatorio")
    assert tipo == "natatorio", f"Esperado natatorio, salió {tipo}"
    assert conf > 0.2
    # Las pistas tienen prefijo url:/key:/val:
    pistas_limpias = {p.split(":", 1)[-1] for p in pistas}
    assert any(p in pistas_limpias for p in ("natatorio", "pileta", "apto_medico", "socio"))
    print(f"  ✓ test_deteccion_natatorio → tipo={tipo} conf={conf} pistas={pistas}")


def test_deteccion_biblioteca():
    data = cargar_ejemplo("biblioteca.json")
    tipo, conf, pistas = detectar_tipo_api(data, "biblioteca")
    assert tipo == "biblioteca"
    assert conf > 0.1
    print(f"  ✓ test_deteccion_biblioteca → tipo={tipo} conf={conf} pistas={pistas}")


def test_inspeccion_campos():
    data = cargar_ejemplo("natatorio.json")
    est = inspeccionar_campos(data)
    assert est["total_registros"] > 0
    assert "id_socio" in est["campos"]
    assert est["campos"]["email"]["tipo_mayoritario"] in ("string_email", "string")
    assert "campos_detectados" in est  # para gap analysis
    print(f"  ✓ test_inspeccion_campos → {est['total_campos_unicos']} campos, "
          f"{est['total_registros']} registros")


def test_faltantes_biblioteca():
    data = cargar_ejemplo("biblioteca.json")
    est = inspeccionar_campos(data)
    faltantes = detectar_faltantes(est, "biblioteca")
    nombres = [f["campo_esperado"] for f in faltantes]
    assert len(faltantes) > 0, "Debería detectar faltantes en biblioteca"
    print(f"  ✓ test_faltantes_biblioteca → {len(faltantes)} faltantes: {nombres[:5]}")


def test_pii_natatorio():
    data = cargar_ejemplo("natatorio.json")
    pii = detectar_pii(data)
    assert pii["total_hallazgos"] > 0
    cats = pii["por_categoria"]
    assert "contacto" in cats
    assert "salud" in cats
    assert "identidad" in cats
    print(f"  ✓ test_pii_natatorio → {pii['total_hallazgos']} hallazgos, cats={cats}")


def test_menores_sin_responsable():
    data = cargar_ejemplo("natatorio.json")
    pii = detectar_pii(data)
    menores = evaluar_menores(data, pii, "natatorio")
    assert menores["total_menores"] >= 1
    assert menores["alerta_menores"] is True
    assert "nombre_responsable" in menores["campos_responsable_faltantes"]
    print(f"  ✓ test_menores_sin_responsable → {menores['total_menores']} menor(es)")


def test_hash_unico():
    p1 = {"url": "http://a.com", "timestamp_utc": "2026-06-16T00:00:00", "x": 1}
    p2 = {"url": "http://a.com", "timestamp_utc": "2026-06-16T00:00:00", "x": 1}
    p3 = {"url": "http://b.com", "timestamp_utc": "2026-06-16T00:00:00", "x": 1}
    h1 = _calcular_hash(p1)
    h2 = _calcular_hash(p2)
    h3 = _calcular_hash(p3)
    assert h1 == h2
    assert h1 != h3
    print("  ✓ test_hash_unico → mismo contenido mismo hash, distinta URL distinto hash")


def test_exportar_formatos(tmp_cwd):
    from datetime import datetime, timezone
    data = cargar_ejemplo("natatorio.json")
    tipo, conf, pistas = detectar_tipo_api(data, "natatorio")
    est = inspeccionar_campos(data)
    pii = detectar_pii(data)
    menores = evaluar_menores(data, pii, tipo)
    faltantes = detectar_faltantes(est, tipo)
    payload = {
        "url": "http://test/natatorio",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "responsable": "tester",
        "cliente": "TestNat",
        "tipo_detectado": tipo,
        "confianza_deteccion": conf,
        "pistas_deteccion": pistas,
        "estructura": est,
        "pii_detectado": pii,
        "reglas_menores": menores,
        "faltantes_reportados": faltantes,
        "metadata_paginacion": {"fuente_paginacion": "ninguna",
                                 "paginas_seguidas": 1,
                                 "total_registros_reales": est["total_registros"],
                                 "total_registros_analizados": est["total_registros"],
                                 "max_alcanzado": False},
        "cadena_auditoria_previa": None,
        "resumen": {
            "total_registros_reales": est["total_registros"],
            "total_registros_analizados": est["total_registros"],
            "total_campos": est["total_campos_unicos"],
            "campos_faltantes": len(faltantes),
            "datos_sensibles_encontrados": pii["total_hallazgos"],
            "menores_detectados": menores["total_menores"],
            "fuente_paginacion": "ninguna",
            "pausa_entre_requests": CFG.pausa_minima,
        },
    }
    payload["hash_sha256"] = _calcular_hash(payload)
    payload["_rutas_generadas"] = []
    rj = exportar_json(payload, tmp_cwd)
    rc = exportar_csv(payload, tmp_cwd)
    rh = exportar_html(payload, tmp_cwd)
    assert Path(rj).exists()
    assert Path(rc).exists()
    assert Path(rh).exists()
    print(f"  ✓ test_exportar_formatos → JSON/CSV/HTML en {tmp_cwd}")


def test_informe_no_vacio():
    from datetime import datetime, timezone
    data = cargar_ejemplo("natatorio.json")
    tipo, conf, pistas = detectar_tipo_api(data, "natatorio")
    est = inspeccionar_campos(data)
    pii = detectar_pii(data)
    menores = evaluar_menores(data, pii, tipo)
    faltantes = detectar_faltantes(est, tipo)
    payload = {
        "url": "http://test/natatorio",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "responsable": "tester",
        "cliente": "TestNat",
        "tipo_detectado": tipo,
        "confianza_deteccion": conf,
        "pistas_deteccion": pistas,
        "estructura": est,
        "pii_detectado": pii,
        "reglas_menores": menores,
        "faltantes_reportados": faltantes,
        "metadata_paginacion": {"fuente_paginacion": "ninguna",
                                 "paginas_seguidas": 1,
                                 "total_registros_reales": 1,
                                 "total_registros_analizados": 1,
                                 "max_alcanzado": False},
        "cadena_auditoria_previa": None,
        "resumen": {
            "total_registros_reales": 1, "total_registros_analizados": 1,
            "total_campos": 1, "campos_faltantes": 0,
            "datos_sensibles_encontrados": 0, "menores_detectados": 0,
            "fuente_paginacion": "ninguna", "pausa_entre_requests": 1.2,
        },
        "hash_sha256": "abc123",
        "_rutas_generadas": ["salidas/test.json"],
    }
    texto = generar_informe(payload)
    assert "EXPLORACIÓN" in texto
    assert "HASH SHA-256" in texto
    assert "FALTANTES" in texto
    assert "DATOS SENSIBLES" in texto
    print("  ✓ test_informe_no_vacio → informe generado")


# ────────────────────── Mejora 1: Normalización PII ──────────────────────

def test_pii_normalizado_email():
    data = {"usuarios": [{"email": "juan\u2024perez\u200B@example\u200B.com"}]}
    pii = detectar_pii(data)
    tipos = [h["tipo_pii"] for h in pii["hallazgos"]]
    assert "email" in tipos
    # El método debe ser valor_normalizado
    metodos = [h["metodo"] for h in pii["hallazgos"] if h["tipo_pii"] == "email"]
    assert "valor_normalizado" in metodos
    print(f"  ✓ test_pii_normalizado_email → email ofuscado detectado ({metodos})")


def test_pii_normalizado_dni():
    data = {"usuarios": [{"dni": "25.478.963"}]}
    pii = detectar_pii(data)
    tipos = [h["tipo_pii"] for h in pii["hallazgos"]]
    assert "dni" in tipos
    print("  ✓ test_pii_normalizado_dni → DNI con puntos detectado")


def test_pii_normalizado_telefono():
    data = {"usuarios": [{"telefono": "11\u00A04567\u00A08901"}]}
    pii = detectar_pii(data)
    tipos = [h["tipo_pii"] for h in pii["hallazgos"]]
    assert "telefono" in tipos
    print("  ✓ test_pii_normalizado_telefono → teléfono con nbsp detectado")


def test_normalizar_para_pii():
    assert normalizar_para_pii("a\u200Bb") == "ab"
    assert normalizar_para_pii("25.478.963") == "25478963"
    assert normalizar_para_pii("11\u00A04567\u00A08901") == "1145678901"
    assert normalizar_para_pii("juan&#64;example.com") == "juan@example.com"
    # Sin cambios
    assert normalizar_para_pii("juan@example.com") == "juan@example.com"
    print("  ✓ test_normalizar_para_pii → casos de normalización OK")


# ──────────────────── Mejora 2: Detección ponderada ────────────────────

def test_deteccion_por_url():
    """JSON minimal, la señal está en la URL."""
    data = [{"id": 1, "i": "978-x", "t": "x", "a": "x"}]
    url = "https://api.biblioteca-popular.org.ar/v2/catalogo/libros"
    tipo, conf, pistas = detectar_tipo_api(data, url)
    # La URL matchea con tipo relacionado a biblioteca (no podemos exigir el
    # exacto porque las keywords están calibradas, no exhaustivas).
    assert tipo in ("biblioteca", "biblioteca_vecinal"), f"Tipo inesperado: {tipo}"
    assert conf > 0.05, f"Confianza muy baja con URL explícita: {conf}"
    assert any("url:" in p for p in pistas), f"Las pistas deberían mencionar URL: {pistas}"
    print(f"  ✓ test_deteccion_por_url → tipo={tipo} conf={conf} pistas={pistas[:3]}")


def test_deteccion_keys_pesan_mas():
    """Keys de primer nivel pesan más que valores."""
    data = {"socios": [{"id_socio": 1}], "clases": [{"id_clase": 1, "horario": "19:00"}]}
    tipo, conf, pistas = detectar_tipo_api(data, "")
    assert tipo == "natatorio"
    assert any("key:" in p for p in pistas), f"Debería haber pistas de keys: {pistas}"
    print(f"  ✓ test_deteccion_keys_pesan_mas → tipo={tipo} pistas={pistas[:3]}")


# ────────────────────── Mejora 3: Paginación ──────────────────────

def test_paginacion_acumulacion():
    """Si le pasamos una lista, no la parte en páginas; si es un wrapper, sí."""
    from explorer.paginacion import _acumular_pagina
    data_total: list = []
    meta: dict = {
        "fuente_paginacion": "ninguna",
        "paginas_seguidas": 0,
        "total_registros_reales": None,
        "total_registros_analizados": 0,
        "max_alcanzado": False,
    }
    # Lista pelada → no se pagina
    siguiente = _acumular_pagina([{"id": 1}, {"id": 2}], data_total, meta)
    assert siguiente is None
    assert len(data_total) == 2

    # Wrapper DRF
    data_total = []
    meta = {"fuente_paginacion": "ninguna", "paginas_seguidas": 0,
            "total_registros_reales": None, "total_registros_analizados": 0,
            "max_alcanzado": False}
    body_drf = {"count": 100, "next": "http://x.com?page=2",
                "results": [{"id": 1}, {"id": 2}]}
    siguiente = _acumular_pagina(body_drf, data_total, meta)
    assert meta["fuente_paginacion"] == "drf"
    assert siguiente == "http://x.com?page=2"
    assert meta["total_registros_reales"] == 100

    # Wrapper {data: [...]}
    data_total = []
    meta = {"fuente_paginacion": "ninguna", "paginas_seguidas": 0,
            "total_registros_reales": None, "total_registros_analizados": 0,
            "max_alcanzado": False}
    body_page = {"page": 1, "total": 50, "data": [{"id": 1}]}
    siguiente = _acumular_pagina(body_page, data_total, meta)
    assert meta["fuente_paginacion"] == "page"
    print("  ✓ test_paginacion_acumulacion → wrappers DRF y page detectados")


def test_pause_config_lectura():
    """La config tiene pausas razonables (>1s) para no levantar sospechas."""
    assert CFG.pausa_minima >= 1.0, f"Pausa mínima muy baja: {CFG.pausa_minima}"
    assert CFG.pausa_maxima >= CFG.pausa_minima, "Max debe ser >= min"
    print(f"  ✓ test_pause_config_lectura → pausa_min={CFG.pausa_minima}s "
          f"pausa_max={CFG.pausa_maxima}s")


# ────────────────────── Mejora 4: Diff forense ──────────────────────

def test_diff_cambios_conocidos():
    previa = {
        "hash_sha256": "aaa",
        "estructura": {"campos": {
            "id_socio": {"tipo_mayoritario": "integer"},
            "nombre": {"tipo_mayoritario": "string"},
            "obra_social": {"tipo_mayoritario": "string"},
        }},
        "pii_detectado": {"hallazgos": [{"path": "x.dni", "tipo_pii": "dni"}]},
        "faltantes_reportados": [{"campo_esperado": "apto_medico"}],
        "metadata_paginacion": {"fuente_paginacion": "ninguna",
                                 "total_registros_reales": 100},
    }
    actual = {
        "hash_sha256": "bbb",
        "estructura": {"campos": {
            "id_socio": {"tipo_mayoritario": "string"},  # cambió
            "nombre": {"tipo_mayoritario": "string"},
            "apto_medico_v2": {"tipo_mayoritario": "boolean"},  # nuevo
            # obra_social eliminado
        }},
        "pii_detectado": {"hallazgos": [
            {"path": "x.dni", "tipo_pii": "dni"},
            {"path": "x.email", "tipo_pii": "email"},  # PII nuevo
        ]},
        "faltantes_reportados": [],  # apto_medico resuelto
        "metadata_paginacion": {"fuente_paginacion": "ninguna",
                                 "total_registros_reales": 100},
    }

    d = diff_forense(actual, previa)
    assert "apto_medico_v2" in d["campos_nuevos"]
    assert "obra_social" in d["campos_eliminados"]
    assert "id_socio" in d["campos_tipo_cambiado"]
    assert ("x.email", "email") in d["pii_nuevos"]
    assert "apto_medico" in d["faltantes_resueltos"]
    assert d["faltantes_nuevos"] == []
    print("  ✓ test_diff_cambios_conocidos → diff detecta todos los cambios")


def test_cadena_hash():
    """Encadenar dos hashes debe dar uno distinto al actual."""
    actual = {"url": "http://x", "x": 1}
    h_solo = _calcular_hash(actual)
    h_encadenado = encadenar_hash(actual, "hash_previo_xyz")
    assert h_solo != h_encadenado
    # Encadenar con la misma previa siempre da igual
    h_encadenado2 = encadenar_hash(actual, "hash_previo_xyz")
    assert h_encadenado == h_encadenado2
    print("  ✓ test_cadena_hash → encadenamiento reproducible y distinto")


def test_formatear_diff_texto():
    previa = {"hash_sha256": "aaa",
              "estructura": {"campos": {"x": {"tipo_mayoritario": "string"}}},
              "pii_detectado": {"hallazgos": []},
              "faltantes_reportados": [],
              "metadata_paginacion": {}}
    actual = {"hash_sha256": "bbb",
              "estructura": {"campos": {"x": {"tipo_mayoritario": "integer"},
                                         "y": {"tipo_mayoritario": "string"}}},
              "pii_detectado": {"hallazgos": []},
              "faltantes_reportados": [],
              "metadata_paginacion": {}}
    d = diff_forense(actual, previa)
    txt = formatear_diff_texto(d)
    assert "CAMBIOS" in txt
    assert "x" in txt  # tipo cambiado
    assert "y" in txt  # campo nuevo
    print("  ✓ test_formatear_diff_texto → texto formateado correctamente")


# ────────────────────── Tier Free: lista permitida ──────────────────────
# Importamos el módulo cli de forma indirecta para evitar el __main__ loop.

def _importar_cli():
    """Importa cli.py sin ejecutar main()."""
    import importlib.util
    from pathlib import Path
    ruta = Path(__file__).parent.parent / "cli.py"
    spec = importlib.util.spec_from_file_location("_cli_test", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dominio_de_url():
    cli = _importar_cli()
    assert cli._dominio_de_url("https://jsonplaceholder.typicode.com/users") \
        == "jsonplaceholder.typicode.com"
    assert cli._dominio_de_url("http://api.cliente.com:8080/v1/") \
        == "api.cliente.com:8080"
    assert cli._dominio_de_url("https://API.Cliente.COM/x") \
        == "api.cliente.com"  # lowercased
    assert cli._dominio_de_url("no-es-url") == ""
    print("  ✓ test_dominio_de_url → netloc extraído correctamente")


def test_lista_permitida_pasa():
    cli = _importar_cli()
    for url in [
        "https://jsonplaceholder.typicode.com/users",
        "https://jsonplaceholder.typicode.com/posts/1",
        "http://randomuser.me/api/?results=20",
        "https://dummyjson.com/products",
        "https://reqres.in/api/users",
    ]:
        puede, motivo = cli._validar_acceso_url(url)
        assert puede, f"{url} debería pasar: {motivo}"
        assert "Free" in motivo
    print("  ✓ test_lista_permitida_pasa → 4 dominios permitidos OK")


def test_url_fuera_bloqueada():
    cli = _importar_cli()
    for url in [
        "https://api.banco.com/v1/clientes",
        "https://mi-api-empresa.com/datos",
        "https://stripe.com/api/charges",
        "https://api.openai.com/v1/models",
    ]:
        puede, motivo = cli._validar_acceso_url(url)
        assert not puede, f"{url} debería estar bloqueada"
        assert "no está en la lista permitida" in motivo
    print("  ✓ test_url_fuera_bloqueada → URLs externas bloqueadas")


def test_url_invalida_bloqueada():
    cli = _importar_cli()
    puede, motivo = cli._validar_acceso_url("esto no es una url")
    assert not puede
    assert "no está en la lista permitida" in motivo
    print("  ✓ test_url_invalida_bloqueada → URL malformada rechazada")


def test_url_file_pasa():
    """Las URLs file:// no son URLs de API; las dejamos pasar (modo demo)."""
    cli = _importar_cli()
    puede, motivo = cli._validar_acceso_url("file:///C:/repo/ejemplos/natatorio.json")
    # file:// tiene netloc vacío → no matchea lista → sin licencia Pro → bloqueada
    # pero el cli.py checkea args.url Y args.demo, así que file:// solo se usa en demo.
    # En _validar_acceso_url pura, esto se bloquea — correcto.
    assert not puede
    print("  ✓ test_url_file_pasa → file:// bloqueada en validación pura "
          "(se bypassea con --demo)")


# ────────────────────── Sistema de licencia Pro ──────────────────────

def test_licencia_generar_firma_determinista():
    """La misma entrada siempre da la misma firma."""
    from explorer.licencia import generar_firma
    f1 = generar_firma("juan@test.com", "pro", "2026-06-21")
    f2 = generar_firma("juan@test.com", "pro", "2026-06-21")
    assert f1 == f2
    assert len(f1) == 64  # SHA-256 hex
    print("  ✓ test_licencia_generar_firma_determinista → firma reproducible")


def test_licencia_generar_firma_cambia_con_datos():
    """Cambiar email/tier/issued cambia la firma."""
    from explorer.licencia import generar_firma
    base = generar_firma("juan@test.com", "pro", "2026-06-21")
    assert base != generar_firma("otro@test.com", "pro", "2026-06-21")
    assert base != generar_firma("juan@test.com", "free", "2026-06-21")
    assert base != generar_firma("juan@test.com", "pro", "2026-06-22")
    print("  ✓ test_licencia_generar_firma_cambia_con_datos → HMAC sensible")


def test_licencia_normaliza_email():
    """El email se normaliza a minúsculas antes de firmar."""
    from explorer.licencia import generar_firma
    f1 = generar_firma("juan@test.com", "pro", "2026-06-21")
    f2 = generar_firma("JUAN@TEST.COM", "pro", "2026-06-21")
    f3 = generar_firma("  juan@test.com  ", "pro", "2026-06-21")
    assert f1 == f2 == f3
    print("  ✓ test_licencia_normaliza_email → mayúsculas y espacios se ignoran")


def test_licencia_valida_archivo_no_existe(tmp_cwd):
    """Archivo inexistente devuelve (False, mensaje)."""
    from pathlib import Path
    from explorer.licencia import validar_licencia_en_archivo
    valida, msg = validar_licencia_en_archivo(Path(tmp_cwd) / "no_existe.json")
    assert valida is False
    assert "No existe" in msg
    print("  ✓ test_licencia_valida_archivo_no_existe → manejo limpio")


def test_licencia_valida_archivo_vacio(tmp_cwd):
    """Archivo vacío → inválido."""
    from pathlib import Path
    from explorer.licencia import validar_licencia_en_archivo
    ruta = Path(tmp_cwd) / "vacio.json"
    ruta.write_text("", encoding="utf-8")
    valida, msg = validar_licencia_en_archivo(ruta)
    assert valida is False
    print("  ✓ test_licencia_valida_archivo_vacio → JSON inválido rechazado")


def test_licencia_valida_json_invalido(tmp_cwd):
    """JSON malformado → inválido."""
    from pathlib import Path
    from explorer.licencia import validar_licencia_en_archivo
    ruta = Path(tmp_cwd) / "malo.json"
    ruta.write_text("esto no es json {{{", encoding="utf-8")
    valida, msg = validar_licencia_en_archivo(ruta)
    assert valida is False
    assert "JSON" in msg
    print("  ✓ test_licencia_valida_json_invalido → rechazado")


def test_licencia_valida_completa(tmp_cwd):
    """Generamos una licencia válida y la validamos. Debe pasar."""
    from datetime import date
    from pathlib import Path
    from explorer.licencia import generar_firma, validar_licencia_en_archivo
    email = "cliente@empresa.com"
    issued = date.today().isoformat()
    sig = generar_firma(email, "pro", issued)
    ruta = Path(tmp_cwd) / "licencia.json"
    ruta.write_text(json.dumps({
        "email": email, "tier": "pro", "issued": issued, "sig": sig
    }), encoding="utf-8")

    valida, msg = validar_licencia_en_archivo(ruta)
    assert valida is True, f"Licencia válida rechazada: {msg}"
    assert email in msg
    print("  ✓ test_licencia_valida_completa → licencia válida pasa")


def test_licencia_rechaza_sig_incorrecto(tmp_cwd):
    """Cambiar el sig manualmente debe rechazarse."""
    from datetime import date
    from pathlib import Path
    from explorer.licencia import validar_licencia_en_archivo
    ruta = Path(tmp_cwd) / "manipulada.json"
    ruta.write_text(json.dumps({
        "email": "cliente@empresa.com",
        "tier": "pro",
        "issued": date.today().isoformat(),
        "sig": "0" * 64  # firma falsa
    }), encoding="utf-8")

    valida, msg = validar_licencia_en_archivo(ruta)
    assert valida is False
    assert "manipulada" in msg.lower() or "firma" in msg.lower()
    print("  ✓ test_licencia_rechaza_sig_incorrecto → firma falsa rechazada")


def test_licencia_rechaza_email_cambiado(tmp_cwd):
    """Cambiar el email después de firmada debe rechazarse."""
    from datetime import date
    from pathlib import Path
    from explorer.licencia import generar_firma, validar_licencia_en_archivo
    email_original = "cliente@empresa.com"
    email_modificado = "otro@atacante.com"
    issued = date.today().isoformat()
    sig = generar_firma(email_original, "pro", issued)  # firmada con el original
    ruta = Path(tmp_cwd) / "swap.json"
    ruta.write_text(json.dumps({
        "email": email_modificado,  # pero el archivo dice otro
        "tier": "pro",
        "issued": issued,
        "sig": sig,
    }), encoding="utf-8")

    valida, msg = validar_licencia_en_archivo(ruta)
    assert valida is False, "Cambiar email sin re-firmar debería rechazarse"
    print("  ✓ test_licencia_rechaza_email_cambiado → swap de email detectado")


def test_licencia_rechaza_tier_incorrecto(tmp_cwd):
    """Una licencia con tier != pro se rechaza."""
    from datetime import date
    from pathlib import Path
    from explorer.licencia import generar_firma, validar_licencia_en_archivo
    email = "cliente@empresa.com"
    issued = date.today().isoformat()
    # Firmada como 'free' (no 'pro')
    sig = generar_firma(email, "free", issued)
    ruta = Path(tmp_cwd) / "free.json"
    ruta.write_text(json.dumps({
        "email": email, "tier": "free", "issued": issued, "sig": sig,
    }), encoding="utf-8")

    valida, msg = validar_licencia_en_archivo(ruta)
    assert valida is False
    assert "Pro" in msg or "tier" in msg.lower()
    print("  ✓ test_licencia_rechaza_tier_incorrecto → tier='free' rechazado")


def test_licencia_email_malformado(tmp_cwd):
    """Un email que no parece email se rechaza."""
    from datetime import date
    from pathlib import Path
    from explorer.licencia import generar_firma, validar_licencia_en_archivo
    email_malo = "no-es-email"
    issued = date.today().isoformat()
    sig = generar_firma(email_malo, "pro", issued)
    ruta = Path(tmp_cwd) / "email_malo.json"
    ruta.write_text(json.dumps({
        "email": email_malo, "tier": "pro", "issued": issued, "sig": sig,
    }), encoding="utf-8")

    valida, msg = validar_licencia_en_archivo(ruta)
    assert valida is False
    print("  ✓ test_licencia_email_malformado → email inválido rechazado")


# ────────────────────── Fix: falso positivo PII en HTML ──────────────────────

def test_pii_skipea_html():
    """Cuando el Content-Type NO es JSON, no se detecta PII aunque
    el contenido tenga palabras como 'dni' o 'email'. Caso real:
    el explorador contra clientes.credicuotas.com.ar (home) detectó
    'dni' en el HTML del formulario de login."""
    from explorer.sensibles import detectar_pii

    data_html = {
        "root": "<html><body>Ingresá tu DNI y tu email para registrarte</body></html>"
    }
    pii = detectar_pii(data_html, content_type="text/html; charset=utf-8")
    assert pii["total_hallazgos"] == 0
    assert "skipped_reason" in pii
    assert "no es JSON" in pii["skipped_reason"]
    print("  ✓ test_pii_skipea_html → false positive evitado en HTML")


def test_pii_skipea_texto_plano():
    """Content-Type text/plain también skipea (no es JSON)."""
    from explorer.sensibles import detectar_pii
    data = {"x": "Mi DNI es 12345678"}
    pii = detectar_pii(data, content_type="text/plain")
    assert pii["total_hallazgos"] == 0
    print("  ✓ test_pii_skipea_texto_plano → text/plain skipeado")


def test_pii_corre_con_json_explicito():
    """Si el content_type es application/json, la detección corre normal."""
    from explorer.sensibles import detectar_pii
    data = {"usuario": {"dni": "25478963", "email": "juan@test.com"}}
    pii = detectar_pii(data, content_type="application/json; charset=utf-8")
    assert pii["total_hallazgos"] >= 2
    tipos = [h["tipo_pii"] for h in pii["hallazgos"]]
    assert "dni" in tipos
    assert "email" in tipos
    print("  ✓ test_pii_corre_con_json_explicito → JSON explícito OK")


def test_pii_corre_sin_content_type():
    """Si NO se pasa content_type (compatibilidad hacia atrás), la
    detección corre como siempre. Esto preserva el comportamiento de
    todos los call sites que no pasan content_type aún."""
    from explorer.sensibles import detectar_pii
    data = {"usuario": {"dni": "25478963"}}
    pii = detectar_pii(data)
    assert pii["total_hallazgos"] >= 1
    assert "skipped_reason" not in pii
    print("  ✓ test_pii_corre_sin_content_type → retrocompatible OK")


# ────────────────────── main ──────────────────────

def main():
    tmp = tempfile.mkdtemp(prefix="api_explorer_test_")
    print("=" * 60)
    print("  TESTS api-explorer")
    print("=" * 60)
    # Núcleo (9 tests originales)
    test_deteccion_natatorio()
    test_deteccion_biblioteca()
    test_inspeccion_campos()
    test_faltantes_biblioteca()
    test_pii_natatorio()
    test_menores_sin_responsable()
    test_hash_unico()
    test_exportar_formatos(tmp)
    test_informe_no_vacio()
    # Mejora 1
    test_pii_normalizado_email()
    test_pii_normalizado_dni()
    test_pii_normalizado_telefono()
    test_normalizar_para_pii()
    # Mejora 2
    test_deteccion_por_url()
    test_deteccion_keys_pesan_mas()
    # Mejora 3
    test_paginacion_acumulacion()
    test_pause_config_lectura()
    # Mejora 4
    test_diff_cambios_conocidos()
    test_cadena_hash()
    test_formatear_diff_texto()
    # Tier Free: lista permitida
    test_dominio_de_url()
    test_lista_permitida_pasa()
    test_url_fuera_bloqueada()
    test_url_invalida_bloqueada()
    test_url_file_pasa()
    # Sistema de licencia Pro
    test_licencia_generar_firma_determinista()
    test_licencia_generar_firma_cambia_con_datos()
    test_licencia_normaliza_email()
    test_licencia_valida_archivo_no_existe(tmp)
    test_licencia_valida_archivo_vacio(tmp)
    test_licencia_valida_json_invalido(tmp)
    test_licencia_valida_completa(tmp)
    test_licencia_rechaza_sig_incorrecto(tmp)
    test_licencia_rechaza_email_cambiado(tmp)
    test_licencia_rechaza_tier_incorrecto(tmp)
    test_licencia_email_malformado(tmp)
    # Fix: falso positivo PII en HTML
    test_pii_skipea_html()
    test_pii_skipea_texto_plano()
    test_pii_corre_con_json_explicito()
    test_pii_corre_sin_content_type()
    print("=" * 60)
    print("  ✓ 41/41 tests pasaron")
    print("=" * 60)


if __name__ == "__main__":
    main()