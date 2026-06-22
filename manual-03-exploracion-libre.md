# Manual 03 — Exploración libre: practicá y sacá tus conclusiones

> **Audiencia**: ya hiciste el Manual 01 y el Manual 02.
> **Duración estimada**: 1–2 horas (8 desafíos, sin apuro).
> **Objetivo**: usar `api-explorer` sin instrucciones paso a paso.
> Cada desafío te propone un objetivo, te da pistas, y te deja
> llegar solo a las conclusiones.

> **Cómo se usa este manual**:
> 1. Leés el objetivo.
> 2. Pensás cómo lo resolverías ANTES de tocar la línea de comandos.
> 3. Ejecutás.
> 4. Comparás lo que pasó con lo que esperabas.
> 5. Si te trabás, mirá las pistas (al final de cada desafío).
>
> **No hay respuestas únicas correctas**. Lo que importa es que
> llegues a una conclusión propia y la puedas defender.

---

## Desafío 1 — Tipo conocido (calentar motores)

**Objetivo**: encontrar una API pública que el explorador **sí pueda
clasificar** como un tipo conocido (biblioteca, natatorio, club, etc.).

**Restricciones**:
- No podés usar las 4 APIs del Manual 02.
- Tenés que verificar que la API devuelve JSON (no HTML, no XML).
- Si no encontrás, anotá qué probaste y por qué no funcionó.

**Para entregar**:
- URL que usaste.
- Comando completo.
- Tipo detectado y confianza.
- Captura del bloque "Tipo detectado" del HTML.

**Preguntas para que respondas vos**:
1. ¿Por qué esta API matchea con el patrón y JSONPlaceholder no?
2. Si el patrón es solo de palabras clave, ¿qué tendrías que cambiar
   para que `JSONPlaceholder` matchee con `biblioteca`?
3. ¿Hay algún patrón en `reglas/patrones_deteccion.json` que esté
   obsoleto y deberías sacar?

---

## Desafío 2 — Paginación oculta

**Objetivo**: encontrar una API que devuelva resultados en varias
páginas **sin usar un campo evidente** (no `page`, no `next`).

**Pistas**:
- Algunas APIs usan el header HTTP `Link` con `rel="next"`.
- Otras usan un parámetro de query string como `?cursor=...`.
- Otras devuelven un objeto con un campo raro tipo `pagination.next`.

**Para entregar**:
- URL y comando.
- Estructura de la paginación (cómo descubriste la siguiente página).
- Verificación de que `metadata_paginacion.fuente_paginacion` muestra
  correctamente el estilo detectado.

**Preguntas para que respondas vos**:
1. ¿Qué estilo de paginación era? ¿Por qué no era evidente?
2. ¿La herramienta detectó el estilo automáticamente o tuviste que
   ayudarla?
3. ¿Cuántas páginas siguió antes de cortar?

---

## Desafío 3 — Evasión por ofuscación

**Objetivo**: armar un caso donde los datos sensibles estén **ofuscados
a propósito** y verificar que la herramienta los detecte igual.

**Setup**:
- Creá un archivo `mi_caso.json` en la carpeta `ejemplos/` con un
  objeto que tenga un email y un DNI con caracteres invisibles.

Ejemplo:

```json
{
  "usuario": {
    "nombre": "Juan",
    "email": "juan\u2024perez\u200B@example.com",
    "dni": "25.478.963",
    "telefono": "11\u00A04567\u00A08901"
  }
}
```

**Para entregar**:
- El JSON que creaste.
- El comando (usá `--url file://.../mi_caso.json`).
- Verificación de que los 3 campos aparecen en `pii_detectado`.
- Captura de la columna "Método" mostrando `valor_normalizado`.

**Preguntas para que respondas vos**:
1. ¿Qué técnica de evasión fue más fácil de detectar? ¿Cuál fue más
   difícil?
2. Si la herramienta NO hubiera normalizado, ¿qué diría el informe?
3. ¿Por qué es importante para el cliente que el informe detecte PII
   aunque esté ofuscado?

---

## Desafío 4 — Diff temporal (la API evoluciona)

**Objetivo**: simular que una API cambia entre dos exploraciones y
verificar que el diff forense detecta los cambios.

**Setup**:
- Guardá un JSON con una estructura en `ejemplos/v1.json`.
- Modificalo y guardá la nueva versión en `ejemplos/v2.json`.

**Cambios sugeridos** (elegí al menos 3):
- Agregá un campo nuevo.
- Sacá un campo existente.
- Cambiá el tipo de un campo (ej. `integer` → `string`).
- Agregá un campo con PII (email).
- Sacá un campo que el patrón detecta como faltante.

**Para entregar**:
- Los dos JSON (o los diffs que generaste).
- Comando con `--diff-con` apuntando al primero.
- Sección "Cambios desde la exploración anterior" del informe.

**Preguntas para que respondas vos**:
1. ¿Detectó el cambio de tipo de campo? ¿Cómo lo muestra?
2. ¿Qué tiene más peso en el diff: un campo nuevo o un cambio de tipo?
   _Pista: mirá `score_cambios` en `explorer/diff.py`._
3. ¿Cómo usarías esto en una auditoría real con un cliente?

---

## Desafío 5 — WAF estricto

