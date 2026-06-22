# 🧪 Protocolo de testing automatizado — api-explorer

> **Para qué sirve**: validar que cada paso del roadmap está completo,
> automatizado y testeado, antes de marcarlo como "listo para producción".
>
> **Cuándo se usa**: cada vez que se cierra un bloque del roadmap o se
> publica una versión nueva. Antes de mandar el PR a awesome-python,
> antes del v0.2.0 release, antes de cualquier venta.
>
> **Quién lo ejecuta**: 2 grupos de agentes en paralelo:
> - **Grupo Web**: experiencia en frontend, Flask, HTML, UX.
> - **Grupo Fullstack**: experiencia en CLI, Python, empaquetado, CI.
>
> **Cuántas veces**: cada agente corre el protocolo **5 veces**
> (corridas independientes) para descartar flakes.

---

## 🎯 Setup (antes de empezar)

### Cosas que tienen que estar listas

- [ ] Repo clonado en una carpeta limpia
- [ ] Python 3.8+ instalado
- [ ] pip install -r requirements.txt ejecutado
- [ ] Las 4 APIs públicas de prueba accesibles (JSONPlaceholder, RandomUser, DummyJSON, ReqRes)
- [ ] Un archivo de licencia Pro de prueba en `~/.api-explorer-license-test` (para Ronda 3)

### Cómo se mide el éxito

Cada corrida registra:
- ✅ Pasó
- ⚠ Pasó con observaciones (no es blocker)
- ❌ Falló (es bug)

**El protocolo cierra como "production ready" solo si 5/5 corridas del ambos grupos pasan sin ❌.**

---

## 📋 Las 5 corridas

### Corrida 1 — Instalación y arranque en limpio

**Objetivo**: que alguien que nunca vio el repo pueda instalarlo y correr `--help` en menos de 3 minutos.

**Pasos**:

```bash
# 1. Clonar fresco
git clone https://github.com/AlbertiJ/api.git test-r1
cd test-r1

# 2. Instalar deps
pip install -r requirements.txt

# 3. Verificar que el --help funciona
python cli.py --help
```

**Resultado esperado**:

- `git clone` no falla
- `pip install` termina con "Successfully installed..."
- `python cli.py --help` muestra el usage con todas las opciones nuevas
  (`--diff-con`, `--pausa-min`, `--max-registros`, etc.)

**Qué tiene que chequear cada grupo**:

| Grupo | Verifica |
|---|---|
| **Web** | El `--help` es legible y tiene buena estructura visual |
| **Fullstack** | El comando no tira excepciones, las opciones nuevas están todas |

---

### Corrida 2 — Flujo end-to-end básico (Free)

**Objetivo**: que el flujo del tier Free funcione completo (demo + URL permitida).

**Pasos**:

```bash
# 1. Demo local
python cli.py --demo
# Esperado: informe completo en consola con natatorio + 32 PII + hash

# 2. URL permitida (Free)
python cli.py --url https://jsonplaceholder.typicode.com/users/1
# Esperado: "✓ Acceso Free" + informe

# 3. URL bloqueada (debe rechazar)
python cli.py --url https://api.banco-privado.com/v1
# Esperado: "🔒 Acceso denegado" + lista de dominios permitidos
```

**Resultado esperado**:
- Demo imprime el informe con tipo detectado, hash, archivos generados
- URL permitida: dice "Acceso Free — dominio en lista permitida" y explora
- URL bloqueada: sale con exit code 3 y mensaje claro

**Qué tiene que chequear cada grupo**:

| Grupo | Verifica |
|---|---|
| **Web** | El HTML generado en `salidas/` se ve bien y abre sin errores |
| **Fullstack** | El JSON y el CSV se generan correctamente y son parseables |

---

### Corrida 3 — Sistema de licencias Pro

**Objetivo**: que la validación HMAC funcione en todos los casos (válida, inválida, manipulada).

**Pasos**:

