# Manual 02 — Práctica guiada contra APIs reales

> **Audiencia**: ya leíste el Manual 01 y corriste `--demo` al menos una vez.
> **Duración estimada**: 45–60 minutos (4 misiones).
> **Objetivo**: usar `api-explorer` contra 4 APIs públicas reales, leer
> los informes, y comparar qué cambia entre una API y otra.

---

## Antes de empezar

Asegurate de tener:

- ✅ Python 3.8+ y la herramienta instalada (Manual 01).
- ✅ Conexión a internet estable.
- ✅ Una carpeta `salidas/` donde se van a guardar los informes.
- ⏱️ Tiempo para esperar entre misiones (cada una hace varias pausas
  humanas deliberadas, para no saturar las APIs).

> **Nota importante**: si ves muchos códigos 403 o "no pude conectar",
> subí las pausas con `--pausa-min 3 --pausa-max 5`. La herramienta
> incluye pausas por defecto, pero algunas APIs son particularmente
> sensibles.

---

## Misión 1 — JSONPlaceholder (la más simple)

**Objetivo**: explorar una API muy simple, sin paginación ni datos
sensibles. Es la mejor para familiarizarte con la herramienta en un
entorno real.

### Comando

```bash
python cli.py --url https://jsonplaceholder.typicode.com/users \
              --responsable "Tu nombre" \
              --cliente "Misión 1 — JSONPlaceholder" \
              --salida salidas/mision1
```

### Resultado esperado

- **Tipo detectado**: `desconocido` (porque JSONPlaceholder no matchea
  con ningún patrón).
- **Confianza**: baja, entre 0 y 0.1.
- **Datos sensibles**: pocos o ninguno (los usuarios tienen emails,
  pero sin DNI ni datos de salud).
- **Tiempo total**: 5–10 segundos.

### Qué mirar

1. Abrí `salidas/mision1/exploracion-*.html` en tu navegador.
2. Fijate en la tabla de "Datos sensibles". ¿Aparecen emails? ¿Por qué?
3. Fijate en "Campos faltantes". ¿Dice algo útil si el tipo es
   "desconocido"? ¿Por qué sí o por qué no?
4. Mirá el JSON completo y buscalo campo `pistas_deteccion`. ¿Qué
   dice?

### Preguntas para chequear tu comprensión

1. ¿Por qué `JSONPlaceholder` devuelve tipo `desconocido`?
   _Pista: mirá las `palabras_clave` en `reglas/patrones_deteccion.json`._

2. ¿Apareció algún hallazgo de PII? ¿De qué tipo?
   _Pista: el archivo tiene emails pero no DNIs ni teléfonos._

3. ¿Cuántas pausas humanas hizo la herramienta antes de cada request?
   _Pista: con `--pausa-min 1.2` y un solo request, no hay pausas._

4. ¿Qué pasa si corrés el comando dos veces seguidas? ¿Cambia el hash?
   _Pista: el timestamp cambia cada vez._

---

## Misión 2 — RandomUser (datos sensibles a granel)

**Objetivo**: explorar una API que **sí tiene muchos datos sensibles**
y ver cómo los detecta el explorador.

### Comando

```bash
python cli.py --url https://randomuser.me/api/?results=20 \
              --responsable "Tu nombre" \
              --cliente "Misión 2 — RandomUser" \
              --salida salidas/mision2
```

### Resultado esperado

- **Tipo detectado**: `desconocido` (RandomUser tampoco matchea patrones).
- **Datos sensibles**: **alto**, esperá ver al menos 20 emails y 20
  teléfonos.
- **Hash SHA-256**: presente.
- **Tiempo total**: 5–10 segundos.

### Qué mirar

1. Abrí el HTML y andá directo a "Datos sensibles detectados".
2. Fijate cuántos hay. ¿Aparecieron todos los esperados?
3. Fijate la columna **Método**. ¿Dice `valor_directo` o
   `valor_normalizado`? ¿Por qué?
4. ¿Apareció algún campo de salud (apto médico, grupo sanguíneo)?
   _Pista: RandomUser no incluye esos campos._

### Preguntas para chequear tu comprensión

1. ¿Por qué RandomUser genera tantos hallazgos de PII?
2. Si la API estuviera mal escrita y los emails vinieran con caracteres
   invisibles (ej. `juan\u2024perez@example.com`), ¿los detectaría igual?
   _Pista: mirá `explorer/normalizar.py`._
3. ¿Aparece alguna alerta de menores? ¿Por qué?
4. ¿El campo `phone` se detecta como PII de tipo "teléfono" aunque el
   nombre sea `phone` en inglés? ¿Por qué sí?

---

## Misión 3 — DummyJSON (paginación DRF)

**Objetivo**: explorar una API que devuelve datos paginados y ver cómo
el explorador **sigue la paginación automáticamente**.

### Comando

```bash
python cli.py --url https://dummyjson.com/products \
              --responsable "Tu nombre" \
              --cliente "Misión 3 — DummyJSON" \
              --salida salidas/mision3
```

### Resultado esperado

