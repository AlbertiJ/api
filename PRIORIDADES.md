# 🗺️ Roadmap — api-explorer

> Versión actual: **v0.2.0**
> Estado: refactor de naming + 4 mejoras de `INGENIERIA.md` aplicadas.
> Repo: `AlbertiJ/api` · Licencia: MIT · Stack: Python 3.8+

---

## ✅ Lo que ya está hecho (v0.2.0)

### 1. Refactor de identidad y limpieza

| Cambio | Antes | Ahora |
|---|---|---|
| Nombre del proyecto | `api-inspector` | `api-explorer` |
| Paquete Python | `inspector/` | `explorer/` |
| Entry point | `prog="usuario"` ❌ | `prog="api-explorer"` ✓ |
| Description del CLI | `"Navegador Firefox."` ❌ | `"Explorador de APIs públicas: ..."` ✓ |
| UI web | `Phantom-QA` (cyberpunk) | `API Explorer` (limpio) |
| User-Agent HTTP | Firefox suplantado | `api-explorer/0.2 (+URL repo)` explícito |
| Archivos basura | `README PRUEBAS.txt` | borrado |

**Por qué importó**: el `prog="usuario"` y la `description="Navegador Firefox."` eran copy-paste mal pegado de otro proyecto. Cualquier persona que corriera `--help` lo notaba. Ahora el tool dice lo que es, sin disfrazarse.

### 2. Sistema de pausas anti-rate-limit

Nuevo módulo: `explorer/config.py`

- `pausa_minima` / `pausa_maxima` configurables (default 1.2s / 2.4s).
- `jitter=True` por default → pausa aleatoria entre min y max para no
  ser detectable como bot por patrón temporal.
- Variables de entorno: `APIEXPLORER_PAUSA_MIN`, `APIEXPLORER_PAUSA_MAX`,
  `APIEXPLORER_TIMEOUT`, `APIEXPLORER_MAX_REGS`, `APIEXPLORER_MAX_PAGINAS`.
- Flags CLI para override: `--pausa-min`, `--pausa-max`, `--max-registros`.
- `discovery.py` (fuzzer de endpoints) usa pausas más largas.
- Paginación agrega pausa extra cada 5 páginas.

**Por qué importó**: las APIs modernas (DummyJSON, RandomUser, ReqRes, JSONPlaceholder) están detrás de Cloudflare/Akamai. Cuando el cliente manda ráfagas con `User-Agent` de navegador y timing robótico, devuelven 403/429 antes de los 5 segundos. Con pausas humanas + User-Agent explícito, la auditoría llega a destino y el informe sale completo.

### 3. Las 4 mejoras de `INGENIERIA.md` aplicadas

#### Mejora 1: Normalización PII (`explorer/normalizar.py`)

Antes: si una API mandaba `dni: "25.478.963"` (con puntos) o `email: "juan\u2024perez@example.com"` (con zero-width chars), el detector decía "no hay PII" — el informe salía **engañosamente correcto**.

Ahora: el valor pasa por `_normalizar_para_pii()` antes de la regex:
- Decodifica entidades HTML (`&#64;` → `@`)
- Quita zero-width chars (`\u200B`, `\u200C`, `\uFEFF`, `\u2024`)
- Reemplaza non-breaking spaces por espacio normal
- Quita separadores numéricos visuales entre dígitos

El método del hallazgo indica `valor_directo` o `valor_normalizado` para trazabilidad forense. El valor **original** se preserva en `muestra_truncada`.

#### Mejora 2: Detección ponderada por origen (`explorer/detectar.py`)

Antes: contaba keywords en un corpus plano. Una API minimal con `[{"t": "x"}]` quedaba en `confianza 0.1, tipo: desconocido`.

Ahora: tres fuentes con pesos distintos:
- **Segmentos de URL** (peso 2.0) — la URL es la señal más explícita
- **Keys de primer nivel del JSON** (peso 1.5) — son nombres estables
- **Valores del JSON** (peso 1.0) — ruidosos pero suman

Las pistas ahora dicen de dónde salió cada match: `url:catalogo`, `key:id_socio`, `val:apto_medico`.

#### Mejora 3: Paginación automática (`explorer/paginacion.py`)

Antes: si la API tenía 3000 socios en 60 páginas, analizábamos solo los primeros 200 registros. El hash SHA-256 quedaba firmado sobre una **muestra parcial**, lo cual rompe el modelo forense.

Ahora: detecta 4 estilos de paginación y los sigue:
- **DRF**: `{"count": N, "next": "...", "results": [...]}`
- **Page-based**: `{"page": N, "total": T, "data": [...]}`
- **Generic cursor**: `{"next": "..."}` o `{"next_cursor": "..."}`
- **GitHub-style**: header `Link: <url>; rel="next"`

