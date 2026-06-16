# 🛠️ Análisis de Ingeniería — api-inspector v0.1.0

> **Auditor forense de migración de datos entre APIs/DBs**
> Repo: `AlbertiJ/api` · Estado: v0.1.0 publicado · Licencia: MIT
> Stack: Python 3.8+ stdlib puro (cero dependencias externas)
> LOC: 808 líneas en 6 módulos + 2 JSON de reglas + 2 JSON de ejemplo + tests

---

## 1. Resumen ejecutivo

`api-inspector` es una herramienta CLI que recibe una URL de API, descarga su contenido, detecta qué tipo de sistema es (biblioteca, natatorio, club, etc.), inspecciona la estructura de campos, identifica datos sensibles (PII), evalúa reglas de menores de edad, reporta campos faltantes contra un patrón esperado, y emite un informe firmado con hash SHA-256 exportable a JSON, CSV y HTML.

**Caso de uso central**: cuando un cliente PyME con software open source te pide migrar su base a otro sistema, vos auditas la API una vez, generás un informe firmado, y queda registro forense de qué se inspeccionó, qué se omitió y qué datos sensibles había.

**Fortalezas del diseño actual**:
- 100% stdlib: corre en cualquier Python 3.8+ sin `pip install`
- Configuración 100% en JSON: agregar un tipo de API nuevo es un archivo, no código
- Hash SHA-256 sobre el payload completo: prueba forense irrepetible
- Separación clara: `core` (motor) / `detectar` / `campos` / `sensibles` / `exportar` / `informe`

**Deuda técnica identificada**: 4 dimensiones con margen claro de mejora.

---

## 2. Arquitectura actual (as-is)

```
┌────────────┐
│   cli.py   │  argparse + modo --demo
└─────┬──────┘
      │
      ▼
┌────────────────────────────────────────────────┐
│              inspector/core.py                  │
│   _descargar → detectar → inspeccionar →       │
│   detectar_pii → evaluar_menores → detectar_   │
│   faltantes → calcular_hash → exportar         │
└──────┬──────────┬──────────┬──────────┬────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
   detectar   campos    sensibles   exportar (JSON/CSV/HTML)
       │          │          │
       ▼          ▼          ▼
   ┌──────────────────────────────────┐
   │   reglas/patrones_deteccion.json │
   │   reglas/sensibles.json          │
   └──────────────────────────────────┘
```

**Flujo de datos**:
1. `cli.py` recibe URL/flags → llama a `inspeccionar()`
2. `core.py` descarga → orquesta 5 análisis
3. Cada análisis vuelca sus hallazgos a un dict `payload_auditoria`
4. `core.py` calcula hash SHA-256 sobre ese dict canónico
5. `exportar.py` serializa a 3 formatos
6. `informe.py` arma el texto para consola

---

## 3. Las 4 mejoras priorizadas

Para cada una: descripción → código actual → escenario de falla → mejora propuesta → cómo se verifica que funciona.

---

### 🔧 MEJORA 1: Evasión de PII por codificación / ofuscación

#### Descripción
El detector de PII actual usa regex fijas sobre el string crudo del valor. Si un cliente intencionalmente (o por bug de su sistema) envía datos sensibles ofuscados, **no los detectamos** y el informe los marca como "no sensibles". Eso es un agujero forense grave.

#### Código actual (`inspector/sensibles.py`, líneas 90-100)

```python
for nombre_patron, cfg in patrones.items():
    regex = cfg.get("regex", "")
    if re.search(regex, valor, re.IGNORECASE):
        hallazgos.append({...})
```

**Problema**: la regex corre sobre el string tal cual llega. Si el valor tiene espacios, separadores unicode invisibles, o el cliente lo manda codificado, se nos pasa.

#### Escenario de falla (PASO 1)

```json
{
  "socios": [
    {
      "nombre": "Juan",
      "email": "juan\u2024perez\u200B@example\u200B.com",
      "dni": "25.478.963",
      "telefono": "11\u00A04567\u00A08901"
    }
  ]
}
```

Resultado con el código actual:
- ✗ `email` no matchea `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` por los caracteres invisibles (`\u2024`, `\u200B`)
- ✗ `dni` no matchea `\b\d{7,8}\b` por los puntos como separadores de miles
- ✗ `telefono` no matchea la regex actual por los `\u00A0` (non-breaking spaces)

