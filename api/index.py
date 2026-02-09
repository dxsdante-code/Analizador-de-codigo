import os
import ast
import astor
import re
import black
import autopep8
import isort
from flake8.api import legacy as flake8
from flask import Flask, request, jsonify, render_template, Response
import requests

# ------------------ CONFIG ------------------
HF_API_TOKEN = "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"
HF_MODEL = "bigcode/starcoder"  # Modelo para análisis de código en HF

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
app = Flask(__name__, template_folder=template_dir)

# ------------------ AUTO REPAIR ------------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant(
                value="Documentación automática añadida.")))
            self.cambios += 1
        return self.generic_visit(node)

def reparar_codigo(code):
    # Corregir ":" faltantes
    lines = code.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "if ", "for ", "while ", "class ")) and not stripped.endswith(":"):
            lines[i] += ":"
    repaired = "\n".join(lines)

    # AST para docstrings
    try:
        tree = ast.parse(repaired)
        motor = AutoRepair()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        codigo_final = astor.to_source(nuevo_tree)
    except Exception:
        codigo_final = repaired

    # Formateo Black
    try:
        codigo_final = black.format_str(codigo_final, mode=black.Mode())
    except Exception:
        pass

    # Formateo autopep8
    codigo_final = autopep8.fix_code(codigo_final)

    # Organizar imports con isort
    codigo_final = isort.code(codigo_final)

    return codigo_final, motor.cambios

# ------------------ ANALIZAR ESTILO ------------------
def analizar_errores_flake8(code):
    style_guide = flake8.get_style_guide(ignore=['E501'])
    report = style_guide.input_file(filename='temp.py', lines=code.splitlines())
    errores = []
    for e in report.get_statistics(''):
        errores.append({"mensaje": e, "tipo": "warning"})
    return errores

# ------------------ ANÁLISIS SEMÁNTICO HF ------------------
def analizar_semantica_hf(codigo):
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": f"Analiza este código Python. Explica su propósito y sugiere mejoras:\n{codigo}\nRespuesta:"
    }
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{HF_MODEL}",
            headers=headers,
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            resultado = response.json()
            if isinstance(resultado, list) and "generated_text" in resultado[0]:
                return resultado[0]["generated_text"]
            return str(resultado)
        else:
            return f"Error API Hugging Face: {response.status_code}"
    except Exception as e:
        return f"Error al llamar API HF: {e}"

# ------------------ RUTAS ------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get("code", "")

    # 1️⃣ Reparar código automáticamente
    fixed_code, cambios = reparar_codigo(code)

    # 2️⃣ Analizar errores de estilo
    errores_flake = analizar_errores_flake8(fixed_code)

    # 3️⃣ Analizar semántica con Hugging Face
    semantica = analizar_semantica_hf(fixed_code)

    return jsonify({
        "report": errores_flake,
        "fixed_code": fixed_code,
        "cambios": cambios,
        "semantica": semantica
    })

@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(code, mimetype="text/x-python", headers={
        "Content-Disposition": "attachment; filename=codigo_reparado.py"
    })

# ------------------ MAIN ------------------
if __name__ == "__main__":
    app.run()
