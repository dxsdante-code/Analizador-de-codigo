import os
import ast
import astor
import black
import autopep8
import isort
import requests
from flake8.api import legacy as flake8
from flask import Flask, request, jsonify, render_template, Response

# --------------------------------------------
# CONFIG
# --------------------------------------------
HF_API_TOKEN = "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"
HF_MODEL = "bigcode/starcoder"  # Modelo para análisis de código
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# Templates al nivel superior
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)

# --------------------------------------------
# AUTO REPAIR
# --------------------------------------------
class AutoRepair(ast.NodeTransformer):
    """Agrega docstrings automáticos y mejora sintaxis simple."""
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
    """Repara errores básicos y aplica formateo automático."""

    # Corregir ":" faltantes
    lines = code.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "if ", "for ", "while ", "class ")) and not stripped.endswith(":"):
            lines[i] += ":"
    repaired = "\n".join(lines)

    # Aplicar AutoRepair AST
    try:
        tree = ast.parse(repaired)
        motor = AutoRepair()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        codigo_final = astor.to_source(nuevo_tree)
    except Exception:
        codigo_final = repaired
        motor = AutoRepair()

    # Formatear con Black
    try:
        codigo_final = black.format_str(codigo_final, mode=black.Mode())
    except Exception:
        pass

    # Formatear con autopep8
    codigo_final = autopep8.fix_code(codigo_final)

    # Organizar imports con isort
    codigo_final = isort.code(codigo_final)

    return codigo_final, motor.cambios

def analizar_errores_flake8(code: str):
    """Analiza errores de estilo con flake8."""
    style_guide = flake8.get_style_guide(ignore=["E501"])
    report = style_guide.input_file(filename="temp.py", lines=code.splitlines())
    errores = []
    for e in report.get_statistics(''):
        errores.append({"mensaje": e, "tipo": "warning"})
    return errores

# --------------------------------------------
# IA SEMÁNTICA
# --------------------------------------------
def analizar_semantica_ia(code: str):
    """Consulta a Hugging Face para obtener análisis semántico del código."""
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    prompt = f"Analiza este código Python y explica qué hace, además de sugerir mejoras:\n\n{code}\n\nRespuesta:"
    response = requests.post(HF_API_URL, headers=headers, json={"inputs": prompt})
    if response.status_code == 200:
        result = response.json()
        # Dependiendo del modelo, puede devolver texto directo o un array de dicts
        if isinstance(result, list) and "generated_text" in result[0]:
            return result[0]["generated_text"]
        elif isinstance(result, dict) and "error" in result:
            return f"Error IA: {result['error']}"
        else:
            return str(result)
    else:
        return f"Error de conexión al modelo: {response.status_code}"

# --------------------------------------------
# RUTAS
# --------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get("code", "")
    report = []

    # Intento de parse AST
    try:
        ast.parse(code)
        report.append({"linea": 0, "mensaje": "No se encontraron errores críticos", "tipo": "ok"})
    except SyntaxError as e:
        report.append({"linea": e.lineno, "mensaje": str(e), "tipo": "critico"})

    # Reparar código
    fixed_code, cambios = reparar_codigo(code)

    # Analizar errores de estilo con flake8
    errores_flake = analizar_errores_flake8(fixed_code)
    report.extend(errores_flake)

    # Análisis semántico con IA
    resumen_semantico = analizar_semantica_ia(fixed_code)

    return jsonify(report=report, fixed_code=fixed_code, cambios=cambios, semantica=resumen_semantico)

@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(code, mimetype="text/x-python", headers={
        "Content-Disposition": "attachment; filename=codigo_reparado.py"
    })

if __name__ == "__main__":
    app.run()
