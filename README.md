# API Explorer

Explorador de APIs públicas. Mapea la estructura, detecta datos sensibles,
sigue paginación, y emite un informe firmado con SHA-256.

Pensado para cuando un cliente te da acceso a una API y querés entender
qué hay antes de tocarla.

## Instalación

```bash
pip install -r requirements.txt   # solo si vas a usar la UI web o discovery
```

El núcleo (`cli.py --demo` o `cli.py --url`) no necesita nada extra.

## Uso

```bash
# Demo offline (sin internet)
python cli.py --demo

# Exploración real contra una API
python cli.py --url https://api.example.com --responsable "responsable_auditoria" --cliente "Cliente X"

# Exportar solo HTML
python cli.py --url https://api.example.com --formato html

# Comparar con una exploración previa
python cli.py --url https://api.example.com --diff-con salidas/vieja.json

# Ajustar ritmo (si la API es muy sensible al rate-limit)
python cli.py --url https://api.example.com --pausa-min 2.0 --pausa-max 4.0
```

## Interfaz web (opcional)

```bash
python app.py
# Abre http://localhost:5000
```

## Tests

```bash
python tests/test_explorer.py
```

## Estructura

```
api/
├── cli.py                  # entrypoint CLI
├── app.py                  # interfaz web Flask
├── explorer/
│   ├── core.py             # motor principal
│   ├── config.py           # ritmo de requests, timeouts
│   ├── detectar.py         # adivina el tipo de API (URL/keys/valores)
│   ├── campos.py           # mapea estructura
│   ├── sensibles.py        # detecta PII (con normalización anti-evasión)
│   ├── normalizar.py       # pre-procesa valores ofuscados
│   ├── paginacion.py       # sigue cursor/page/Link header
│   ├── exportar.py         # JSON / CSV / HTML
│   ├── informe.py          # texto para consola
│   ├── gap.py              # compara con campos "oficiales"
│   ├── discovery.py        # fuzzer opcional de endpoints
│   └── diff.py             # compara dos exploraciones en el tiempo
├── reglas/                 # JSON de patrones y reglas PII
├── ejemplos/               # JSON de prueba
├── salidas/                # archivos generados
└── tests/
```

## Características

- **Sin suplantación**: identifica lo que es pero habla HTTP maduro.
- **Ritmo humano**: pausas configurables entre requests para no ser
  detectado como bot por WAF/CDN.
- **Paginación automática**: sigue `next` cursors, `Link` headers, y
  wrappers `data/results/items` con un tope de seguridad.
- **PII con normalización**: detecta emails/DNIs incluso si vienen
  ofuscados con caracteres invisibles o separadores visuales.
- **Detección ponderada**: la URL pesa más que las keys, las keys más
  que los valores. Útil contra APIs minimalistas.
- **Diff entre corridas**: ¿qué cambió desde la última exploración?
- **Informe firmado**: hash SHA-256 sobre el payload canónico.
- **Cadena de hashes**: el hash de hoy puede incluir el de ayer.

## 📚 Documentación complementaria

- **[`docs/EJEMPLOS.html`](docs/EJEMPLOS.html)** — Página de presentación + 7 casos de uso copy-paste con output real esperado.
- **[`EXAMPLES.md`](EXAMPLES.md)** — Comandos rápidos con las 4 APIs públicas del tier Free.
- **[`manual-01-demostracion.md`](manual-01-demostracion.md)** · [`manual-02-practica-guiada.md`](manual-02-practica-guiada.md) · [`manual-03-exploracion-libre.md`](manual-03-exploracion-libre.md)` — Manuales paso a paso en español.
- **[`INGENIERIA.md`](INGENIERIA.md)** — Las 4 mejoras técnicas documentadas (normalización PII, detección ponderada, paginación, diff).
- **[`docs/DIARIO-TECNICO.md`](docs/DIARIO-TECNICO.md)** — Bitácora del grupo de agentes: hallazgo → análisis → fix → hash SHA-256.

## 🗺️ Roadmap

| Tier | Estado | Detalle |
|---|---|---|
| **v0.1.0** MVP | ✅ publicado | Auditor forense básico (9 tests) |
| **v0.2.0** refactor | ✅ publicado | 4 mejoras de `INGENIERIA.md` + 21 tests |
| **v0.3.0** tiers | ✅ publicado | Free/Pro + licencias HMAC + 92 tests + CI verde |
| **v0.4.0** modulos | 🔜 siguiente | MOD-2 (grafo), MOD-3 (recon host), MOD-8 (API terceros) |
| **v0.5.0** compliance | 📋 planeado | Reporte GDPR / Ley 25.326 / CCPA por campo |
| **v1.0.0** SaaS | 💭 visión | UI web con auth + histórico de diffs por cliente |

Roadmap completo con justificación y criterios de éxito: **[`PRIORIDADES.md`](PRIORIDADES.md)**.

Modelo de negocio y tiers: **[`MODELO-NEGOCIO-final.md`](MODELO-NEGOCIO-final.md)**.

## ✅ Estado del proyecto

```
Tests:           92/92 verde (local) · 91/91 verde (CI en 3 versiones de Python)
Lint:            flake8 limpio
CI:              GitHub Actions verde en push
Release actual:  v0.3.0
Licencia:        MIT
```

## Licencia

MIT.

---

## 💼 Producto y pricing

**api-explorer** se ofrece en tiers. La idea es que pruebes con el Free y,
si te sirve, compres el Pro. Los módulos premium son add-ons opcionales.

| Producto | Precio | Incluye |
|---|---|---|
| **Free** | $0 | Demo local + 1 exploración online/día contra APIs públicas conocidas (JSONPlaceholder, RandomUser, DummyJSON, ReqRes). Informe JSON/CSV/HTML con hash SHA-256. |
| **Pro** | **$20** one-time | Todo lo del Free + cualquier URL pública + paginación automática + detección ponderada + normalización PII + diff entre corridas. |
| **MOD-2** (Visualización de grafo) | **$15** | Genera grafo HTML clickeable de tipos compartidos. Estilo `developer-roadmap`. Requiere Pro. |
| **MOD-3** (Recon de host) | **$15** | Quién hostea la API, datacenter, listas negras. Requiere Pro. |
| **MOD-8** (API para terceros) | **$15** | Endpoint HTTP para integrar api-explorer en otros sistemas. Requiere Pro. |

Para más detalle, ver `MODELO-NEGOCIO-final.md`.

**Tagline**: *"Saber qué tiene tu API antes de que sea un problema."*