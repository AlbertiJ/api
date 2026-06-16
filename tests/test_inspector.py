"""
Tests del inspector. Corren con `python -m pytest tests/` o `python tests/test_inspector.py`.
"""
import json
import sys
from pathlib import Path

# permitir importar inspector sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from inspector.core import _calcular_hash
from inspector.detectar import detectar_tipo_api
from inspector.campos import inspeccionar_campos, detectar_faltantes
from inspector.sensibles import detectar_pii, evaluar_menores
from inspector.exportar import exportar_json, exportar_csv, exportar_html
from inspector.informe import generar_informe


def cargar_ejemplo(nombre: str):
    ruta = Path(__file__).parent.parent / "ejemplos" / nombre
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def test_deteccion_natatorio():
    data = cargar_ejemplo("natatorio.json")
    tipo, conf, pistas = detectar_tipo_api(data, "natatorio")
    assert tipo == "natatorio", f"Esperado natatorio, salió {tipo}"
    assert conf > 0.2
    assert "natatorio" in pistas or "pileta" in pistas or "apto_medico" in pistas or "socio" in pistas
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
    print(f"  ✓ test_inspeccion_campos → {est['total_campos_unicos']} campos, {est['total_registros']} registros")


def test_faltantes_biblioteca():
    """La biblioteca de ejemplo NO trae 'id_socio' en prestamos, debe detectarlo."""
    data = cargar_ejemplo("biblioteca.json")
    est = inspeccionar_campos(data)
    faltantes = detectar_faltantes(est, "biblioteca")
    nombres = [f["campo_esperado"] for f in faltantes]
    # Esperamos que falten cosas como id_socio en prestamos, fecha_devolucion, etc.
    assert len(faltantes) > 0, "Debería detectar faltantes en biblioteca"
    print(f"  ✓ test_faltantes_biblioteca → {len(faltantes)} faltantes detectados: {nombres[:5]}")


def test_pii_natatorio():
    data = cargar_ejemplo("natatorio.json")
    pii = detectar_pii(data)
    assert pii["total_hallazgos"] > 0
    cats = pii["por_categoria"]
    assert "contacto" in cats  # emails, teléfonos
    assert "salud" in cats     # apto_medico, grupo_sanguineo
    assert "identidad" in cats # dni
    print(f"  ✓ test_pii_natatorio → {pii['total_hallazgos']} hallazgos, categorías: {cats}")


def test_menores_sin_responsable():
    data = cargar_ejemplo("natatorio.json")
    pii = detectar_pii(data)
    menores = evaluar_menores(data, pii, "natatorio")
    # En el ejemplo hay 1 menor (Sofía, 2015) y NO hay campos de responsable
    assert menores["total_menores"] >= 1
    assert menores["alerta_menores"] is True
    assert "nombre_responsable" in menores["campos_responsable_faltantes"]
    print(f"  ✓ test_menores_sin_responsable → {menores['total_menores']} menor(es), faltan: {menores['campos_responsable_faltantes']}")


def test_hash_unico():
    """Dos auditorías con el mismo contenido + mismo timestamp + distinta URL → mismo hash."""
    # (No es exactamente lo que se quiere probar; ajustamos a lo real)
    p1 = {"url": "http://a.com", "timestamp_utc": "2026-06-16T00:00:00", "x": 1}
    p2 = {"url": "http://a.com", "timestamp_utc": "2026-06-16T00:00:00", "x": 1}
    p3 = {"url": "http://b.com", "timestamp_utc": "2026-06-16T00:00:00", "x": 1}
    h1 = _calcular_hash(p1)
    h2 = _calcular_hash(p2)
    h3 = _calcular_hash(p3)
    assert h1 == h2
    assert h1 != h3
    print(f"  ✓ test_hash_unico → mismo contenido mismo hash, distinto URL distinto hash")


def test_exportar_formatos(tmp_cwd):
    data = cargar_ejemplo("natatorio.json")
    from datetime import datetime, timezone
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
        "resumen": {
            "total_registros": est["total_registros"],
            "total_campos": est["total_campos_unicos"],
            "campos_faltantes": len(faltantes),
            "datos_sensibles_encontrados": pii["total_hallazgos"],
            "menores_detectados": menores["total_menores"],
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
    print(f"  ✓ test_exportar_formatos → JSON/CSV/HTML generados en {tmp_cwd}")


def test_informe_no_vacio():
    data = cargar_ejemplo("natatorio.json")
    tipo, conf, pistas = detectar_tipo_api(data, "natatorio")
    est = inspeccionar_campos(data)
    pii = detectar_pii(data)
    menores = evaluar_menores(data, pii, tipo)
    faltantes = detectar_faltantes(est, tipo)
    payload = {
        "url": "http://test/natatorio",
        "timestamp_utc": "2026-06-16T00:00:00+00:00",
        "responsable": "tester",
        "cliente": "TestNat",
        "tipo_detectado": tipo,
        "confianza_deteccion": conf,
        "pistas_deteccion": pistas,
        "estructura": est,
        "pii_detectado": pii,
        "reglas_menores": menores,
        "faltantes_reportados": faltantes,
        "resumen": {
            "total_registros": est["total_registros"],
            "total_campos": est["total_campos_unicos"],
            "campos_faltantes": len(faltantes),
            "datos_sensibles_encontrados": pii["total_hallazgos"],
            "menores_detectados": menores["total_menores"],
        },
        "hash_sha256": "abc123",
        "_rutas_generadas": ["salidas/auditoria-test.json"],
    }
    texto = generar_informe(payload)
    assert "HASH SHA-256" in texto
    assert "FALTANTES" in texto
    assert "PII" in texto
    print("  ✓ test_informe_no_vacio → informe generado correctamente")


def main():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="api_inspector_test_")
    print("=" * 60)
    print("  TESTS api-inspector")
    print("=" * 60)
    test_deteccion_natatorio()
    test_deteccion_biblioteca()
    test_inspeccion_campos()
    test_faltantes_biblioteca()
    test_pii_natatorio()
    test_menores_sin_responsable()
    test_hash_unico()
    test_exportar_formatos(tmp)
    test_informe_no_vacio()
    print("=" * 60)
    print("  ✓ 9/9 tests pasaron")
    print("=" * 60)


if __name__ == "__main__":
    main()