```bash
# 1. Sin licencia
python cli.py --url https://api.banco.com/v1
# Esperado: 🔒 denegado

# 2. Generar licencia válida
python scripts/generar_licencia.py test@ejemplo.com --out ~/.api-explorer-license

# 3. Con licencia válida
python cli.py --url https://api.banco.com/v1
# Esperado: ✓ Acceso Pro — pasa

# 4. Manipular la licencia
python -c "
import json, pathlib
r = pathlib.Path.home() / '.api-explorer-license'
data = json.loads(r.read_text())
data['sig'] = '0' * 64  # firma falsa
r.write_text(json.dumps(data))
"
python cli.py --url https://api.banco.com/v1
# Esperado: 🔒 denegado + "Firma inválida"

# 5. Cambiar email de la licencia (debe fallar aunque la firma sea del email original)
python -c "
import json, pathlib
r = pathlib.Path.home() / '.api-explorer-license'
data = json.loads(r.read_text())
data['email'] = 'otro@atacante.com'
r.write_text(json.dumps(data))
"
python cli.py --url https://api.banco.com/v1
# Esperado: 🔒 denegado

# 6. Borrar licencia y volver a Free
rm ~/.api-explorer-license
python cli.py --url https://api.banco.com/v1
# Esperado: 🔒 denegado (volvió a Free)
```

**Resultado esperado**: 5/5 verificaciones se comportan como dice.

**Qué tiene que chequear cada grupo**:

| Grupo | Verifica |
|---|---|
| **Web** | El mensaje de error al cliente es claro y le dice qué hacer |
| **Fullstack** | El HMAC funciona, no hay manera de falsificarlo con un cambio de email |

---

### Corrida 4 — Casos de error y recovery

**Objetivo**: que la herramienta NO se rompa con entradas malformadas y dé mensajes útiles.

**Casos a probar**:

```bash
# Caso 4.1: URL inválida (sin esquema)
python cli.py --url "esto no es url"
# Esperado: 🔒 denegado, no crashea

# Caso 4.2: URL que devuelve HTML (no JSON)
python cli.py --url https://example.com
# Esperado: error claro, no crashea

# Caso 4.3: URL con timeout
python cli.py --url https://httpstat.us/200?sleep=30000 --pausa-min 0.5
# Esperado: timeout limpio, no se cuelga el proceso

# Caso 4.4: URL que devuelve JSON vacío
python cli.py --url https://jsonplaceholder.typicode.com/posts/0
# Esperado: maneja el caso gracefully

# Caso 4.5: URL que devuelve 404
python cli.py --url https://jsonplaceholder.typicode.com/este-path-no-existe
# Esperado: error claro

# Caso 4.6: API con paginación rota (next URL inválida)
# Esperado: cortar paginación limpio, no crashea

# Caso 4.7: API con millones de registros (topa en max_registros)
python cli.py --url https://dummyjson.com/products --max-registros 5
# Esperado: corta en 5, avisa "max_alcanzado=true"

# Caso 4.8: Ctrl+C durante exploración
python cli.py --url https://jsonplaceholder.typicode.com/users
# (presionar Ctrl+C después de 1 segundo)
# Esperado: sale limpio con código 130, sin stacktrace
```

**Resultado esperado**: la herramienta NO crashea en ningún caso. Devuelve mensajes entendibles o exit codes limpios.

**Qué tiene que chequear cada grupo**:

| Grupo | Verifica |
|---|---|
| **Web** | Si la app Flask (`app.py`) recibe una URL rota, no muestra 500 al usuario |
| **Fullstack** | Cada caso de error tiene su log o mensaje entendible para debugging |

---

### Corrida 5 — UX end-to-end y stress

**Objetivo**: validar la experiencia completa de un cliente real.

**Pasos completos de un usuario nuevo**:

```bash
# 1. Descubre el repo, clona, instala (como Corrida 1)
git clone https://github.com/AlbertiJ/api.git test-r5
cd test-r5
pip install -r requirements.txt

# 2. Lee el README, encuentra el manual 01
# (no se ejecuta, solo verifica que existe y es legible)

# 3. Corre el demo
python cli.py --demo

# 4. Mira el HTML generado
# Espera: HTML presentable, sin errores visuales, hash visible

# 5. Prueba con URL permitida
python cli.py --url https://jsonplaceholder.typicode.com/users --responsable "Test User"

# 6. Compra Pro (simula: copia licencia a ~/.api-explorer-license)
python scripts/generar_licencia.py test@cliente.com --out ~/.api-explorer-license

# 7. Explora una API real
python cli.py --url https://api.github.com/repos/python/cpython

# 8. Hace un diff entre dos corridas
python cli.py --url https://api.github.com/repos/python/cpython --diff-con salidas/exploracion-anterior.json

# 9. Lee el HTML del diff, ve los cambios
```