**Conclusión del fallo**: el inspector dice "no hay PII" cuando en realidad hay 3 campos sensibles. El informe firmado es técnicamente correcto pero **engañoso**. Eso rompe el modelo forense.

#### Mejora propuesta (PASO 2)

1. **Función de normalización previa** al regex matching:
   - Decodificar HTML entities (`&#64;` → `@`)
   - Quitar zero-width characters (`\u200B`, `\u200C`, `\u200D`, `\uFEFF`)
   - Reemplazar non-breaking space (`\u00A0`) por espacio normal
   - Quitar separadores visuales de números (`25.478.963` → `25478963`, `25 478 963` → `25478963`)
2. **Aplicar normalización** antes de pasar el valor a la regex
3. **Mantener el valor original** en el reporte (para trazabilidad)
4. **Marcar el hallazgo con flag `metodo: "regex_normalizado"`** para distinguirlo del match directo

#### Código de la mejora

```python
# inspector/sensibles.py — agregar función

import html
import unicodedata

def _normalizar_para_pii(valor: str) -> str:
    """Normaliza un valor para que las regex de PII matcheen
    aún si el cliente usó ofuscación visual."""
    if not isinstance(valor, str):
        return valor
    s = html.unescape(valor)
    # Quitar zero-width chars
    s = re.sub(r'[\u200B-\u200D\uFEFF\u2024\u2025]', '', s)
    # Reemplazar non-breaking space y similares por espacio normal
    s = re.sub(r'[\u00A0\u2000-\u200A\u2028\u2029]', ' ', s)
    # Quitar separadores visuales de números (puntos, espacios, comas)
    # solo si están entre dígitos
    s = re.sub(r'(?<=\d)[\s.,\-_]+(?=\d)', '', s)
    return s
```

Y en el bucle principal:

```python
valor_original = valor
valor = _normalizar_para_pii(valor)
metodo = "regex_valor"
if valor != valor_original:
    metodo = "regex_valor_normalizado"

if re.search(regex, valor, re.IGNORECASE):
    hallazgos.append({
        "path": path,
        "campo": nombre_campo,
        "tipo_pii": nombre_patron,
        "categoria": cfg.get("categoria", "desconocida"),
        "nivel_sensibilidad": cfg.get("nivel_sensibilidad", "medio"),
        "metodo": metodo,
        "muestra_truncada": (valor_original[:30] + "...") if len(valor_original) > 30 else valor_original,
    })
```

#### Test que verifica (PASO 3)

```python
def test_pii_normalizado():
    """Datos sensibles ofuscados deben detectarse igual."""
    data = {
        "socios": [{
            "nombre": "Juan",
            "email": "juan\u2024perez\u200B@example\u200B.com",
            "dni": "25.478.963",
            "telefono": "11\u00A04567\u00A08901"
        }]
    }
    pii = detectar_pii(data)
    # Debe detectar los 3
    tipos = [h["tipo_pii"] for h in pii["hallazgos"]]
    assert "email" in tipos, f"Email ofuscado no detectado: {pii}"
    assert "dni" in tipos, f"DNI con puntos no detectado: {pii}"
    assert "telefono" in tipos, f"Teléfono con non-breaking space no detectado: {pii}"
```

#### Criterio de cierre (PASO 4)

✅ Test pasa con datos ofuscados
✅ El método del hallazgo indica "regex_valor_normalizado" cuando hubo normalización
✅ El valor original se preserva en `muestra_truncada`
✅ Los 9 tests previos siguen pasando

---

### 🔧 MEJORA 2: Detección de tipo de API basada en el path / URL, no solo en keywords

#### Descripción
El detector actual (`inspector/detectar.py`) busca keywords en el JSON. Eso falla cuando:
- La API devuelve un wrapper tipo `{"data": [...]}` sin keys que matcheen
- El path de la URL es muy explícito (`/api/v1/socios/natatorio`) y la palabra clave está ahí, no en el JSON
- La API es minimal y devuelve un array pelado `[{"id": 1, ...}]`

#### Código actual (`inspector/detectar.py`, líneas 30-50)

