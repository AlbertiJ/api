# 📦 PR a awesome-python — texto listo y checklist

> Documento vivo. Lo armamos el 2026-06-21 con las reglas del CONTRIBUTING
> de [vinta/awesome-python](https://github.com/vinta/awesome-python/blob/master/CONTRIBUTING.md)
> y los hallazgos del README en ese momento.
>
> **Cuándo usar**: cuando el repo `AlbertiJ/api` tenga **al menos 50 stars** y
> un README público prolijo. Antes de eso el PR va a ser rechazado por el
> bot automático.

---

## 🛑 Por qué NO mandarlo ahora (jun-2026)

| Criterio del CONTRIBUTING | Lo que pide | Lo que tenemos ahora |
|---|---|---|
| 100 stars (sin Hidden Gem) | ≥ 100 stars | ❌ 0 stars |
| Repo > 1 mes | Activo | ✅ Sí |
| Commits últimos 12 meses | Activo | ✅ Sí |
| Documentado | README claro | ⚠ Mejorable |
| PyPI | Paquete publicable | ❌ No está |
| Estable | No alpha/beta | ✅ Sí |
| Único | Valor distinto | ✅ Sí |

**Conclusión**: con 0 stars, el bot te cierra el PR en menos de 1 día. Mejor
preparar el repo y mandar cuando llegue a 50+ stars.

---

## 📝 El entry (3 variantes para probar)

awesome-python tiene categorías que podrían容纳 el proyecto. Acá van las 3
opciones, en orden de probabilidad de aceptación:

### Opción A — **HTTP Clients** (más probable)

Ubicación en el README actual: `### HTTP Clients`

```markdown
- [api-explorer](https://github.com/AlbertiJ/api) - Audita APIs públicas: detecta tipo de sistema, mapea estructura, identifica PII (incluso ofuscada), sigue paginación y emite informe firmado con SHA-256.
```

### Opción B — **Web APIs** (alternativa)

Ubicación: `### Web APIs > Framework Agnostic`

```markdown
- [api-explorer](https://github.com/AlbertiJ/api) - Herramienta de auditoría forense para APIs públicas. Detecta tipos, mapea campos, identifica PII y faltantes contra el patrón esperado.
```

### Opción C — **Testing > Frameworks** (como scanapi)

Ubicación: `### Testing > Frameworks`

```markdown
- [api-explorer](https://github.com/AlbertiJ/api) - Audita APIs públicas para detectar tipo, estructura, datos sensibles y faltantes. Genera informe firmado con SHA-256.
```

---

## 📄 Título del PR (3 opciones)

1. `Add api-explorer to HTTP Clients section`
2. `Add api-explorer (API auditing tool) to HTTP Clients`
3. `Add api-explorer: forense auditing tool for public APIs`

Recomendación: el **1** es el más limpio, sigue el formato del repo.

---

## 📄 Cuerpo del PR (versión estándar)

```markdown
## What is api-explorer?

A command-line auditing tool for public APIs. When you point it at an API
endpoint, it downloads the JSON response, detects what kind of system it is
(library, swim club, gym, etc.), maps the structure, identifies sensitive
data (PII) — including data hidden behind unicode zero-width characters or
numeric separators — and emits a forensic report signed with SHA-256.

## Use cases

- **API migration**: compare the structure of your old API with the new one.
- **Compliance**: detect PII before touching user data.
- **Discovery**: map undocumented APIs in minutes instead of hours.

## Why it fits here

api-explorer uses `urllib` (Python standard library) and respects the
HTTP semantics. It handles pagination automatically (DRF, page-based,
cursor, GitHub-style `Link` headers), human-like request timing (1.2-2.4s
with jitter) to avoid triggering WAFs, and reports the source of every
detection (URL segments, top-level keys, or values).

## Standards compliance

- Python-first: 100% Python stdlib, zero external dependencies for the core.
- Python 3.8+ supported.
- Active: commits within last 30 days.
- Documented: README with examples, three tutorials (demo, guided practice,
  free exploration) in Spanish.
- Unique: combines PII detection with anti-evasion normalization (handles
  unicode-obfuscated data), which other tools in this list don't do.
- Stable: production-ready, no alpha/beta tag.
```

---

## 📄 Cuerpo del PR (versión **Hidden Gem** — si tenés < 100 stars)

Si querés mandarlo antes de los 100 stars, esta versión justifica con
evidencia de uso real. Reemplazá los placeholders.

```markdown
## What is api-explorer?

[Misma intro que arriba]

## Real-world usage (Hidden Gem justification)

- Used in production by [cliente/empresa] since [fecha].
- Featured in [post en dev.to / artículo / charla].
- [N] users reached via [canal: LinkedIn, Telegram, Discord, etc.].
- Recommended by [nombre de dev conocido / publicación].
- Demonstrated in [video / demo grabado].

## Why a Hidden Gem?

While the repo has fewer than 100 stars today, it solves a real problem
in the API migration space: most auditing tools focus on security
vulnerabilities (OWASP-style) or performance, not on data structure
mapping with PII detection. api-explorer fills that gap, and the included
Spanish-language tutorials make it accessible to LATAM developers
underrepresented in the Python ecosystem.

## Future plans

- PyPI publication in the next release.
- English translation of tutorials.
- OpenTelemetry integration for production observability.
```

---

## ✅ Checklist pre-PR (antes de mandar)

Marcá antes de abrir el PR:

- [ ] Repo tiene ≥ 50 stars (idealmente ≥ 100)
- [ ] README en GitHub prolijo, con:
  - [ ] Descripción corta de 1 línea
  - [ ] Badges (CI si hay, license MIT, version)
  - [ ] Instalación clara
  - [ ] Ejemplo de uso (output esperado)
  - [ ] Tabla de features
  - [ ] Link a `MODELO-NEGOCIO-final.md` o pricing público
- [ ] **Topics de GitHub** configurados:
  - `python`, `api`, `auditing`, `data-migration`, `pii-detection`,
    `forensics`, `cli`, `json`
- [ ] **Description** del repo en GitHub (corto, 1-2 oraciones)
- [ ] **Releases tab** con tag `v0.2.0` y notas de release
- [ ] **License MIT** confirmada
- [ ] Al menos 1 issue cerrado o abierto (muestra que el repo está vivo)
- [ ] El entry elegido sigue orden alfabético en la sección

---

## 🚀 Cómo mandar el PR (paso a paso)

1. Fork `vinta/awesome-python` desde GitHub.
2. Cloná tu fork:
   ```bash
   git clone https://github.com/<tu-usuario>/awesome-python.git
   cd awesome-python
   ```
3. Creá una rama:
   ```bash
   git checkout -b add-api-explorer
   ```
4. Editá `README.md` con el entry elegido (respetá el orden alfabético).
5. Commit:
   ```bash
   git add README.md
   git commit -m "Add api-explorer to HTTP Clients"
   ```
6. Pusheá:
   ```bash
   git push origin add-api-explorer
   ```
7. Abrí PR en GitHub desde tu fork hacia `vinta/awesome-python:master`.
8. Título: el que elegiste arriba.
9. Cuerpo: la versión estándar o Hidden Gem según corresponda.
10. **Esperá 1-3 días**. Si no hay respuesta, dejá un comment amable pidiendo review.

---

## 🔄 Si te rechazan el PR

No es el fin. Pasos:

1. Lee el mensaje de cierre del bot (generalmente explica qué falta).
2. Si dice "Hidden Gem justification": agregá más evidencia de uso real
   (artículos, demos, testimonios) y reintentá.
3. Si dice "stars < 100": esperá a tener más tracción y reintentá.
4. Si te dicen "duplicate o recently closed": buscá en issues cerrados
   si ya hubo un PR similar.

Mientras tanto, **no te quedes quieto**: mandá el mismo contenido a
**dev.to**, **Reddit r/Python**, **Hacker News Show HN**, y grupos de
Telegram/Discord de devs Python LATAM.

---

## 📌 Mientras tanto — tareas para conseguir stars

Lista de acciones concretas que te llevan de 0 → 100 stars en 2-4 semanas:

1. **Publicar v0.2.0 release** en GitHub con notas de release.
2. **Escribir 1 artículo en dev.to** (ej. "Audité randomuser.me y encontré
   32 PII en mi propia herramienta").
3. **Postear en LinkedIn** con screenshot del informe HTML generado.
4. **Pedir feedback a 5 colegas** (los de tu red Obsidian, Defensa Civil,
   GBA) → cada uno deja star + comenta.
5. **Postear en 2 grupos de Telegram** de devs Python LATAM.
6. **Postear en Reddit r/Python** con título: "I built a forensic API
   auditor in pure Python stdlib (no dependencies)".
7. **Cross-post en Hacker News** con "Show HN: api-explorer – forensic
   auditor for public APIs".

Cada una te debería dar 10-30 stars. Sumadas, llegás a 50-100 en 2-4 semanas.

---

_Mantenido por Juan Alberti — armado el 2026-06-21._
