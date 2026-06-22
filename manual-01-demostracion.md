# Manual 01 — Cargar la herramienta y leer el resultado

> **Audiencia**: nunca usaste `api-explorer` antes.
> **Duración estimada**: 15–20 minutos (lectura + ejecución).
> **Objetivo**: que termines este manual sabiendo instalar la herramienta,
> correr tu primera exploración, y entender qué significa cada sección
> del informe que aparece en pantalla.

---

## 1. ¿Qué es api-explorer?

`api-explorer` es una herramienta de línea de comando escrita en Python.
Su trabajo es **recorrer una API pública y producir un informe firmado**
con SHA-256 que describe:

- Qué tipo de sistema parece ser (biblioteca, natatorio, club, etc.).
- Qué campos trae y de qué tipo son.
- Qué campos faltan según el patrón esperado.
- Qué datos sensibles (PII) detectó.
- Si hay menores de edad sin responsable.
- Un resumen navegable exportado a JSON, CSV y HTML.

El caso de uso real: cuando un cliente te da acceso a una API y querés
entender qué hay antes de tocar nada.

---

## 2. Requisitos previos

Antes de empezar, asegurate de tener:

| Requisito | Cómo verificar |
|---|---|
| Python 3.8 o superior | `python --version` |
| pip | `pip --version` |
| Conexión a internet | Abrí https://example.com en el navegador |
| Permiso para escribir en una carpeta | El lugar donde vas a clonar |

**No necesitás** instalar bases de datos, ni configurar servidores, ni
tener nada raro. Es una herramienta autocontenida.

---

## 3. Instalación

### Paso 3.1 — Clonar el repositorio

Abrí una terminal (PowerShell en Windows, bash en Linux/Mac) y andá a la
carpeta donde quieras guardar el proyecto. Después:

```bash
git clone https://github.com/AlbertiJ/api.git
cd api
```

Si ya lo tenés clonado, simplemente:

```bash
cd api
git pull
```

### Paso 3.2 — Instalar dependencias opcionales

El núcleo funciona solo con la biblioteca estándar de Python. Pero si
querés usar el fuzzer de endpoints o la interfaz web, instalá:

```bash
pip install -r requirements.txt
```

**Resultado esperado**: pip muestra las versiones que instaló y termina
con un mensaje tipo "Successfully installed ...". No debería dar errores.

### Paso 3.3 — Verificar la instalación

```bash
python cli.py --help
```

**Resultado esperado** (recortado):

```
usage: api-explorer [-h] [--url URL] [--responsable RESPONSABLE]
                    [--cliente CLIENTE] [--formato {json,csv,html,todos}]
                    [--salida SALIDA] [--demo] [--diff-con ARCHIVO_JSON]
                    [--pausa-min PAUSA_MIN] [--pausa-max PAUSA_MAX]
                    [--max-registros MAX_REGISTROS]

Explorador de APIs públicas: mapea estructura, detecta datos sensibles,
sigue paginación y emite un informe firmado con SHA-256.

options:
  -h, --help            show this help message and exit
  --url URL             URL de la API a explorar
  ...
```

Si ves esto, la herramienta está lista. Si ves un error tipo
"ModuleNotFoundError", volvé al paso 3.2 y revisá que el `pip install`
haya corrido.

---

## 4. Tu primera exploración (modo demo)

El comando más simple es el modo demo, que no necesita internet. Carga
un archivo de ejemplo local y lo analiza como si fuera una API real.

```bash
python cli.py --demo
```

**Resultado esperado en pantalla** (los números concretos pueden variar
un poco porque el hash cambia con el timestamp):