```python
def detectar_tipo_api(data, url=""):
    corpus = " ".join(_aplanar(data)) + " " + url.lower()
    ...
    for tipo, cfg in patrones.items():
        palabras = cfg.get("palabras_clave", [])
        matches = [p for p in palabras if re.search(rf"\b{re.escape(p)}\b", corpus)]
```

**Problema**: si la URL es `https://api.micliente.com/v1/socios/natacion/horarios` y el JSON es `{"records": [{"id": 1, "h": "19:00"}]}` → el corpus tiene "natacion" pero `_aplanar(data)` no aporta nada distintivo. La confianza queda muy baja.

#### Escenario de falla (PASO 1)

```json
GET https://api.biblioteca-sanmartin.gov.ar/v2/catalogo/libros
```

```json
[
  {"id": 1, "i": "978-950-07-1234-5", "t": "El Aleph", "a": "Borges"},
  {"id": 2, "i": "978-950-07-5678-9", "t": "Rayuela", "a": "Cortázar"}
]
```

Con el código actual:
- Las keywords `titulo`, `autor` no están (el JSON usa `t`, `a`, `i`)
- Solo `libro` aparece en la URL
- Resultado: confianza ≈ 0.1, tipo detectado = `biblioteca` pero con confianza inútil

**Conclusión del fallo**: el auditor dice "no sé bien qué es esto, confianza 0.1", y el operador humano tiene que adivinar. Si la URL hubiera sido `https://api.micliente.com/v1/animales/veterinaria`, el patrón `biblioteca` no se activaría y se iría a `desconocido`.

#### Mejora propuesta (PASO 2)

1. **Scoring ponderado por fuente**:
   - Match en URL: peso 2.0
   - Match en keys de primer nivel del JSON: peso 1.5
   - Match en valores del JSON: peso 1.0
2. **Normalización de path**: dividir la URL por `/` y `-`, `\_`, y tomar cada segmento como candidato
3. **Detección por "sufijo de dominio"**: si la URL es `*.edu.ar` o `*.gob.ar`, sumar bonus de confianza a "biblioteca" o "club"
4. **Threshold adaptativo**: si no se llega a 0.3, mostrar los top 3 candidatos en el informe como "posibles tipos"

#### Código de la mejora

```python
# inspector/detectar.py

def _segmentos_url(url: str) -> List[str]:
    """Divide una URL en segmentos normalizados para búsqueda."""
    # Ej: https://api.biblioteca.com.ar/v1/socios/natacion → [biblioteca, com, ar, v1, socios, natacion]
    path = url.split("://", 1)[-1]
    path = re.sub(r'[/\-_.?&=]', ' ', path)
    return [p for p in path.lower().split() if len(p) > 2]

def detectar_tipo_api(data, url="") -> Tuple[str, float, List[str]]:
    patrones = _cargar_patrones()
    segmentos = set(_segmentos_url(url))
    
    # Aplanar solo keys de primer nivel (peso alto) y valores (peso bajo)
    keys_top = set()
    valores = []
    if isinstance(data, dict):
        keys_top = {str(k).lower() for k in data.keys() if isinstance(k, str)}
        for v in data.values():
            if isinstance(v, list):
                for item in v[:20]:
                    if isinstance(item, dict):
                        keys_top.update(str(k).lower() for k in item.keys() if isinstance(k, str))
                        for vv in item.values():
                            valores.append(str(vv).lower())
    elif isinstance(data, list):
        for item in data[:20]:
            if isinstance(item, dict):
                keys_top.update(str(k).lower() for k in item.keys() if isinstance(k, str))
                for v in item.values():
                    valores.append(str(v).lower())
    
    resultados = []
    for tipo, cfg in patrones.items():
        palabras = cfg.get("palabras_clave", [])
        score = 0.0
        matches = []
        for p in palabras:
            if p in segmentos:
                score += 2.0
                matches.append(f"url:{p}")
            elif p in keys_top:
                score += 1.5
                matches.append(f"key:{p}")
            elif any(p in v for v in valores if len(v) < 80):
                score += 1.0
                matches.append(f"val:{p}")
        
        if matches:
            # normalizar a 0-1
            score_norm = min(score / (len(palabras) * 1.5), 1.0)
            resultados.append((tipo, round(score_norm, 2), matches))
    
    if not resultados:
        return ("desconocido", 0.0, [])
    
    resultados.sort(key=lambda x: x[1], reverse=True)
    return resultados[0]
```

