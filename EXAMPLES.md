# Guía de pruebas — API Explorer

Comandos rápidos para verificar que el explorador funciona.

## Comando base

`python.exe .\cli.py --url [URL] --responsable "[TU_NOMBRE]" --cliente "[CLIENTE]"`

## APIs públicas para probar

### 1. DummyJSON (estructura compleja)
Ideal para probar detección de datasets múltiples.

```powershell
python.exe .\cli.py --url https://dummyjson.com --responsable "Juan" --cliente "Prueba Dummy"
```

### 2. RandomUser (datos sensibles)
Genera perfiles con PII. Ideal para probar el detector.

```powershell
python.exe .\cli.py --url https://randomuser.me/api/ --responsable "Juan" --cliente "Prueba PII"
```

### 3. JSONPlaceholder (rápido)
La más ligera y estable.

```powershell
python.exe .\cli.py --url https://jsonplaceholder.typicode.com --responsable "Juan" --cliente "Prueba Simple"
```

### 4. ReqRes (gestión de usuarios)
Para probar el flujo sobre endpoints de usuarios.

```powershell
python.exe .\cli.py --url https://reqres.in --responsable "Juan" --cliente "Prueba ReqRes"
```

## Modo demo (sin internet)

```powershell
python.exe .\cli.py --demo
```

## Tips

1. **Salidas**: todos los reportes van a `salidas/`.
2. **Formatos**: `--formato json`, `--formato csv` o `--formato html`.
3. **URL raíz**: usá la URL raíz de la API (ej. `https://api.empresa.com`)
   en lugar de un endpoint específico, así el explorador puede mapear
   toda la estructura.
4. **Rate-limit**: si la API es sensible al ritmo, subí las pausas:
   `--pausa-min 2.0 --pausa-max 4.0`.