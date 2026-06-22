# 💼 Modelo de negocio — api-explorer (DECIDIDO 2026-06-20)

> Documento vivo. Las decisiones de pricing, tiers y mercado se tomaron
> el 20/06/2026 y se aplican al roadmap de lanzamiento.

---

## 🎯 Tagline

**"Saber qué tiene tu API antes de que sea un problema."**

Alternativa (subtítulo o posts técnicos): "Cuidar tu infraestructura."

---

## 📦 Producto y tiers

### **Free** — $0

- Exploración contra **APIs públicas de la lista permitida** (1 por día).
  - Lista actual: `https://jsonplaceholder.typicode.com`, `https://randomuser.me/api/`, `https://dummyjson.com`, `https://reqres.in`.
- `--demo` con archivo local (sin internet).
- Informe en JSON, CSV y HTML, con hash SHA-256.

**Limitaciones explícitas**:
- Si pasás `--url` y NO está en la lista permitida → "Esto es Pro, comprá $20".
- Sin paginación automática.
- Sin normalización anti-evasión PII.
- Sin diff entre corridas.
- Sin fuzzer.
- Sin interfaz web Flask.

### **Pro** — **$20 one-time**

Incluye TODO lo del Free +:
- **Cualquier URL pública** (sin restricción).
- **Paginación automática** (DRF, page, cursor, Link header).
- **Detección ponderada** por URL/keys/valores (Mejora 2 de INGENIERIA).
- **Normalización PII** anti-evasión (Mejora 1).
- **Diff entre corridas** (Mejora 4).
- Tope configurable: hasta 5000 registros por corrida.
- Soporte por issues de GitHub.

### **Módulos premium** — $15 c/u (se compran aparte, sobre Pro)

| Módulo | Qué hace | Estado |
|---|---|---|
| **MOD-2 (Visualización)** | Genera un grafo visual HTML de tipos compartidos entre endpoints. Estilo `developer-roadmap` clickeable. | ⭐ Estrella — primero a vender |
| **MOD-3 (Recon de host)** | Quién hostea la API, en qué datacenter, si la IP aparece en listas negras. | 🟡 Segundo |
| **MOD-8 (API para terceros)** | Endpoint HTTP para que otros sistemas consuman api-explorer como servicio. | ⚪ Último (requiere hosting) |

**Notas sobre los módulos**:
- Son archivos `.py` adicionales en `explorer/`, NO servicios externos.
- El cliente los descarga y los corre local con `python -m explorer.mod2 ...`.
- El hash SHA-256 del módulo se valida contra el publicado para evitar tampering.

---

## 💰 Pricing — resumen ejecutivo

| Producto | Precio | Tipo |
|---|---|---|
| Free | $0 | — |
| Pro | $20 | one-time |
| MOD-2 | $15 | one-time, requiere Pro |
| MOD-3 | $15 | one-time, requiere Pro |
| MOD-8 | $15 | one-time, requiere Pro |
| Soporte enterprise custom | $80-200/h | por hora (LATAM) |
| **Bonus "pagá más"** | opcional | sugerido $25-50 para clientes generosos |

**Bundle sugerido (después de v0.5)**:
- Pro + MOD-2 = $30 (ahorra $5)
- Pro + todos los módulos = $50 (ahorra $25)

---

## 👤 Buyer persona

### **Pedro** (primario)

- **Edad**: 26
- **Rol**: técnico de infraestructura en entidad financiera
- **Dolor**: abrumado por las novedades de tecnología. Miedo a que una herramienta open source rompa su infra.
- **Necesita**: confiar antes de tocar nada. Informes presentables que pueda mostrar a su jefe.
- **Compra**: Pro ($20) — pago con tarjeta personal o tarjeta corporativa chica.

### **Empresa B2B** (secundario)

- **Tipo**: PyME argentina migrando entre APIs (10-50 empleados).
- **Decisor**: dueño o CTO. Compra con tarjeta corporativa.
- **Dolor**: auditoría de compliance / migración entre sistemas.
- **Necesita**: el HTML presentable + algo que pueda mostrar al contador/abogado.
- **Compra**: Pro + MOD-2 (o bundle).

---

## 🌍 Mercado y canal

### Mercado inicial (honesto)

1. **Gente básica** — estudiantes, devs junior, curiosos.
2. **Comunidad open source LATAM** — vía GitHub + Discord + Telegram.
3. **PyMEs argentinas** — vía Fiverr/Upwork en español.

### Canal de distribución

- **Boca a boca** entre colegas (prioridad 1).
- **GitHub Topics** + awesome-python (prioridad 2 — visibilidad gratis).
- **LinkedIn outbound** a 5-10 Pedros por mes (prioridad 3 — cuando esté v0.5).

---

## 🏁 Lanzamiento — próximos pasos P0

### Esta semana

1. **Resolver las 6 decisiones** → ✅ HECHO (este documento).
2. **PR a `vinta/awesome-python`** → 30 min, visibilidad gratis.
3. **Probar `github/spec-kit`** en un proyecto chico (Bot-de-consulta).
4. **Prompt 4 con objetivo propio**: "vender 3 clientes api-explorer en 60 días".

### Este mes

5. **Landing page** con TCO + tagline final.
6. **"Tutorial de 4 horas"** como lead magnet (Prompt 1).
7. **MOD-2** como primer módulo premium.
8. **Primer outreach** a 5 Pedros.

---

## 📐 Decisiones que se dejaron pendientes

| # | Decisión | Estado |
|---|---|---|
| D1 | Renombrar repo `api` → `api-explorer` en GitHub | ⏳ Pendiente (cosmético, post-lanzamiento) |
| D4 | One-time $20 + bonus pay-what-you-want | ✅ Decidido |
| D5 | 2 tiers, sin Enterprise | ✅ Decidido |

---

_Mantenido por Juan Alberti — generado el 2026-06-20._