#### Test que verifica (PASO 3)

```python
def test_deteccion_por_url():
    """El path de la URL debe pesar en la detección."""
    # JSON minimal, la señal está en la URL
    data = [{"id": 1, "i": "978-x", "t": "x", "a": "x"}]
    url = "https://api.biblioteca-popular.org.ar/v2/catalogo/libros"
    tipo, conf, pistas = detectar_tipo_api(data, url)
    assert tipo == "biblioteca"
    assert conf > 0.3, f"Confianza muy baja con URL explícita: {conf}"
    assert any("url:" in p for p in pistas), f"Las pistas deberían mencionar URL: {pistas}"


def test_deteccion_keys_top():
    """Keys de primer nivel pesan más que valores."""
    data = {"socios": [{"id_socio": 1}], "clases": [{"id_clase": 1, "horario": "19:00"}]}
    tipo, conf, pistas = detectar_tipo_api(data, "")
    assert tipo == "natatorio"
    assert any("key:" in p for p in pistas)
```

#### Criterio de cierre (PASO 4)

✅ Test pasa con JSON minimal + URL explícita
✅ Test pasa con keys de primer nivel
✅ Los 9 tests previos siguen pasando
✅ El output del CLI ahora muestra en `pistas_deteccion` el origen del match: `url:natacion`, `key:id_socio`, `val:apto_medico`

---

### 🔧 MEJORA 3: Robustez ante APIs que devuelven paginación o respuestas grandes

#### Descripción
El inspector actual (`inspector/campos.py` y `core.py`) tiene un cap de 200 muestras por lista. Si una API devuelve 50.000 registros, **no los analizamos todos** y el muestreo puede no ser representativo. Además, **no seguimos links de paginación**, así que solo vemos la primera página.

#### Código actual (`inspector/campos.py`, línea 35-40)

```python
if isinstance(data, list):
    total_registros = len(data)
    for item in data[:200]:  # sample para no matar memoria
```

**Problemas**:
1. Si la API tiene 50.000 socios, analizamos los primeros 200. Si el campo `apto_medico` solo aparece en los últimos 100, **no lo detectamos**.
2. Si la API es de GitHub-style con `Link: <next>; rel="next"`, no seguimos el next.
3. El `total_registros` que reportamos es el de la primera página, no el real.

#### Escenario de falla (PASO 1)

```json
GET https://api.natatorio.com/v1/socios
```

```json
{
  "page": 1,
  "per_page": 50,
  "total": 3000,
  "data": [
    {"id_socio": 1, "nombre": "A", "apto_medico": true},
    ...
  ]
}
```

- Header: `Link: <https://api.natatorio.com/v1/socios?page=2>; rel="next"`

Con el código actual:
- Solo vemos 50 registros
- `total_registros` se reporta como 50 (engañoso)
- Los IDs 51-3000 nunca se inspeccionan
- Si el campo `obra_social` solo aparece en socios con ID > 2500, **no lo registramos como esperado**

**Conclusión del fallo**: el hash SHA-256 se calcula sobre un muestreo parcial. El informe dice "3000 socios" pero solo se inspeccionaron 50. Riesgo legal: el cliente podría argumentar que la auditoría no fue exhaustiva.

#### Mejora propuesta (PASO 2)

1. **Detectar paginación automáticamente**:
   - **Cursor-based**: si hay `next_cursor` o `Link: <...>; rel="next"`, seguir el link
   - **Page-based**: si hay `page` y `total` o `total_pages`, iterar hasta el final
   - **Offset/limit**: si hay `offset` y `limit` con `total`, iterar
2. **Cap configurable** de registros totales a inspeccionar (default 5000) para no DoS-ear APIs
3. **Reportar en el informe**:
   - `total_registros_reales` (de la paginación)
   - `total_registros_analizados` (cap o menos)
   - `fuente_paginacion: "cursor" | "page" | "ninguna"`
4. **Acumular muestras globalmente** en vez de cortar a 200

#### Código de la mejora