```
══════════════════════════════════════════════════════════════════════
  INFORME DE EXPLORACIÓN DE API
══════════════════════════════════════════════════════════════════════
  URL:              file://.../api/ejemplos/natatorio.json
  Fecha (UTC):      2026-06-19T...
  Responsable:      no_especificado
  Cliente:          no_especificado
  Tipo detectado:   natatorio  (confianza 0.38)
  Pistas:           key:apto_medico, key:grupo_sanguineo, key:horario

  HASH SHA-256:     d9fc1560a4cbb4eae882ea191661d5e3759a8af278f524f74b7d93f1844e62f2
══════════════════════════════════════════════════════════════════════
  RESUMEN
══════════════════════════════════════════════════════════════════════
   • Registros reales:           6
   • Registros analizados:       6
   • Campos únicos:              14
   • Campos faltantes:           0
   • Datos sensibles (PII):      32
   • Menores detectados:         1
   • Fuente de paginación:       ninguna
   • Pausa entre requests:       0s

  PII por nivel de sensibilidad:
     🟡 medio: 16
     🟠 alto: 9
     🔴 critico: 7

  ⚠ ALERTA: Se detectaron menores y faltan campos de responsable:
     - nombre_responsable
══════════════════════════════════════════════════════════════════════
```

¡Listo! Ya recorriste tu primera API. Ahora vamos a leer juntos qué
significa cada parte.

---

## 5. Cómo leer el informe (sección por sección)

El informe tiene 6 bloques. Vamos uno por uno.

### 5.1 — Cabecera

```
URL:              file://.../api/ejemplos/natatorio.json
Fecha (UTC):      2026-06-19T...
Responsable:      no_especificado
Cliente:          no_especificado
Tipo detectado:   natatorio  (confianza 0.38)
Pistas:           key:apto_medico, key:grupo_sanguineo, key:horario
```

- **URL**: de dónde sacó los datos. En este caso es un archivo local;
  en una exploración real es la URL que vos le pasaste.
- **Fecha (UTC)**: cuándo se hizo la exploración, en hora universal.
- **Responsable / Cliente**: datos opcionales, los llenás con `--responsable`
  y `--cliente` para que el informe sea más trazable.
- **Tipo detectado**: la herramienta adivinó qué tipo de sistema es.
  "natatorio" significa un club con pileta.
- **Confianza**: qué tan segura está la herramienta. Va de 0 a 1.
  - Mayor a 0.3: bastante seguro.
  - Entre 0.1 y 0.3: probable, pero revisá.
  - Menor a 0.1: adivinó, no confíes.
- **Pistas**: por qué llegó a esa conclusión. Cada pista tiene un
  prefijo que indica de dónde salió:
  - `url:` → vino de la URL.
  - `key:` → vino del nombre de un campo del JSON.
  - `val:` → vino del valor de un campo.

### 5.2 — Hash SHA-256

```
HASH SHA-256:     d9fc1560a4cbb4eae882ea191661d5e3759a8af278f524f74b7d93f1844e62f2
```

Es la firma digital de toda la exploración. Si cambia **un solo byte**
del JSON analizado, este hash cambia completamente. Sirve para demostrar
que el informe no fue alterado después.

### 5.3 — Resumen

```
• Registros reales:           6      ← cuántos registros dijo tener la API
• Registros analizados:       6      ← cuántos vimos realmente
• Campos únicos:              14     ← cuántos nombres de campos distintos hay
• Campos faltantes:           0      ← cuántos campos del patrón no aparecieron
• Datos sensibles (PII):      32     ← cuántos hallazgos de PII hubo
• Menores detectados:         1      ← personas <18 años en los datos
• Fuente de paginación:       ninguna ← si la API tiene paginación o no
• Pausa entre requests:       0s     ← tiempo de espera entre requests
```

### 5.4 — PII por nivel de sensibilidad

```
🟡 medio: 16
🟠 alto: 9
🔴 critico: 7
```

Los hallazgos de datos sensibles se agrupan por criticidad:

- 🟡 **medio**: emails, teléfonos. Son PII pero no críticos.
- 🟠 **alto**: DNI, CUIT, fecha de nacimiento. Requieren cuidado legal.
- 🔴 **crítico**: datos de salud (apto médico, grupo sanguíneo, obra
  social). Tienen protección legal reforzada.

### 5.5 — Alerta de menores

```
⚠ ALERTA: Se detectaron menores y faltan campos de responsable:
   - nombre_responsable
```

