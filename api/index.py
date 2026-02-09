import os
import re
import ast
import astor
import black
import autopep8
import isort
from flask import Flask, request, jsonify, render_template, Response
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
app = Flask(__name__, template_folder=template_dir)

MAX_REPAIR_ATTEMPTS = 3

# ---------------- PRE-SCAN TEXTUAL ----------------
COMMON_FIXES = [
    (r"with open\((.*?)\) as (\w+)\n", r"with open(\1) as \2:\n"),
    (r"\belse\s*\n", "else:\n"),
    (r"\btry\s*\n", "try:\n"),
    (r"\bexcept\s*\n", "except Exception:\n"),
    (r"f\.close\b", "f.close()"),
    (r"\)\s*\n\s*\(", "),\n("),
    (r"==\s*None", "is None"),
]

def prescan_textual(code: str) -> str:
    for pattern, repl in COMMON_FIXES:
        code = re.sub(pattern, repl, code)
    return code

# ---------------- INDENTACIÓN HEURÍSTICA ----------------
def fix_indentation(code: str) -> str:
    lines = code.splitlines()
    fixed = []
    indent = 0

    for line in lines:
        stripped = line.strip()

        if stripped.startswith(("else", "elif", "except", "finally")):
            indent -= 1

        fixed.append("    " * max(indent, 0) + stripped)

        if stripped.endswith(":"):
            indent += 1

    return "\n".join(fixed)

# ---------------- AST AUTO-REPAIR ----------------
class AutoRepairAST(ast.NodeTransformer):
    def __init__(self):
        self.cambios = []

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(value=ast.Constant(value="Documentación automática añadida."))
            )
            self.cambios.append("Docstring añadido")
        if not node.body:
            node.body.append(ast.Pass())
            self.cambios.append("Pass añadido en función vacía")
        return self.generic_visit(node)

    def visit_If(self, node):
        if not node.orelse:
            node.orelse = [ast.Pass()]
            self.cambios.append("Else añadido automáticamente")
        return self.generic_visit(node)

# ---------------- VALIDACIÓN ----------------
def validar_codigo(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

# ---------------- FORMATEO FINAL ----------------
def formatear_codigo(code: str) -> str:
    try:
        code = black.format_str(code, mode=black.Mode())
    except Exception:
        pass

    code = autopep8.fix_code(code)
    code = isort.code(code)
    return code

# ---------------- FLAKE8 ----------------
def analizar_flake8(code: str):
    style = flake8.get_style_guide(ignore=["E501"])
    report = style.input_file(filename="temp.py", lines=code.splitlines())
    errores = []

    for stat in report.get_statistics(""):
        errores.append({
            "tipo": "style",
            "mensaje": stat
        })

    return errores

# ---------------- MOTOR PRINCIPAL ----------------
def reparar_codigo(code: str):
    cambios = []
    code = prescan_textual(code)
    code = fix_indentation(code)

    for intento in range(MAX_REPAIR_ATTEMPTS):
        try:
            tree = ast.parse(code)
            motor = AutoRepairAST()
            nuevo = motor.visit(tree)
            ast.fix_missing_locations(nuevo)
            code = astor.to_source(nuevo)
            cambios.extend(motor.cambios)
            break
        except SyntaxError:
            code = fix_indentation(code)

    code = formatear_codigo(code)
    return code, cambios

# ---------------- RUTAS ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    original = data.get("code", "")

    reporte = []
    try:
        ast.parse(original)
        reporte.append({
            "tipo": "ok",
            "mensaje": "No se encontraron errores críticos"
        })
    except SyntaxError as e:
        reporte.append({
            "tipo": "syntax",
            "linea": e.lineno,
            "mensaje": str(e)
        })

    fixed_code, cambios = reparar_codigo(original)
    flake_errors = analizar_flake8(fixed_code)

    reporte.extend(flake_errors)

    confianza = min(90, 60 + len(cambios) * 5)

    return jsonify(
        reporte=reporte,
        codigo_corregido=fixed_code,
        cambios_realizados=cambios,
        confianza=f"{confianza}%"
    )

@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(
        code,
        mimetype="text/x-python",
        headers={"Content-Disposition": "attachment; filename=codigo_reparado.py"},
    )

if __name__ == "__main__":
    app.run(debug=True)