Tope absoluto: `CFG.max_registros` (default 5000) y `CFG.max_paginas` (default 50). El informe ahora reporta `total_registros_reales` vs `total_registros_analizados` para ser honesto sobre la cobertura.

#### Mejora 4: Diff forense entre exploraciones (`explorer/diff.py`)

Antes: si el cliente evolucionaba su API, no había forma de saber qué cambió entre dos exploraciones — había que abrir los dos JSON a ojo.

Ahora: nuevo módulo con tres funciones:
- `diff_forense(actual, previa)` → devuelve `campos_nuevos`, `campos_eliminados`, `campos_tipo_cambiado`, `pii_nuevos`, `pii_eliminados`, `faltantes_resueltos`, `faltantes_nuevos`, `cambios_paginacion`.
- `encadenar_hash(actual, hash_previo)` → hash SHA-256 que incorpora el hash anterior para detectar manipulación de la cadena forense.
- `formatear_diff_texto(diff)` → versión legible para consola.

Activación desde CLI: `python cli.py --url https://api.example.com --diff-con salidas/vieja.json`.

### 4. Cobertura de tests: 9/9 → 21/21

```
TESTS api-explorer
  ✓ test_deteccion_natatorio
  ✓ test_deteccion_biblioteca
  ✓ test_inspeccion_campos
  ✓ test_faltantes_biblioteca
  ✓ test_pii_natatorio
  ✓ test_menores_sin_responsable
  ✓ test_hash_unico
  ✓ test_exportar_formatos
  ✓ test_informe_no_vacio
  ✓ test_pii_normalizado_email
  ✓ test_pii_normalizado_dni
  ✓ test_pii_normalizado_telefono
  ✓ test_normalizar_para_pii
  ✓ test_deteccion_por_url
  ✓ test_deteccion_keys_pesan_mas
  ✓ test_paginacion_acumulacion
  ✓ test_pause_config_lectura
  ✓ test_diff_cambios_conocidos
  ✓ test_cadena_hash
  ✓ test_formatear_diff_texto
  ✓ 21/21 tests pasaron
```

### 5. CLI refactorizado

```bash
# Demo offline
python cli.py --demo

# Exploración real
python cli.py --url https://api.example.com --responsable "Juan" --cliente "Cliente X"

# Formato específico
python cli.py --url https://api.example.com --formato html

# Diff con exploración previa
python cli.py --url https://api.example.com --diff-con salidas/vieja.json

# Ajustar ritmo
python cli.py --url https://api.example.com --pausa-min 2.0 --pausa-max 4.0

# Override del tope de registros
python cli.py --url https://api.example.com --max-registros 10000
```

---

## 🎯 Próximas prioridades

Ordenadas por impacto / esfuerzo. La idea es que cada bloque sea
**entregable solo** (se puede parar después de cualquier bloque y
el proyecto sigue funcionando).

### 🔴 P0 — Crítico, hacerlo primero (1-2 semanas)

#### P0.1. Publicar v0.2.0 en GitHub

- Commit con mensaje claro del refactor + mejoras.
- Tag `v0.2.0`.
- Actualizar la descripción del repo en GitHub.
- Actualizar el README principal (ya hecho localmente, falta commit).
- Limpiar las salidas viejas (`salidas/auditoria-20260617-*`) — son
  de cuando el tool se llamaba distinto.

**Por qué importa**: ahora mismo el repo público dice v0.1.0 pero el
código es v0.2.0 con un gap visible para cualquiera que lo clone.

#### P0.2. Validar contra las 4 APIs públicas

Correr el explorador contra:
1. `https://dummyjson.com` — verificar que la paginación DRF sigue al cursor
2. `https://randomuser.me/api/` — verificar que la normalización PII
   detecta emails con caracteres raros (RandomUser a veces los manda)
3. `https://jsonplaceholder.typicode.com` — verificar que no rompe
   con APIs que NO paginan
4. `https://reqres.in` — verificar que el diff detecta los cambios
   entre dos corridas

**Por qué importa**: los tests con archivos locales prueban el motor.
Los tests contra APIs reales prueban el ritmo, la evasión de WAF y la
resilencia.

### 🟠 P1 — Importante (2-4 semanas)

#### P1.1. Salidas legibles para clientes no técnicos

El HTML actual es funcional pero árido. Mejoras concretas:
- Gráfico de barras con distribución de tipos de campo.
- Sección "Campos con datos sensibles" filtrable.
- Modo "informe ejecutivo" (1 página, sin jerga).
- Modo "informe técnico" (todo el detalle).

**Por qué importa**: si vendés esto como gig de Fiverr, el HTML es
lo que el cliente ve primero. Tiene que poder reenviarlo por mail
sin pedir explicaciones.

#### P1.2. Caché de respuestas y modo "exploración silenciosa"

