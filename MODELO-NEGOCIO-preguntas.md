# 🧠 Modelo de negocio — preguntas para definir api-explorer

> **Contexto**: ya tenemos el producto base funcionando (v0.2.0 con las 4
> mejoras de INGENIERIA.md aplicadas). Ahora hay que decidir cómo lo
> cortamos para venderlo.
>
> **Inspiración**: SAP Finance — un core que todos compran + módulos
> que se agregan por separado según necesidad del cliente.
>
> **Para responder**: andate tranquilo, cada pregunta tiene su espacio
> abajo. Cuando llegues a casa, charlamos y armamos el plan.

---

## 📌 Resumen ejecutivo (para arrancar a pensar)

Antes de entrar en las preguntas, anotá esta intuición tuya ahora,
en frío, sin analizar demasiado:

> **¿Qué te imaginás cuando pensás en api-explorer como producto
> para vender?**
>
> (1 sola línea — tu primer instinto)
>
> _Espacio para tu respuesta:_
>
> ```
>
> ```

---

## Bloque 1 — El core (qué queda en TODOS los tiers)

Estas funcionalidades son **imprescindibles**: las pagas o no, las tenés.
Son el corazón del producto.

### P1. ¿Cuál es el mínimo absoluto que necesita un cliente para
sentir que "usó api-explorer"?

Opciones (podés elegir más de una):

- [ ] **C1**: Descargar una API y mostrarme la estructura (campos y tipos).
- [ ] **C2**: Decirme qué tipo de sistema es (biblioteca, natatorio, etc.).
- [ ] **C3**: Avisarme si hay datos sensibles (PII básico).
- [ ] **C4**: Generarme un informe en PDF/HTML presentable.
- [ ] **C5**: Firmar el informe con hash para que sea prueba forense.

> **Tu respuesta — ¿cuáles quedan en el core?**
>
> ```
>
> ```

### P2. ¿Qué cosas del producto actual NO van en el core?

O sea, ¿qué se mueve a un tier pago aunque sea útil?

- [ ] **M1**: Paginación automática de la API.
- [ ] **M2**: Detección ponderada por URL (Mejora 2 de INGENIERIA).
- [ ] **M3**: Normalización anti-evasión de PII (Mejora 1 de INGENIERIA).
- [ ] **M4**: Diff entre dos corridas (Mejora 4 de INGENIERIA).
- [ ] **M5**: Fuzzer de endpoints (`discovery.py`).
- [ ] **M6**: Interfaz web Flask (`app.py`).

> **Tu respuesta — ¿cuáles sacás del core?**
>
> ```
>
> ```

---

## Bloque 2 — Los tiers (cómo se corta el producto)

### P3. ¿Cuántos niveles querés ofrecer?

Pensá en el modelo SAP: tienen SAP Business One (PyME), SAP S/4HANA (mediana), SAP S/4HANA Cloud (enterprise). Tres niveles suele ser el sweet spot.

- [ ] **Opción A**: 2 niveles — Free + Pro.
- [ ] **Opción B**: 3 niveles — Free + Pro + Enterprise.
- [ ] **Opción C**: 4+ niveles — Free + Lite + Pro + Enterprise.
- [ ] **Opción D**: Solo Pro, sin free (todo pago).

> **Tu respuesta — y ¿por qué?**
>
> ```
>
> ```

### P4. Si elegís 3 niveles, ¿qué va en cada uno?

Completá esta tabla con tu instinto (no hace falta que sea definitivo):

| Funcionalidad | Free / Lite | Pro (pago único) | Enterprise (suscripción) |
|---|---|---|---|
| Exploración básica (1 API, sin paginación) | | | |
| Paginación automática | | | |
| Normalización PII | | | |
| Detección ponderada | | | |
| Diff entre corridas | | | |
| Fuzzer de endpoints | | | |
| Interfaz web | | | |
| Multi-usuario / nube | | | |
| Soporte por email | | | |

> **Tu respuesta — llená la tabla con ✓ (incluido) o — (no incluido)**
>
> ```
>
> ```

### P5. ¿Cuál es el techo del tier Free?

Si es muy generoso, nadie paga. Si es muy restrictivo, nadie lo prueba.

- [ ] **A**: El Free puede hacer **1 exploración por día** con tope de **50 registros**.
- [ ] **B**: El Free puede hacer exploraciones **ilimitadas** pero sin paginación y con tope de **10 registros por corrida**.
- [ ] **C**: El Free es **solo demo local** — no puede explorar APIs reales online.
- [ ] **D**: Otra cosa que se te ocurra.

> **Tu respuesta — y ¿por qué pensás así?**
>
> ```
>
> ```

---

## Bloque 3 — Los módulos premium (qué se vende por separado)

Esto es lo que copia el modelo SAP: módulos opcionales que el cliente
suma si los necesita.

### P6. ¿Cuáles de estos módulos te imaginás vendibles?

Marcá los que te parezca que alguien pagaría aparte:

