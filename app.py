"""
app.py — Interfaz web mínima para correr la exploración desde el navegador.

Pensada para correr local. No tiene autenticación — solo para uso personal.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from explorer.core import ErrorExploracion, explorar
from explorer.gap import analizar_brechas

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Explorer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #f5f5f7; color: #1d1d1f;
               font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .panel { background: white; border: 1px solid #e0e0e0;
                 border-radius: 8px; padding: 1.5rem; }
        .input { background: #fafafa; border: 1px solid #d0d0d0;
                 color: #1d1d1d; width: 100%; padding: .5rem;
                 border-radius: 6px; font-family: inherit; }
        .btn { background: #0071e3; color: white; font-weight: 600;
               transition: 0.2s; }
        .btn:hover { background: #0058b0; }
        pre { background: #1d1d1d; color: #5ac8fa; padding: 1rem;
              border-radius: 6px; overflow: auto; max-height: 24rem; }
        .ghost { color: #ff4d4d; font-weight: 600; }
        .valid { color: #0071e3; }
    </style>
</head>
<body class="p-8">
    <div class="max-w-6xl mx-auto">
        <header class="mb-8 text-center">
            <h1 class="text-3xl font-bold mb-2">API Explorer</h1>
            <p class="text-gray-500">Mapeo de estructura y detección de datos sensibles</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="panel">
                <h2 class="text-xl mb-4 pb-2 border-b border-gray-200">Configuración</h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm mb-1">URL del endpoint</label>
                        <input type="text" id="url" class="input"
                               placeholder="https://api.empresa.com/v1/...">
                    </div>
                    <div>
                        <label class="block text-sm mb-1">Responsable</label>
                        <input type="text" id="responsable" class="input" value="Juan">
                    </div>
                    <div>
                        <label class="block text-sm mb-1">
                            Campos oficiales (separados por coma)
                        </label>
                        <textarea id="official_fields" class="input h-32"
                                  placeholder="nombre, legajo, area..."></textarea>
                    </div>
                    <button onclick="runInspection()"
                            class="btn w-full p-3 rounded uppercase">
                        Ejecutar análisis
                    </button>
                </div>
            </div>

            <div class="md:col-span-2 space-y-6">
                <div id="loading" class="hidden text-center text-xl">
                    Analizando estructura…
                </div>

                <div id="results" class="hidden grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div class="panel">
                        <h3 class="text-lg mb-2 pb-1 border-b border-gray-200">
                            Datos obtenidos
                        </h3>
                        <pre id="raw_data"></pre>
                    </div>

                    <div class="panel">
                        <h3 class="text-lg mb-2 pb-1 border-b border-gray-200">
                            Análisis de brechas
                        </h3>
                        <div id="gap_report" class="text-sm space-y-3"></div>
                    </div>
                </div>

                <div id="error" class="hidden p-4 bg-red-100 border
                                       border-red-400 text-red-700 rounded"></div>
            </div>
        </div>
    </div>

    <script>
        async function runInspection() {
            const url = document.getElementById('url').value;
            const responsable = document.getElementById('responsable').value;
            const official_fields = document.getElementById('official_fields').value
                .split(',').map(s => s.trim()).filter(s => s);

            if (!url) return alert('Ingrese la URL');

            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('results').classList.add('hidden');
            document.getElementById('error').classList.add('hidden');

            try {
                const response = await fetch('/explorar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, responsable, official_fields })
                });

                const data = await response.json();
                if (data.error) throw new Error(data.error);

                document.getElementById('raw_data').textContent =
                    JSON.stringify(data.raw_response, null, 2);

                const gap = data.gap;
                let gapHtml = `
                    <div class="flex justify-between mb-2">
                        <span>Coincidencia: <strong>${gap.porcentaje_coincidencia}%</strong></span>
                        <span>Total reales: <strong>${gap.total_reales}</strong></span>
                    </div>
                    <div class="mb-4">
                        <p class="text-gray-500 mb-1">Campos no documentados:</p>
                        <ul class="list-disc pl-5">
                            ${gap.campos_fantasma.length
                                ? gap.campos_fantasma.map(f => `<li class="ghost">${f}</li>`).join('')
                                : '<li class="text-gray-400">Ninguno detectado</li>'}
                        </ul>
                    </div>
                    <div>
                        <p class="text-gray-500 mb-1">Campos validados:</p>
                        <ul class="list-disc pl-5">
                            ${gap.campos_validados.map(f => `<li class="valid">${f}</li>`).join('')}
                        </ul>
                    </div>
                `;
                document.getElementById('gap_report').innerHTML = gapHtml;
                document.getElementById('results').classList.remove('hidden');

            } catch (e) {
                document.getElementById('error').textContent = e.message;
                document.getElementById('error').classList.remove('hidden');
            } finally {
                document.getElementById('loading').classList.add('hidden');
            }
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/explorar", methods=["POST"])
def explorar_endpoint():
    params = request.json or {}
    url = params.get("url")
    responsable = params.get("responsable", "no_especificado")
    official_fields = params.get("official_fields", [])

    try:
        resultado = explorar(
            url=url,
            responsable=responsable,
            cliente="exploración_web",
            formato="json",
        )

        exploracion = resultado["exploracion"]
        estructura = exploracion["estructura"]

        gap_result = analizar_brechas(estructura, official_fields)

        return jsonify({
            "raw_response": estructura,
            "gap": gap_result,
            "hash": exploracion.get("hash_sha256"),
            "resumen": exploracion.get("resumen"),
        })
    except ErrorExploracion as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error interno: {str(e)}"}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(port=5000, debug=False)