```python
# inspector/core.py — nueva función

def _descargar_paginado(url: str, max_total: int = 5000) -> Tuple[Any, Dict]:
    """Descarga la URL siguiendo paginación. Devuelve (data_acumulada, metadata_paginacion)."""
    data_total = []
    meta = {
        "fuente_paginacion": "ninguna",
        "total_registros_reales": None,
        "total_registros_analizados": 0,
        "paginas_seguidas": 0,
        "max_alcanzado": False,
    }
    
    siguiente_url = url
    headers = {"User-Agent": "API-Inspector/1.0"}
    
    while siguiente_url and meta["total_registros_analizados"] < max_total:
        try:
            req = Request(siguiente_url, headers=headers)
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()
                link_header = resp.headers.get("Link", "")
                content_type = resp.headers.get("Content-Type", "")
        except (URLError, HTTPError, socket.timeout) as e:
            break
        
        try:
            page_data = json.loads(raw)
        except json.JSONDecodeError:
            break
        
        # Extraer registros de la página actual
        if isinstance(page_data, list):
            records = page_data
            meta["total_registros_reales"] = len(records) if meta["total_registros_reales"] is None else meta["total_registros_reales"] + len(records)
            data_total.extend(records)
            meta["paginas_seguidas"] += 1
            siguiente_url = None  # sin paginación
        elif isinstance(page_data, dict):
            # detectar forma del wrapper
            if "data" in page_data and isinstance(page_data["data"], list):
                records = page_data["data"]
                meta["fuente_paginacion"] = "page"
                meta["total_registros_reales"] = page_data.get("total", len(records))
                data_total.extend(records)
                meta["paginas_seguidas"] += 1
                # GitHub-style: Link header con next
                if "next" in page_data and isinstance(page_data["next"], str):
                    siguiente_url = page_data["next"]
                elif 'rel="next"' in link_header:
                    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
                    siguiente_url = match.group(1) if match else None
                else:
                    siguiente_url = None
            elif "results" in page_data and isinstance(page_data["results"], list):
                records = page_data["results"]
                meta["fuente_paginacion"] = "page"
                meta["total_registros_reales"] = page_data.get("count", len(records))
                data_total.extend(records)
                meta["paginas_seguidas"] += 1
                siguiente_url = page_data.get("next")
            else:
                data_total = page_data
                siguiente_url = None
        else:
            data_total = page_data
            siguiente_url = None
        
        meta["total_registros_analizados"] = len(data_total)
        if meta["total_registros_analizados"] >= max_total:
            meta["max_alcanzado"] = True
            break
    
    return data_total, meta
```

Y modificar `campos.py` para que use `data_total` directamente en vez de cortar a 200.

#### Test que verifica (PASO 3)

```python
def test_paginacion_detectada(monkeypatch):
    """Simula una API paginada y verifica que se acumulen todas las páginas."""
    from inspector.core import _descargar_paginado
    
    paginas = [
        {"page": 1, "total": 150, "data": [{"id": i, "nombre": f"U{i}"} for i in range(50)]},
        {"page": 2, "total": 150, "data": [{"id": i, "nombre": f"U{i}"} for i in range(50, 100)]},
        {"page": 3, "total": 150, "data": [{"id": i, "nombre": f"U{i}", "obra_social": "OSDE"} for i in range(100, 150)]},
    ]
    
    llamadas = {"count": 0}
    def fake_urlopen(req, **kwargs):
        llamadas["count"] += 1
        if llamadas["count"] > len(paginas):
            raise StopIteration("test finished")
        body = json.dumps(paginas[llamadas["count"] - 1]).encode()
        return _FakeResponse(body, "")
    
    # ... mockear urllib
    data, meta = _descargar_paginado("http://test")
    assert meta["paginas_seguidas"] == 3
    assert meta["total_registros_analizados"] == 150
    assert meta["total_registros_reales"] == 150
```

#### Criterio de cierre (PASO 4)

✅ Test pasa con API paginada
✅ El informe ahora muestra `total_registros_reales` y `total_registros_analizados`
✅ Si el cliente tiene una API con 3000 socios, los inspeccionamos todos (cap 5000)
✅ Si la API tiene un campo `obra_social` que solo aparece en IDs > 2500, ahora lo detectamos
✅ El hash SHA-256 se calcula sobre la muestra representativa

---

### 🔧 MEJORA 4: Modo "comparar con auditoría previa" (diff forense)