**Objetivo**: encontrar una API que esté detrás de un WAF estricto y
verificar que la herramienta no se trabe.

**Setup**:
- Buscá una API conocida por ser estricta con el rate-limit
  (ej. algunas APIs de Binance, GitHub, o cualquier API de un banco).
- Corré el explorador primero con pausas bajas (`--pausa-min 0.5`).
- Después con pausas altas (`--pausa-min 5 --pausa-max 10`).

**Para entregar**:
- URL que usaste.
- Resultado del primer intento (probablemente 403).
- Resultado del segundo intento (probablemente éxito).
- Hash SHA-256 de los dos intentos (si el segundo funcionó).

**Preguntas para que respondas vos**:
1. ¿Cuál fue el código de error en el primer intento? ¿Qué dice el
   mensaje?
2. ¿Cuánto tiempo total tomó el segundo intento con pausas altas?
3. Si tuvieras que auditar 50 endpoints contra esta misma API,
   ¿cuánto tardarías en total? _Pista: 50 × pausa media = ?_

---

## Desafío 6 — Limitación descubierta

**Objetivo**: encontrar un caso donde la herramienta **no funciona
bien** y documentarlo.

**Setup**:
- Probá cosas distintas hasta que algo no funcione como esperás:
  - Una API que devuelve HTML en vez de JSON.
  - Una API con autenticación OAuth.
  - Una API GraphQL (no REST).
  - Una API que devuelve un error 500.
  - Una API que devuelve JSON pero con campos muy anidados.

**Para entregar**:
- URL que probaste.
- Qué esperabas que pasara.
- Qué pasó realmente.
- Cómo lo arreglarías (en pseudocódigo, no hace falta codear).

**Preguntas para que respondas vos**:
1. ¿Es una limitación de la herramienta o del caso de uso?
2. ¿Qué agregarías al código para soportar este caso?
3. ¿En qué P0/P1/P2/P3 del roadmap encajaría esa mejora?

---

## Desafío 7 — Informe ejecutivo

**Objetivo**: tomar un informe complejo y armar un resumen de
**1 párrafo** para un cliente no técnico.

**Setup**:
- Usá el HTML del Desafío 1 (el que tiene tipo conocido).
- Leélo completo.
- Escribí un párrafo de 5 líneas para el cliente.

**Restricciones del párrafo**:
- Máximo 5 líneas.
- Sin jerga técnica (no decir "PII", "SHA-256", "DRF").
- Tiene que incluir: tipo detectado, qué datos sensibles se encontraron,
  si hay alertas de menores, y una recomendación.
- Lenguaje llano, como si se lo explicaras a tu tía.

**Para entregar**:
- El párrafo que escribiste.
- El HTML original.
- Tu propia evaluación: ¿el párrafo refleja bien el informe o estás
  omitiendo algo importante?

---

## Desafío 8 — Mejora propuesta

**Objetivo**: proponer una mejora concreta a la herramienta.

**Setup**:
- Releé `PRIORIDADES.md`.
- Encontrá algo que te parezca más importante que lo que está marcado
  como P0/P1.
- O encontrá algo que falte completamente.

**Para entregar**:
- Nombre de la mejora (1 línea).
- Por qué importa (3–5 líneas).
- Cómo lo implementarías (a grandes rasgos, no hace falta codear).
- En qué sprint entraría.

**Preguntas para que respondas vos**:
1. ¿Tu mejora ya estaba en el roadmap pero con otra prioridad? ¿Por
   qué pensás que merece subir o bajar?
2. ¿O es una mejora completamente nueva? ¿Qué la hace más urgente que
   las que ya están listadas?
3. Si tuvieras que defenderla en una reunión, ¿qué dirías?

---

## Tabla de seguimiento

A medida que completes los desafíos, anotá:

| # | Desafío | URL usada | Resultado principal | Conclusión |
|---|---|---|---|---|
| 1 | Tipo conocido | _pendiente_ | | |
| 2 | Paginación oculta | _pendiente_ | | |
| 3 | Evasión por ofuscación | _pendiente_ | | |
| 4 | Diff temporal | _pendiente_ | | |
| 5 | WAF estricto | _pendiente_ | | |
| 6 | Limitación descubierta | _pendiente_ | | |
| 7 | Informe ejecutivo | _pendiente_ | | |
| 8 | Mejora propuesta | _pendiente_ | | |

---

## Resumen del manual

Después de hacer este manual, ya podés:

- ✅ Encontrar y elegir APIs para explorar por tu cuenta.
- ✅ Detectar cuándo la herramienta tiene limitaciones.
- ✅ Producir informes para públicos no técnicos.
- ✅ Proponer mejoras concretas al proyecto.

---

## Próximo paso

Cuando hayas completado los 8 desafíos (o los que puedas), tenés
varias opciones:

1. **Publicar v0.2.0** en GitHub con tus propias mejoras.
2. **Vender el servicio** en Fiverr / Upwork (los informes HTML son
   la muestra que se muestra al cliente).
3. **Sumar este manual** al BlackHat Lab v3 como módulo educativo.
4. **Seguir explorando** con tus propias APIs privadas.

Si en algún desafío te trabás y querés charlarlo, mandame el contexto
(qué intentaste, qué esperabas, qué pasó) y lo vemos juntos.