- Guardar cada respuesta en `cache/<hash_url>.json`.
- Si el hash es el mismo, no volver a pegar.
- Modo `--offline` que solo lee de caché.
- TTL configurable (default 24h).

**Por qué importa**: para un cliente con 20 endpoints, no querés
volver a pegarle a la API cada vez que abrís el informe. Y para
auditar sin tocar la API (modo "foto histórica"), es indispensable.

#### P1.3. Más patrones de detección (`reglas/patrones_deteccion.json`)

Hoy hay 8 tipos (biblioteca, natatorio, club, música, películas,
hosting, empresa_sellos, biblioteca_vecinal). Faltan:
- `salud`: clínicas, sanatorios, obras sociales
- `educacion`: escuelas, universidades, campus virtual
- `gobierno`: APIs públicas de municipios / ministerios
- `fintech`: cuentas corrientes, transferencias, CBU
- `ecommerce`: carritos, órdenes, productos, categorías
- `inmobiliaria`: propiedades, contratos, alquileres

**Por qué importa**: cada tipo nuevo es una línea deKeywords + un
conjunto de `campos_esperados`. Es trabajo repetitivo pero
multiplica el alcance del tool.

### 🟡 P2 — Deseable (1-2 meses)

#### P2.1. UI web con auth y guardado de corridas

La `app.py` actual es local, sin auth, sin persistencia. Para
ofrecer el servicio:
- Login con email + magic link (sin passwords).
- Cada exploración queda guardada con su diff histórico.
- El cliente puede volver a ver sus informes sin reinstalar nada.
- Deploy en Fly.io / Render / Railway (todos tienen tier free).

**Por qué importa**: es la diferencia entre "herramienta para mí"
y "producto para vender". Esta es la base del Fiverr gig de $80-250.

#### P2.2. Soporte para GraphQL

Hoy solo JSON sobre REST. GraphQL necesita:
- Parser de queries (enviar la query como POST body).
- Introspección del schema (`__schema`).
- Walking recursivo de tipos y campos.

**Por qué importa**: las APIs modernas son cada vez más GraphQL.
Quedarse solo en REST te deja afuera de medio mercado.

#### P2.3. Detección de errores estructurales

Hoy decimos "faltan X campos". Falta decir:
- "el campo Y cambió de tipo entre v1 y v2".
- "hay un campo Z que solo aparece en el 5% de los registros".
- "los registros están ordenados distinto entre páginas".

**Por qué importa**: para un cliente migrando entre dos sistemas,
el "qué cambió" es más útil que el "qué falta".

### 🟢 P3 — Largo plazo (cuando haya tracción)

#### P3.1. Plugin de Postman / Insomnia

Que el explorador pueda leer una colección de Postman existente
y usarla como punto de partida en vez de tener que inventar URLs.

#### P3.2. Integración con OpenAPI / Swagger

Si la API tiene `openapi.json`, leerla y comparar contra lo que
devuelve en realidad. Detectar drift documentación ↔ realidad.

#### P3.3. Reporte de compliance (GDPR, CCPA, Ley 25.326 Argentina)

Mapeo explícito: "este campo es PII bajo GDPR artículo 4",
"este sistema necesita consentimiento explícito", etc.

---

## 🧭 Decisiones pendientes

Cosas que dejé abiertas a propósito. Decime cuál preferís y las aplico:

### D1. Nombre del repo en GitHub

Sigue siendo `api`. ¿Querés que se llame `api-explorer`?
- **Pro de renombrar**: URL pública más descriptiva, mejor SEO.
- **Contra**: rompe links existentes, hay que avisar.

### D2. CLI flags

Hoy: `--pausa-min`, `--pausa-max`, `--max-registros`.
Alternativa: `--ritmo humano|rapido` (preset en lugar de 3 flags).
- **Pro del preset**: más simple, menos docs.
- **Contra**: menos flexible.

### D3. Output HTML

Estilo actual: limpio, monocromo, tipo Apple.
Alternativa: oscuro, con badges, tipo "console cyberpunk".
- **Pro oscuro**: más "técnico", más impactante visualmente.
- **Pro monocromo**: más serio, más vendible a empresas.

### D4. Distribución

PyPI (`pip install api-explorer`) vs solo GitHub.
- **Pro PyPI**: `pip install` es la puerta de entrada standard.
- **Contra PyPI**: hay que mantener versiones, CI, etc.

---

## 📌 Cómo seguir

1. Validar v0.2.0 localmente: `python tests/test_explorer.py` → 21/21 OK.
2. Probar el demo: `python cli.py --demo`.
3. Probar contra una API real de la lista: `python cli.py --url https://jsonplaceholder.typicode.com/users`.
4. Decidir las prioridades de P0 (publicar ya vs validar más).
5. Cuando esté publicado, conectar con el Fiverr gig de auditoría forense.

---

_Mantenido por Juan Alberti — generado el 2026-06-19._