Cuando hay menores de edad en los datos y NO están los campos de
responsable adulto, esto aparece arriba de todo. Es una señal de que
la API probablemente no cumple con la protección de datos de menores
(ley 25.326 en Argentina, GDPR en Europa).

### 5.6 — Archivos generados

Al final del informe, vas a ver:

```
📄 salidas/exploracion-20260619-...-d9fc1560.json
📄 salidas/exploracion-20260619-...-d9fc1560.csv
📄 salidas/exploracion-20260619-...-d9fc1560.html
```

Son los tres archivos exportados. El hash corto (`d9fc1560`) en el
nombre es el mismo que ves en el bloque del hash completo.

---

## 6. Ver el HTML generado

Abrí la carpeta `salidas/` y hacé doble click sobre el archivo `.html`.
Se abre en tu navegador.

**Qué vas a ver**:

- Un encabezado con la URL, fecha, responsable.
- El hash SHA-256 completo, en una caja oscura.
- Tarjetas grandes con los números del resumen.
- Una tabla con los campos faltantes (si hay).
- Una tabla con todos los hallazgos de datos sensibles.
- Un pie de página con la firma.

Esto es lo que le podés pasar a un cliente. Es presentable y se entiende
sin tener que instalar nada.

---

## 7. Ver el JSON generado

Abrí el archivo `.json` con cualquier editor de texto (VSCode, Notepad++,
incluso el bloc de notas).

**Qué vas a ver**:

```json
{
  "url": "file://...",
  "timestamp_utc": "...",
  "responsable": "no_especificado",
  "cliente": "no_especificado",
  "tipo_detectado": "natatorio",
  "confianza_deteccion": 0.38,
  "pistas_deteccion": ["key:apto_medico", ...],
  "estructura": {
    "total_registros": 6,
    "total_campos_unicos": 14,
    "campos": { ... }
  },
  "pii_detectado": {
    "total_hallazgos": 32,
    "hallazgos": [ ... ],
    "por_categoria": { ... },
    "por_nivel": { ... }
  },
  "reglas_menores": { ... },
  "faltantes_reportados": [],
  "resumen": { ... },
  "hash_sha256": "d9fc1560..."
}
```

El JSON tiene **toda** la información del informe. Es el dato crudo para
procesar después con otro script, o para guardar como evidencia.

---

## 8. Glosario

| Término | Significado |
|---|---|
| **API** | Interfaz de programación. Una URL que devuelve datos en formato JSON. |
| **Endpoint** | Una URL específica dentro de una API (ej. `/users`). |
| **JSON** | Formato de texto para intercambiar datos. Parecido a un diccionario. |
| **PII** | Personally Identifiable Information. Datos que identifican a una persona. |
| **Hash SHA-256** | Una "huella digital" de un texto. Si el texto cambia, el hash cambia. |
| **Paginación** | Cuando una API devuelve los datos en varias páginas en vez de todas juntas. |
| **WAF** | Web Application Firewall. Sistema que detecta y bloquea tráfico automático. |
| **Rate-limit** | Límite de cuántos requests podés hacer por minuto a una API. |
| **Cursor** | Un puntero que indica "desde dónde leer la próxima página". |
| **DRF** | Django REST Framework. Un estilo de paginación muy común. |

---

## 9. Resumen del manual

Después de hacer este manual, ya sabés:

- ✅ Cómo clonar e instalar la herramienta.
- ✅ Cómo correr tu primera exploración con `--demo`.
- ✅ Qué significa cada bloque del informe en pantalla.
- ✅ Cómo abrir el HTML y el JSON generados.
- ✅ Qué es un hash SHA-256 y para qué sirve.

---

## 10. Próximo paso

Cuando te sientas cómodo con todo esto, seguí con el **Manual 02 —
Práctica guiada contra APIs reales**, donde vas a usar la herramienta
contra 4 APIs públicas de verdad y comparar los resultados.

Si algo no funcionó como dice este manual, volvé a la sección
correspondiente. Si el problema persiste, mandame el error tal cual
lo ves en pantalla.