#### Descripción
Hoy cada auditoría es independiente. Si el cliente te dice *"la semana pasada auditaste mi API y ahora me trae campos nuevos"*, no tenés forma de saber qué cambió. Hay que ir al informe viejo, abrirlo a mano, comparar a ojo. **Eso no escala**.

#### Código actual

No existe. La función `inspeccionar()` no tiene un flag de comparación.

#### Escenario de falla (PASO 1)

El auditor corre `api-inspector` contra `https://api.cliente.com/v1` el lunes 16/06/2026. Genera `auditoria-20260616-...-aaa.json`.

El jueves 18/06/2026 el cliente dice: *"agregamos el campo `apto_medico_v2` y sacamos `obra_social` por la ley de protección de datos"*.

El auditor corre de nuevo. Genera `auditoria-20260618-...-bbb.json`.

**Problema**: tiene 2 JSONs y necesita saber:
1. ¿Qué campos nuevos aparecieron?
2. ¿Qué campos desaparecieron?
3. ¿Cambió el tipo de algún campo?
4. ¿Apareció/desapareció PII?
5. ¿Mejoró o empeoró la cobertura de los campos esperados?

Con el código actual: 0 soporte. Hay que hacerlo a mano.

#### Mejora propuesta (PASO 2)

1. **Flag `--comparar-con <ruta_a_json_anterior>`** en el CLI
2. **Función `comparar_auditorias(actual, previa)`** que devuelve un dict de diffs:
   - `campos_nuevos`
   - `campos_eliminados`
   - `campos_tipo_cambiado`
   - `pii_nuevos`
   - `pii_eliminados`
   - `faltantes_resueltos` (antes faltaba, ahora está)
   - `faltantes_nuevos` (estaba, ahora falta)
3. **Sección "Cambios desde la auditoría anterior"** en el HTML y en el informe de consola
4. **Hash chaining**: el hash de la auditoría actual incorpora el hash de la anterior → cadena forense

#### Código de la mejora

```python
# inspector/core.py — nueva función

def comparar_auditorias(actual: Dict, previa: Dict) -> Dict:
    """Compara dos auditorías y devuelve el diff."""
    campos_prev = set(previa.get("estructura", {}).get("campos", {}).keys())
    campos_actual = set(actual.get("estructura", {}).get("campos", {}).keys())
    
    pii_prev = {(h["path"], h["tipo_pii"]) for h in previa.get("pii_detectado", {}).get("hallazgos", [])}
    pii_actual = {(h["path"], h["tipo_pii"]) for h in actual.get("pii_detectado", {}).get("hallazgos", [])}
    
    faltantes_prev = {f["campo_esperado"] for f in previa.get("faltantes_reportados", [])}
    faltantes_actual = {f["campo_esperado"] for f in actual.get("faltantes_reportados", [])}
    
    tipos_prev = {k: v.get("tipo_mayoritario") for k, v in previa.get("estructura", {}).get("campos", {}).items()}
    tipos_actual = {k: v.get("tipo_mayoritario") for k, v in actual.get("estructura", {}).get("campos", {}).items()}
    
    cambios_tipo = {
        k: {"antes": tipos_prev.get(k), "ahora": tipos_actual.get(k)}
        for k in (campos_prev & campos_actual)
        if tipos_prev.get(k) != tipos_actual.get(k)
    }
    
    return {
        "auditoria_previa": previa.get("hash_sha256"),
        "auditoria_actual": actual.get("hash_sha256"),
        "campos_nuevos": sorted(campos_actual - campos_prev),
        "campos_eliminados": sorted(campos_prev - campos_actual),
        "campos_tipo_cambiado": cambios_tipo,
        "pii_nuevos": sorted(pii_actual - pii_prev),
        "pii_eliminados": sorted(pii_prev - pii_actual),
        "faltantes_resueltos": sorted(faltantes_prev - faltantes_actual),
        "faltantes_nuevos": sorted(faltantes_actual - faltantes_prev),
        "resumen": {
            "score_cambios": len(campos_actual - campos_prev) + len(campos_prev - campos_actual),
            "delta_pii": len(pii_actual - pii_prev) - len(pii_prev - pii_actual),
        },
    }
```

Y en el CLI:

```python
# cli.py
p.add_argument("--comparar-con", help="Ruta a una auditoría JSON previa para hacer diff")
```

#### Test que verifica (PASO 3)

```python
def test_diff_entre_auditorias():
    """Dos auditorías con diferencias conocidas deben detectarse."""
    previa = {
        "hash_sha256": "aaa",
        "estructura": {"campos": {
            "id_socio": {"tipo_mayoritario": "integer"},
            "nombre": {"tipo_mayoritario": "string"},
            "obra_social": {"tipo_mayoritario": "string"},
        }},
        "pii_detectado": {"hallazgos": [{"path": "x.dni", "tipo_pii": "dni"}]},
        "faltantes_reportados": [{"campo_esperado": "apto_medico"}],
    }
    actual = {
        "hash_sha256": "bbb",
        "estructura": {"campos": {
            "id_socio": {"tipo_mayoritario": "string"},  # cambió de int a string!
            "nombre": {"tipo_mayoritario": "string"},
            "apto_medico_v2": {"tipo_mayoritario": "boolean"},  # nuevo
            # obra_social ya no está
        }},
        "pii_detectado": {"hallazgos": [
            {"path": "x.dni", "tipo_pii": "dni"},
            {"path": "x.email", "tipo_pii": "email"},  # nuevo PII
        ]},
        "faltantes_reportados": [],  # apto_medico resuelto
    }
    
    diff = comparar_auditorias(actual, previa)
    assert "apto_medico_v2" in diff["campos_nuevos"]
    assert "obra_social" in diff["campos_eliminados"]
    assert "id_socio" in diff["campos_tipo_cambiado"]
    assert ("x.email", "email") in diff["pii_nuevos"]
    assert "apto_medico" in diff["faltantes_resueltos"]
    assert diff["faltantes_nuevos"] == []
```

#### Criterio de cierre (PASO 4)

✅ Test pasa con 2 auditorías con diferencias conocidas
✅ El CLI acepta `--comparar-con`
✅ El HTML y el informe de consola tienen una sección "Cambios desde la auditoría del <fecha>"
✅ El hash chaining funciona: el hash de la nueva auditoría incorpora el de la previa → si alguien edita la anterior, se rompe toda la cadena
✅ Los 9 tests previos + los 3 nuevos de las mejoras 1-3 siguen pasando

---

## 4. Resumen de las 4 mejoras

| # | Mejora | Escenario de falla que resuelve | Impacto | Esfuerzo |
|---|--------|----------------------------------|---------|----------|
| 1 | Normalización PII | Cliente ofusca emails/DNIs con caracteres invisibles o separadores | 🔴 Crítico (forense) | Bajo (1-2 días) |
| 2 | Detección por URL | API minimal sin keys distintivas, info clave en el path | 🟡 Alto (usabilidad) | Bajo (1 día) |
| 3 | Paginación | API con 3000+ registros, se inspeccionan solo 50 | 🔴 Crítico (exhaustividad) | Medio (3-4 días) |
| 4 | Diff entre auditorías | No se puede rastrear qué cambió entre dos inspecciones | 🟡 Alto (operacional) | Medio (2-3 días) |

**Total esfuerzo estimado**: 1 sprint de 2 semanas para las 4.

## 5. Roadmap de implementación

```
Sprint 1 (semana 1-2)
├─ Mejora 1: Normalización PII
├─ Mejora 2: Detección por URL  
└─ Mejora 3: Paginación

Sprint 2 (semana 3)
├─ Mejora 4: Diff forense
└─ Integración de las 4 + release v0.2.0
```

## 6. Tests objetivo

De **9/9** actuales a **15/15** después del Sprint 1 (las 4 mejoras suman 6 tests nuevos).

Cobertura objetivo: **>85%** de líneas.

## 7. Compatibilidad

Las 4 mejoras son **aditivas**:
- Mejora 1: nueva función, no rompe API existente
- Mejora 2: cambia scoring interno, el output es compatible (mismo formato)
- Mejora 3: nuevo campo en el payload `metadata_paginacion`, no rompe nada
- Mejora 4: nueva flag de CLI, sin flag funciona igual que antes

**Cero breaking changes** para usuarios de v0.1.0.

---

_Mantenido por Juan Alberti — análisis técnico para la evolución de api-inspector._
