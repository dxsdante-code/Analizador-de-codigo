import os
from flask import Flask, request, jsonify, render_template, Response
import ast
import astor
import black
import autopep8
import isort
from flake8.api import legacy as flake8

# Templates al nivel superior
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)

# ----------------- AUTO REPAIR -----------------
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
    # AST básico: docstrings y ":" faltantes
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

    # Formateo con Black
    try:
        codigo_final = black.format_str(codigo_final, mode=black.Mode())
    except Exception:
        pass

    # Formateo con autopep8
    codigo_final = autopep8.fix_code(codigo_final)

    # Organizar imports con isort
    codigo_final = isort.code(codigo_final)

    return codigo_final, motor.cambios

def analizar_errores_flake8(code):
    style_guide = flake8.get_style_guide(ignore=['E501'])
    report = style_guide.input_file(filename='temp.py', lines=code.splitlines())
    errores = []
    for e in report.get_statistics(''):
        errores.append({"mensaje": e, "tipo": "warning"})
    return errores

# ----------------- RUTAS -----------------
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

    return jsonify(report=report, fixed_code=fixed_code, cambios=cambios)

@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(code, mimetype="text/x-python", headers={
        "Content-Disposition": "attachment; filename=codigo_reparado.py"
    })

if __name__ == "__main__":
    app.run()