- **Tipo detectado**: `desconocido` (no matchea ningún patrón conocido).
- **Registros reales**: probablemente 100 o más.
- **Registros analizados**: igual a los reales (la herramienta siguió
  todas las páginas).
- **Fuente de paginación**: `drf` o `page` según cómo vino el JSON.
- **Tiempo total**: 1–3 minutos (hay que esperar pausas entre páginas).

### Qué mirar

1. Abrí el HTML y mirá el bloque de "Resumen".
2. Fijate los números de "Registros reales" vs "Registros analizados".
3. ¿Aparece el aviso de "tope de registros alcanzado"?
4. En el JSON, buscá `metadata_paginacion`. Dice cuántas páginas siguió.

### Preguntas para chequear tu comprensión

1. ¿Por qué DummyJSON muestra 100+ registros si le pediste solo una
   URL? _Pista: la herramienta siguió el `next` automáticamente._
2. Si DummyJSON tuviera 50.000 productos y vos ejecutás este comando,
   ¿qué pasa? _Pista: mirá la variable `max_registros` en
   `explorer/config.py`._
3. ¿Cuántas pausas entre páginas hizo la herramienta? ¿Cómo podés
   verificarlo?
4. ¿Qué estilo de paginación usa DummyJSON? DRF, page, cursor, o Link
   header? _Pista: abrí la URL en tu navegador y mirá la estructura._

### Desafío adicional

Volvé a correr la herramienta, pero esta vez limitá los registros:

```bash
python cli.py --url https://dummyjson.com/products \
              --responsable "Tu nombre" \
              --cliente "Misión 3b — DummyJSON con tope" \
              --salida salidas/mision3b \
              --max-registros 50
```

Compará los dos informes. ¿Qué cambió?

---

## Misión 4 — Diff forense (ReqRes)

**Objetivo**: correr dos veces la herramienta contra la misma API y ver
qué cambios detecta el módulo de diff.

### Comando (primera pasada)

```bash
python cli.py --url https://reqres.in/api/users \
              --responsable "Tu nombre" \
              --cliente "Misión 4 — ReqRes pasada 1" \
              --salida salidas/mision4-pasada1
```

**Resultado esperado**: informe estándar, con tipo `desconocido` y
pocos o ningún dato sensible.

### Esperá un momento

Para que el diff tenga sentido, necesitamos que la API "haya cambiado"
entre las dos pasadas. ReqRes a veces devuelve datos distintos en
peticiones consecutivas.

### Comando (segunda pasada con diff)

```bash
python cli.py --url https://reqres.in/api/users \
              --responsable "Tu nombre" \
              --cliente "Misión 4 — ReqRes pasada 2" \
              --salida salidas/mision4-pasada2 \
              --diff-con salidas/mision4-pasada1/exploracion-*.json
```

> **Nota**: el comodín `*` después de `exploracion-` lo tenés que
> reemplazar por el nombre real del archivo que se generó en la pasada 1.
> En PowerShell podés usar `Get-ChildItem` para copiar el nombre.

**Resultado esperado**: al final del informe aparece una sección nueva
llamada **CAMBIOS DESDE LA EXPLORACIÓN ANTERIOR** con una lista de lo
que cambió.

### Qué mirar

1. ¿Aparecieron "campos nuevos" o "campos eliminados"? ¿Cuáles?
2. ¿Cambió algún tipo de campo?
3. ¿Apareció algún PII nuevo o se eliminó alguno?

### Preguntas para chequear tu comprensión

1. ¿Por qué ReqRes devuelve cosas distintas entre pasadas? _Pista: es
   una API de prueba que randomiza algunos campos._
2. Si la API **no hubiera cambiado**, ¿el diff mostraría algo?
3. ¿Qué ventajas tiene el hash encadenado para una auditoría forense
   real? _Pista: pensá en detectar manipulaciones._

---

## Tabla resumen de las 4 misiones

| Misión | API | Tipo | PII | Paginación | Tiempo |
|---|---|---|---|---|---|
| 1 | JSONPlaceholder | desconocido | bajo | ninguna | 5–10s |
| 2 | RandomUser | desconocido | alto | ninguna | 5–10s |
| 3 | DummyJSON | desconocido | medio | DRF | 1–3 min |
| 4 | ReqRes | desconocido | bajo | ninguna | 5–10s |

---

## Resumen del manual

Después de hacer este manual, ya sabés:

- ✅ Correr la herramienta contra 4 APIs públicas distintas.
- ✅ Leer los informes y entender las diferencias entre cada caso.
- ✅ Interpretar la paginación automática cuando aparece.
- ✅ Usar el diff forense para comparar dos corridas.
- ✅ Ajustar el ritmo con `--pausa-min` y `--max-registros` cuando hace falta.

---

## Próximo paso

Cuando hayas completado las 4 misiones, seguí con el **Manual 03 —
Exploreración libre**, donde vas a elegir tus propias APIs y sacar
tus propias conclusiones sin guía paso a paso.

Si en alguna misión los resultados no coinciden con lo esperado, volvé
a la sección de esa misión. Si el problema persiste, mandame el error.