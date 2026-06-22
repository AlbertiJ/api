# CI workflow — `tests.yml`

> **⚠ NO está en el repo todavía.** El push inicial fue rechazado porque
> el Personal Access Token usado no tenía el scope `workflow` (es un
> scope especial que solo sirve para crear/modificar archivos en
> `.github/workflows/`). Para subirlo, Juan tiene que hacerlo con su
> token que sí tiene ese scope.

## Por qué hace falta

- En cada push a `main` corre los 92 tests automáticamente
- Marca el commit con ✅ verde o ❌ rojo
- Genera un badge que podés mostrar en el README
- Bloquea PRs con tests rotos

## Cómo subirlo

### Opción 1 — Con `git push` desde tu máquina local

1. Asegurate de que el archivo `.github/workflows/tests.yml` esté en tu
   working tree (si seguís los pasos de este agente, debería estarlo).
2. Desde la raíz del repo:
   ```bash
   git add .github/workflows/tests.yml
   git commit -m "ci: agregar GitHub Actions para correr 92 tests automáticamente"
   git push origin main
   ```
3. Si tu PAT tiene scope `workflow`, se sube. Si no, regenerá el PAT en
   https://github.com/settings/tokens con los scopes `repo` + `workflow`.

### Opción 2 — Desde la UI de GitHub

1. Andá a https://github.com/AlbertiJ/api/tree/main/.github/workflows/new
2. Pegá el contenido de `.github/workflows/tests.yml` (está en tu
   working tree local).
3. Commit directo desde la UI.

## Qué hace el workflow (resumen)

- Se dispara en push a `main` y en pull_request
- Corre en Ubuntu con Python 3.10, 3.11 y 3.12
- Instala dependencias con `pip install -r requirements.txt`
- Corre `pytest tests/ -v --tb=short`
- Reporta resultado con badge verde/rojo en el commit

## Contenido del workflow

El archivo está en `.github/workflows/tests.yml` en el working tree local.
También lo dejé copiado al final de este documento para referencia.

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('requirements.txt') }}
      - run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short
```

## Cómo verificar que funciona

Después de subir el workflow:

1. Hacé un push trivial (ej. un cambio en README.md).
2. Andá a https://github.com/AlbertiJ/api/actions
3. Tendrías ver el job "tests" corriendo.
4. Cuando termina, el badge al lado del README muestra ✅ passing.

## Badge sugerido para el README

```markdown
![Tests](https://github.com/AlbertiJ/api/actions/workflows/tests.yml/badge.svg)
```

Pegalo arriba del título en el README una vez que el workflow esté corriendo.
