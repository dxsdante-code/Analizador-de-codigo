import os
import re
import ast
import astor
import black
import autopep8
import isort
import requests
from flake8.api import legacy as flake8
from flask import Flask, request, jsonify, render_template, Response

# ---------------- CONFIG ----------------
HF_API_TOKEN = "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"  # Token de Hugging Face
HF_MODEL = "bigcode/starcoder"  # Modelo de ejemplo para análisis de código

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
app = Flask(__name__, template_folder=template_dir)

# ------------------ AUTO REPAIR ------------------
class PreRepair:
    """Pre-reparación básica para evitar errores graves de AST."""

    @staticmethod
    def reparar_sintaxis(code: str) -> str:
        lines = code.split("\n")
        repaired_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Agregar ":" faltante
            if stripped.startswith(("def ", "if ", "for ", "while ", "class ")) and not stripped.endswith(":"):
                line += ":"

            # Cerrar strings simples si faltan comillas
            if stripped.count('"') % 2 != 0:
                line += '"'
            if stripped.count("'") % 2 != 0:
                line += "'"

            repaired_lines.append(line)

        return "\n".join(repaired_lines)


class AutoRepair(ast.NodeTransformer):
    """Reparación con AST: docstrings y limpieza básica."""

    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant(value="Documentación automática añadida.")))
            self.cambios += 1
        return self.generic_visit(node)


# ------------------ UTILIDADES ------------------
def reparar_codigo(code: str):
    code = PreRepair.reparar_sintaxis(code)

    try:
        tree = ast.parse(code)
        motor = AutoRepair()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        codigo_final = astor.to_source(nuevo_tree)
    except Exception:
        codigo_final = code
        motor = AutoRepair()

    try:
        codigo_final = black.format_str(codigo_final, mode=black.Mode())
    except Exception:
        pass
    codigo_final = autopep8.fix_code(codigo_final)
    codigo_final = isort.code(codigo_final)

    return codigo_final, motor.cambios


def analizar_errores_flake8(code: str):
    style_guide = flake8.get_style_guide(ignore=['E501'])
    report = style_guide.input_file(filename='temp.py', lines=code.splitlines())
    errores = []
    for e in report.get_statistics(''):
        errores.append({"mensaje": e, "tipo": "warning"})
    return errores


# ------------------ IA SEMÁNTICA ------------------
def analizar_semantica_ia(code: str) -> str:
    """Usa Hugging Face Inference API para análisis semántico de código."""
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": f"Analiza este código Python y describe su función: {code}"
    }

    try:
        response = requests.post(f"https://api-inference.huggingface.co/models/{HF_MODEL}",
                                 headers=headers, json=payload, timeout=20)
        if response.status_code == 200:
            result = response.json()
            # El resultado depende del modelo, aquí simplificamos:
            if isinstance(result, list) and "generated_text" in result[0]:
                return result[0]["generated_text"]
            return str(result)
        else:
            return f"Error IA: {response.status_code}"
    except Exception as e:
        return f"Error IA: {e}"


# ------------------ RUTAS ------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get("code", "")
    report = []

    # Intento de parse con pre-reparación
    code_pre = PreRepair.reparar_sintaxis(code)
    try:
        ast.parse(code_pre)
        report.append({"linea": 0, "mensaje": "No se encontraron errores críticos", "tipo": "ok"})
    except SyntaxError as e:
        report.append({"linea": e.lineno, "mensaje": str(e), "tipo": "critico"})

    # Reparar código
    fixed_code, cambios = reparar_codigo(code)

    # Analizar estilo
    errores_flake = analizar_errores_flake8(fixed_code)
    report.extend(errores_flake)

    # Analizar semántica con IA
    semantica = analizar_semantica_ia(fixed_code)

    return jsonify(report=report, fixed_code=fixed_code, cambios=cambios, semantica=semantica)


@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(code, mimetype="text/x-python", headers={
        "Content-Disposition": "attachment; filename=codigo_reparado.py"
    })


if __name__ == "__main__":
    app.run(debug=True)
