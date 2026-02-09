import os
import ast
import astor
import requests

import black
import autopep8
import isort

from flask import Flask, request, jsonify, render_template, Response
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------
BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "templates"))

HF_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL_URL = "https://api-inference.huggingface.co/models/bigcode/starcoder"

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# ---------------- AUTO REPAIR AST ----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(value=ast.Constant(value="Documentación automática añadida."))
            )
            self.cambios += 1
        return self.generic_visit(node)


def reparar_codigo(code: str):
    """Correcciones sintácticas + formato"""
    cambios = 0

    # Fix ':' faltantes
    lines = code.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "if ", "for ", "while ", "class ")) and not stripped.endswith(":"):
            lines[i] += ":"
            cambios += 1

    repaired = "\n".join(lines)

    # AST
    try:
        tree = ast.parse(repaired)
        motor = AutoRepair()
        tree = motor.visit(tree)
        ast.fix_missing_locations(tree)
        repaired = astor.to_source(tree)
        cambios += motor.cambios
    except Exception:
        pass

    # Formatters
    try:
        repaired = black.format_str(repaired, mode=black.Mode())
    except Exception:
        pass

    repaired = autopep8.fix_code(repaired)
    repaired = isort.code(repaired)

    return repaired, cambios


def analizar_flake8(code: str):
    style = flake8.get_style_guide(ignore=["E501"])
    report = style.input_file(filename="temp.py", lines=code.splitlines())

    errores = []
    for e in report.get_statistics(""):
        errores.append({"tipo": "warning", "mensaje": e})
    return errores


# ---------------- IA SEMÁNTICA ----------------
def analisis_semantico_ia(code: str):
    if not HF_TOKEN:
        return "IA no configurada (HF_API_TOKEN faltante)"

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }

    prompt = f"""
Analiza el siguiente código Python.
Explica qué intenta hacer, qué le falta y qué errores lógicos existen.
NO reescribas el código, SOLO análisis.

Código:
{code}
"""

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 300,
            "temperature": 0.2
        }
    }

    try:
        r = requests.post(HF_MODEL_URL, headers=headers, json=payload, timeout=25)
        if r.status_code != 200:
            return f"Error IA ({r.status_code})"

        data = r.json()

        if isinstance(data, list) and "generated_text" in data[0]:
            return data[0]["generated_text"]

        return "Respuesta IA no válida"

    except Exception as e:
        return f"Error de conexión IA: {str(e)}"


# ---------------- RUTAS ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True)
        code = data.get("code", "")

        report = []

        # AST check
        try:
            ast.parse(code)
            report.append({"tipo": "ok", "mensaje": "Sin errores críticos de sintaxis"})
        except SyntaxError as e:
            report.append({
                "tipo": "critico",
                "linea": e.lineno,
                "mensaje": str(e)
            })

        fixed_code, cambios = reparar_codigo(code)
        report.extend(analizar_flake8(fixed_code))

        semantic = analisis_semantico_ia(code)

        return jsonify({
            "report": report,
            "fixed_code": fixed_code,
            "semantic": semantic,
            "cambios": cambios
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(
        code,
        mimetype="text/x-python",
        headers={"Content-Disposition": "attachment; filename=codigo_reparado.py"},
    )


# Local only
if __name__ == "__main__":
    app.run(debug=True)