- [ ] **MOD-1**: **Compliance** — informe automático de cumplimiento GDPR / Ley 25.326 / CCPA con checklist descargable.
- [ ] **MOD-2**: **Visualización** — grafo interactivo de tipos de campos compartidos entre endpoints (estilo Visual-Map pero sin Gemini).
- [ ] **MOD-3**: **Recon de host** — quién hostea la API, en qué datacenter está, si la IP está en listas negras (hermano de api-explorer, no integrado).
- [ ] **MOD-4**: **OpenAPI** — leer un `openapi.json` y comparar contra lo que devuelve la API real (drift detection).
- [ ] **MOD-5**: **Postman** — importar una colección Postman existente como punto de partida.
- [ ] **MOD-6**: **Asistente IA** — genera el resumen ejecutivo de 1 párrafo usando un LLM (vos elegís cuál).
- [ ] **MOD-7**: **Programación de exploraciones** — correr auditorías cada lunes a las 9am automáticamente.
- [ ] **MOD-8**: **API para terceros** — endpoint HTTP para que otros sistemas puedan usar api-explorer como servicio.

> **Tu respuesta — ¿cuáles ves viables?**
>
> ```
>
> ```

### P7. ¿Cuál sería tu **módulo estrella** (el primero para vender)?

Si tuvieras que elegir UNO solo para arrancar, ¿cuál sería y por qué?

> **Tu respuesta:**
>
> ```
>
> ```

---

## Bloque 4 — Pricing

### P8. ¿One-time (pago único) o suscripción mensual/anual?

- [ ] **A**: One-time (comprás el Pro y es tuyo para siempre, módulos premium aparte).
- [ ] **B**: Suscripción mensual/anual (pagás mientras lo usás).
- [ ] **C**: Mix — Pro es one-time, módulos premium son suscripción.
- [ ] **D**: Freemium + pay-what-you-want (como GitHub Sponsors).

> **Tu respuesta — y ¿cómo lo justificarías ante un cliente?**
>
> ```
>
> ```

### P9. Rangos de precio tentativos

Anotá números redondos, en USD, que te parezcan razonables.
No te cases con esto todavía, es un primer pase.

- **Free**: $ ____
- **Pro (one-time)**: $ ____
- **Enterprise (suscripción anual)**: $ ____ / año
- **Módulos premium (cada uno)**: $ ____

> **Tu respuesta — números instintivos**
>
> ```
>
> ```

### P10. ¿Cobro en USD o en ARS?

- [ ] **USD** (mercado internacional: USA, Europa, Latam dev).
- [ ] **ARS** (mercado local argentino: bancos, fintechs, gov).
- [ ] **Ambos** — el precio se ajusta por tipo de cliente.

> **Tu respuesta**
>
> ```
>
> ```

---

## Bloque 5 — Mercado

### P11. ¿A quién le vendés primero?

- [ ] **A**: Bancos / fintechs LATAM (ya tenés la experiencia con Infoblox en BBVA, HSBC, MercadoLibre).
- [ ] **B**: PyMEs argentinas que migran entre sistemas (Natatorio Olivos, biblioteca, etc.).
- [ ] **C**: Empresas USA/EU vía Fiverr / Upwork en inglés.
- [ ] **D**: Gobierno (GBA, ministerios) — ya tenés el pie en Defensa Civil.
- [ ] **E**: Otro — contame cuál.

> **Tu respuesta — y por qué ese primero**
>
> ```
>
> ```

### P12. ¿Por dónde llega el primer cliente?

- [ ] **A**: Tu LinkedIn personal (322 followers, 241 conexiones).
- [ ] **B**: GitHub (5 repos públicos, 3 followers — hay que trabajar esto).
- [ ] **C**: Fiverr / Upwork.
- [ ] **D**: Outreach directo (mail + LinkedIn) a una lista de 20 empresas.
- [ ] **E**: Boca a boca entre colegas de GBA / Defensa Civil.
- [ ] **F**: Otro.

> **Tu respuesta**
>
> ```
>
> ```

### P13. ¿Cuál es la **promesa de una línea** del producto?

Si tuvieras que explicarlo en una sola oración para el homepage de
una landing page, ¿cuál sería?

Inspiración: SAP promete "run live" / Salesforce "we bring companies and customers together" / Figma "where teams bring designs to life".

> **Tu respuesta — tu tagline**
>
> ```
>
> ```

---

## Bloque 6 — Lanzamiento

### P14. ¿Cuál es el primer paso concreto esta semana?

- [ ] **A**: Definir pricing final y armar landing page.
- [ ] **B**: Publicar v0.2.0 en GitHub con README nuevo.
- [ ] **C**: Hacer el primer outreach a 5 empresas.
- [ ] **D**: Crear el primer módulo premium y venderlo como producto separado.
- [ ] **E**: Otra cosa.

> **Tu respuesta**
>
> ```
>
> ```

### P15. ¿Quién es tu **cliente ideal** en una persona?

Inventate un personaje. Nombre, edad, rol, dónde labura, qué dolor tiene, qué lo haría pagar.

> **Tu respuesta — tu buyer persona**
>
> ```
>
> ```

### P16. ¿Cuánto querés facturar en los primeros 6 meses?

Número realista, sin apuro. En USD o ARS, lo que te sea más cómodo.

> **Tu respuesta**
>
> ```
>
> ```

---

## 🗒️ Tus notas libres

Cualquier cosa que se te ocurra mientras viajás:

```
[ anotaciones ]
```

---

## 🏁 Próximo paso al llegar a casa

Cuando hayas completado las preguntas (o al menos las 6 primeras),
me pasás las respuestas y armamos juntos:

1. El **TCO del producto** (qué entra en cada tier con precisión).
2. El **roadmap de lanzamiento** (qué sale primero, qué segundo).
3. El **primer mensaje de outreach** para la primera empresa.

Si te trabás en alguna, dejala en blanco y seguimos después.
¡Buen viaje! 🚆