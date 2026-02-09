import os
import ast
import astor
import re
import black
import autopep8
import isort
from flake8.api import legacy as flake8
from flask import Flask, request, jsonify, render_template, Response

# Templates al nivel superior
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)

# ----------------- AUTO REPAIR AVANZADO -----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    # Docstrings automáticas
    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant(
                value="Documentación automática añadida.")))
            self.cambios += 1
        # Convierte CamelCase a snake_case
        original = node.name
        nuevo_nombre = re.sub(r'(?<!^)(?=[A-Z])', '_', original).lower()
        if nuevo_nombre != original:
            node.name = nuevo_nombre
            self.cambios += 1
        return self.generic_visit(node)

    # Elimina bloques inútiles (if False)
    def visit_If(self, node):
        if isinstance(node.test, ast.Constant) and node.test.value is False:
            self.cambios += 1
            return None
        return self.generic_visit(node)

def reparar_codigo(code):
    # Añadir ":" faltantes
    lines = code.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "if ", "for ", "while ", "class ")) and not stripped.endswith(":"):
            lines[i] += ":"
    repaired = "\n".join(lines)

    # Reparación AST avanzada
    try:
        tree = ast.parse(repaired)
        motor = AutoRepair()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        codigo_final = astor.to_source(nuevo_tree)
    except Exception:
        codigo_final = repaired
        motor = AutoRepair()  # Para contar cambios aunque falle

    # Formateo Black
    try:
        codigo_final = black.format_str(codigo_final, mode=black.Mode())
    except Exception:
        pass

    # Formateo autopep8
    codigo_final = autopep8.fix_code(codigo_final)

    # Ordenar imports
    codigo_final = isort.code(codigo_final)

    # Auto-reparación básica de errores de indentación y comillas
    codigo_final = auto_repair_syntax(codigo_final)

    return codigo_final, motor.cambios

def auto_repair_syntax(code):
    """Repara errores simples de indentación y comillas faltantes."""
    lines = code.split("\n")
    indent = 0
    fixed_lines = []
    for line in lines:
        stripped = line.lstrip()
        # Ajustar indentación según ":" previo
        if stripped.endswith(":"):
            fixed_lines.append(" " * indent + stripped)
            indent += 4
        else:
            fixed_lines.append(" " * indent + stripped)
        # Cerrar comillas simples o dobles
        if stripped.count('"') % 2 != 0:
            fixed_lines[-1] += '"'
        if stripped.count("'") % 2 != 0:
            fixed_lines[-1] += "'"
    return "\n".join(fixed_lines)

# ----------------- ANALISIS DE ERRORES -----------------
def analizar_errores_flake8(code):
    style_guide = flake8.get_style_guide(ignore=['E501'])
    report = style_guide.input_file(filename='temp.py', lines=code.splitlines())
    errores = []
    # Parsear estadísticas para obtener línea y tipo
    for e in report.get_statistics(''):
        m = re.match(r'(\d+):(\d+) (.+)', e)
        if m:
            linea, col, msg = m.groups()
            errores.append({"linea": int(linea), "mensaje": msg, "tipo": "warning"})
        else:
            errores.append({"linea": 0, "mensaje": e, "tipo": "warning"})
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

    # Intento parse AST
    try:
        ast.parse(code)
        report.append({"linea": 0, "mensaje": "No se encontraron errores críticos", "tipo": "ok"})
    except SyntaxError as e:
        report.append({"linea": e.lineno, "mensaje": str(e), "tipo": "critico"})

    # Reparar código
    fixed_code, cambios = reparar_codigo(code)

    # Analizar errores de estilo
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