**Resultado esperado**: un usuario nuevo llega a explorar una API real, firmar el informe y hacer un diff, todo en menos de 15 minutos.

**Qué tiene que chequear cada grupo**:

| Grupo | Verifica |
|---|---|
| **Web** | El HTML es presentable a un cliente no técnico, los colores funcionan, no hay errores visuales |
| **Fullstack** | El flujo completo no tiene pasos confusos, los mensajes guían al usuario |

---

## 📝 Plantilla de reporte de error

Cuando algo falla, completar esto:

```markdown
## Bug detectado — Corrida N — Fecha

**Severidad**: 🔴 bloqueante / 🟠 mayor / 🟡 menor

**Pasos para reproducir**:
1. ...
2. ...

**Resultado esperado**:
...

**Resultado actual**:
...

**Stacktrace / log**:
```
(pegar aquí)
```

**Hipótesis de causa**:
...

**Fix propuesto**:
...

**Estado**: abierto / en progreso / arreglado / verificado

**Verificado en corrida N+1**: ✅ / ❌
```

---

## 🐛 Tabla de bugs detectados (se llena durante las 5 corridas)

| # | Severidad | Descripción corta | Detectado en corrida | Estado | Cerrado en corrida |
|---|---|---|---|---|---|
| | | | | | |

---

## ✅ Criterio de cierre del protocolo

El protocolo se considera **EXITOSO** solo cuando:

- [ ] Corrida 1: 5/5 ✅ en ambos grupos
- [ ] Corrida 2: 5/5 ✅ en ambos grupos
- [ ] Corrida 3: 5/5 ✅ en ambos grupos (incluyendo manipulación)
- [ ] Corrida 4: 0 ❌ en ambos grupos (puede haber ⚠ con justificación)
- [ ] Corrida 5: 5/5 ✅ en ambos grupos (flujo completo sin confusión)

Si algún criterio falla → el bloque del roadmap **NO se marca como production ready**.

---

## 🤖 Cómo automatizar esto con agentes

Cuando tengas agentes reales (Mavis Cloud, OpenClaw, lo que sea), este
protocolo se ejecuta así:

1. **Setup**: cada agente clona el repo en su propia carpeta temporal.
2. **Ejecución**: el agente corre los comandos de cada corrida uno por uno,
   capturando output.
3. **Comparación**: el agente compara el output real con el esperado.
4. **Reporte**: si hay diff, genera un bug con la plantilla de arriba.
5. **Loop**: 5 corridas independientes con seed aleatorio para evitar flakes.
6. **Consolidación**: los resultados de los 2 grupos se cruzan; si ambos
   reportan el mismo bug, sube de severidad automáticamente.

### Prompt template para los agentes

```
Sos el agente {web|fullstack}. Ejecutá el protocolo en
docs/PROTOCOLO-TESTING.md. Reportá:
- ✅ Pasó / ⚠ Pasó con observación / ❌ Falló por corrida.
- Bugs con la plantilla del protocolo.
- Tiempo total de las 5 corridas.
No modifiques código. No leas archivos fuera del repo. No ejecutes
comandos destructivos. Cuando termines, escribí tu reporte en
docs/REPORTES/REPORTE-{fecha}-{grupo}.md.
```

---

## 📌 Cuándo correr este protocolo

- ✅ Antes de mandar el PR a awesome-python (visibilidad)
- ✅ Antes de publicar v0.2.0 release
- ✅ Antes de la primera venta
- ✅ Después de cualquier cambio en `cli.py`, `explorer/licencia.py`,
      `scripts/generar_licencia.py`
- ✅ Una vez por mes como smoke test

---

_Mantenido por Juan Alberti — generado el 2026-06-21._
