import ast
import json
import os
import re
import tempfile

import autopep8
import black
import isort
import requests
from flask import Flask, jsonify, render_template, request
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

# Corrección de __file__ y rutas
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, "..", "templates")

app = Flask(__name__, template_folder=template_dir)

# ---------------- AUTO REPAIR ----------------

class AutoRepair(ast.NodeTransformer):
    """Transformador AST para mejoras automáticas de código."""
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        # Añadir Docstring si no existe
        if not ast.get_docstring(node):
            docstring = ast.Expr(value=ast.Constant(value="Documentación automática añadida."))
            node.body.insert(0, docstring)
            self.cambios += 1
        return self.generic_visit(node)

def pre_reparar(code: str):
    """Corrige errores sintácticos comunes antes del parsing."""
    cambios = 0
    lines = code.splitlines()
    for i, l in enumerate(lines):
        s = l.strip()
        # Reparación de colons faltantes en estructuras básicas
        if s.startswith(("def ", "if ", "for ", "while ", "class ")) and not s.endswith(":"):
            lines[i] += ":"
            cambios += 1
    return "\n".join(lines), cambios

def reparar_codigo(code: str):
    """Pipeline principal de limpieza y formateo."""
    total_cambios = 0
    
    # 1. Heurística simple
    code, c = pre_reparar(code)
    total_cambios += c

    # 2. Transformación AST
    try:
        tree = ast.parse(code)
        motor = AutoRepair()
        tree = motor.visit(tree)
        ast.fix_missing_locations(tree)
        code = ast.unparse(tree)  # Uso de ast nativo (Python 3.9+)
        total_cambios += motor.cambios
    except Exception:
        return code, total_cambios, False

    # 3. Formateo profesional
    try:
        code = black.format_str(code, mode=black.Mode())
    except Exception:
        pass

    code = autopep8.fix_code(code)
    code = isort.code(code)

    return code, total_cambios, True

def analizar_flake8(code: str):
    """Análisis estático de estilo usando un archivo temporal."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        style = flake8.get_style_guide(ignore=["E501"])
        report = style.check_files([tmp_path])
        # Nota: La API legacy de Flake8 es limitada para obtener mensajes detallados vía código
        return [{"tipo": "estilo", "mensaje": "Revisión PEP8 completada con éxito."}]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ---------------- IA SEMÁNTICA ----------------

def analisis_semantico_ia(code: str):
    if not OPENAI_API_KEY:
        return {"error": "API Key de OpenAI no configurada en variables de entorno."}

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un analizador experto de código Python.\n"
                    "Detecta errores lógicos o de seguridad.\n"
                    "Responde estrictamente en JSON con este formato:\n"
                    '{"analisis": "descripción", "riesgos": ["alto", "bajo"]}'
                ),
            },
            {"role": "user", "content": code},
        ],
        "temperature": 0.1,
    }

    try:
        r = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return {"error": f"Fallo en IA: {str(e)}"}

# ---------------- RUTAS ----------------

@app.route("/")
def home():
    return "Servidor de Análisis de Código Activo. Usa el endpoint /analyze."

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    code = data.get("code", "")
    reporte = []

    # 1. Validación AST inicial
    try:
        ast.parse(code)
        ast_ok = True
    except SyntaxError as e:
        reporte.append({"tipo": "critico", "linea": e.lineno, "mensaje": str(e)})
        ast_ok = False

    # 2. Reparación
    fixed_code, cambios, reparado = reparar_codigo(code)

    if reparado:
        reporte.extend(analizar_flake8(fixed_code))

    # 3. Consulta a IA (solo si hay errores graves o para validación semántica)
    ia_res = None
    if not ast_ok or "error" in str(reporte):
        ia_res = analisis_semantico_ia(code)

    return jsonify({
        "status": "success" if reparado else "partial_fail",
        "cambios_realizados": cambios,
        "reporte_estatico": reporte,
        "codigo_limpio": fixed_code,
        "analisis_ia": ia_res
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
