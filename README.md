# 🔍 api-inspector

**Herramienta de auditoría forense de migración de datos entre APIs / DBs.**

Pensada para cuando un cliente te dice *"pasame la base a otro sistema"*. Inspeccionás la API una vez, generás un informe firmado con hash SHA-256, y queda registro de qué se vio, qué se omitió, y qué datos sensibles se encontraron.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)
![Tests](https://img.shields.io/badge/tests-9%2F9-success)

---

## ✨ Qué hace

- 🌐 Se conecta a una **URL de API** (sin auth — asumiendo endpoints abiertos tipo API pública de un software open source)
- 🏷️ **Detecta el tipo de sistema** (biblioteca, natatorio, club, música, pelis, hosting, etc.) por palabras clave en el JSON
- 🔬 **Inspecciona la estructura**: tipos de campos inferidos (string, int, float, fecha, email, boolean, null)
- 🔒 **Detecta PII** (datos sensibles): mail, teléfono, DNI, fechas de nacimiento, datos médicos, grupos sanguíneos, obra social
- 👶 **Detecta menores de edad** y avisa si faltan los campos del responsable obligatorio
- 🚨 **Reporta campos faltantes** vs. el patrón esperado del tipo detectado (la "columna roja" de transparencia en la migración)
- 🔐 **Genera informe con hash SHA-256** único por timestamp + URL + contenido + responsable + cliente
- 📦 **Exporta a JSON, CSV y HTML**

---

## 🚀 Quick start

```bash
# Sin instalar nada, solo Python 3.8+
cd api-inspector

# Demo con JSON de ejemplo
python3 cli.py --demo --responsable "Tu Nombre" --cliente "Natatorio Olivos"

# Auditoría real contra una API
python3 cli.py \
    --url "http://api.cliente.com/v1" \
    --responsable "Tu Nombre" \
    --cliente "Cliente X" \
    --formato todos
```

Te deja 3 archivos en `salidas/` por auditoría:
- `auditoria-<timestamp>-<hash8>.json` — datos completos
- `auditoria-<timestamp>-<hash8>.csv` — planilla con secciones
- `auditoria-<timestamp>-<hash8>.html` — informe visual para presentar al cliente

---

## 📋 Uso

### Flags del CLI

| Flag | Descripción | Default |
|------|-------------|---------|
| `--url` | Endpoint a inspeccionar | (requerido o `--demo`) |
| `--responsable` | Quién corre la auditoría (tu nombre) | `no_especificado` |
| `--cliente` | Nombre del cliente dueño de la DB | `no_especificado` |
| `--formato` | `json` / `csv` / `html` / `todos` | `todos` |
| `--salida` | Directorio de salida | `salidas/` |
| `--demo` | Usa el JSON de ejemplo `ejemplos/natatorio.json` | off |

### Ejemplo de salida (consola)

```
══════════════════════════════════════════════════════════════════════
  INFORME DE AUDITORÍA DE MIGRACIÓN DE DATOS
══════════════════════════════════════════════════════════════════════
  URL:              file:///path/ejemplos/natatorio.json
  Fecha (UTC):      2026-06-16T05:33:31.160322+00:00
  Responsable:      Tu Nombre
  Cliente:          Natatorio Olivos
  Tipo detectado:   natatorio  (confianza 0.5)
  Pistas:           natatorio, apto_medico, grupo_sanguineo, horario

  HASH SHA-256:     453adac150a4a0478eb1a01609ba14483449364917e8b973fa82fd5782773eca
══════════════════════════════════════════════════════════════════════
  RESUMEN
══════════════════════════════════════════════════════════════════════
   • Registros:                 6
   • Campos únicos:             14
   • Campos faltantes:          0
   • Datos sensibles (PII):     28
   • Menores detectados:        1

  PII por nivel de sensibilidad:
     🟡 medio: 15
     🟠 alto: 6
     🔴 critico: 7

  ⚠ ALERTA: Se detectaron menores de edad y faltan campos de responsable:
     - nombre_responsable
     - dni_responsable
     - telefono_responsable
     - parentesco
══════════════════════════════════════════════════════════════════════
  CAMPOS FALTANTES (lo que el cliente omitió)
══════════════════════════════════════════════════════════════════════
   [opcional] general.categoria
   [opcional] socio.telefono
   ...
```

---

## 🏷️ Tipos de API detectados (extensibles)

| Tipo | Palabras clave | Datos sensibles típicos |
|------|----------------|------------------------|
| `biblioteca` | libro, socio, prestamo, isbn, autor | nombre, dni, email |
| `biblioteca_vecinal` | libro, socio, barrio, taller | nombre, dni, email, barrio |
| `natatorio` | pileta, natacion, apto_medico, grupo_sanguineo | nombre, dni, fecha_nac, **datos médicos** |
| `club_deportivo` | club, deporte, actividad, cuota, cancha | nombre, dni, email |
| `musica` | track, album, artista, genero | bajo riesgo |
| `peliculas` | pelicula, director, genero, reparto | bajo riesgo |
| `hosting_isp` | dominio, plan, hosting, vencimiento, dns | email, contacto técnico |
| `empresa_sellos` | sello, pedido, cliente, producto | email |

¿Tu cliente tiene un sistema que no está? Solo agregá un bloque a `reglas/patrones_deteccion.json`:

```json
"veterinaria": {
    "palabras_clave": ["mascota", "veterinario", "vacuna", "especie", "raza", "tutor"],
    "campos_esperados": ["id_mascota", "nombre", "especie", "raza", "edad", "tutor"],
    "campos_tutor": ["id_tutor", "nombre", "apellido", "dni", "email", "telefono"],
    "obligatorios_mascota": ["id_mascota", "nombre", "especie", "tutor"],
    "obligatorios_tutor": ["id_tutor", "nombre", "apellido", "dni"]
}
```

Y listo. Cero código nuevo.

---

## 🔐 Modelo de auditoría forense

**Hash SHA-256** sobre el payload completo de la auditoría:

```python
hash = SHA256({
    "url",                          # endpoint inspeccionado
    "timestamp_utc" (con μs),       # cuándo se hizo
    "responsable",                  # quién lo hizo
    "cliente",                      # a quién
    "tipo_detectado",               # qué tipo de sistema
    "confianza_deteccion",          # qué tan seguro fue el match
    "pistas_deteccion",             # por qué se clasificó así
    "estructura",                   # campos encontrados
    "pii_detectado",                # PII hallados
    "reglas_menores",               # evaluación de menores
    "faltantes_reportados",         # lo que el cliente omitió
    "resumen",                      # totales
})
```

Como auditoría nunca corre dos veces en el mismo microsegundo sobre la misma URL+contenido+responsable, el hash es **irrepetible** y **forense**: cualquier edición posterior del informe rompe el hash.

> **Caso típico**: el cliente te dice "no te di el campo `id_user`". Mostrás el hash del informe, la fecha, y queda claro que vos no lo omitiste, él tampoco te lo pasó.

---

## 🧪 Tests

```bash
python3 tests/test_inspector.py
```

9/9 tests pasando. Cubren:

- ✅ Detección de tipo (natatorio, biblioteca)
- ✅ Inspección de campos y tipos inferidos
- ✅ Detección de campos faltantes vs. patrón esperado
- ✅ Detección de PII (médico, contacto, identidad)
- ✅ Reglas de menores + alerta de responsable
- ✅ Hash único y reproducible
- ✅ Exportación a los 3 formatos
- ✅ Generación del informe en texto

---

## 📂 Estructura del proyecto

```
api-inspector/
├── cli.py                       # entry point CLI
├── inspector/                   # 5 módulos del motor
│   ├── core.py                  # conecta + orquesta + hashea
│   ├── detectar.py              # detecta tipo de API
│   ├── campos.py                # inspecciona estructura y faltantes
│   ├── sensibles.py             # detecta PII y evalúa menores
│   ├── exportar.py              # exporta JSON/CSV/HTML
│   └── informe.py               # arma el informe en texto
├── reglas/                      # configuración 100% en JSON
│   ├── patrones_deteccion.json  # vocabulario por tipo de API
│   └── sensibles.json           # regex + lista de campos sensibles
├── ejemplos/                    # 2 JSONs de prueba
│   ├── natatorio.json
│   └── biblioteca.json
├── salidas/                     # auditorías generadas (gitignored)
├── tests/
│   └── test_inspector.py
├── requirements.txt             # vacío — no tiene deps externas
└── README.md
```

---

## 🛣️ Roadmap

- [ ] **Web (Flask)** — formulario donde el cliente mete la URL y descarga el informe HTML firmado
- [ ] **Conectores** — Odoo, WordPress, Django-REST, ERPNext
- [ ] **Regla de consentimiento** — flag si el JSON tiene `consentimiento` o `acepto_terminos`
- [ ] **Firma digital PGP** — opcional, además del hash
- [ ] **Soporte HTML/CSV como input** — además de JSON

---

## 💡 Casos de uso

- **Auditoría de migración**: cliente te pasa la URL → vos inspeccionás → informe firmado para presentarle
- **Pre-flight de import**: antes de cargar una base de datos en otro sistema, verificá qué trae y qué le falta
- **Inventario de datos**: descubrí qué datos sensibles tiene una API que no sabías
- **Compliance**: registro forense de qué se inspeccionó, cuándo, y quién

---

## 🤝 Contribuir

Sumar un nuevo tipo de API es **un JSON nuevo** en `reglas/patrones_deteccion.json`. No hace falta tocar código.

Si querés sumar un conector a un framework (Odoo, WP, etc.), abrí un issue y lo charlamos.

---

## 📜 Licencia

MIT. Hacé lo que quieras, pero no me hago responsable si exportás una base de datos a otro sistema y se rompe 😅 (en serio, **siempre** probá en un ambiente de staging antes de migrar a producción).

---

## ✍️ Autor

Hecho por [Tu Nombre](https://github.com/AlbertiJ) — herramienta forense para auditorías de migración de datos en PyMEs que usan open source.
