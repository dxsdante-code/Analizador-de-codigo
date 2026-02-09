import os
import ast
import astor
import black
import autopep8
import isort
import re
from flask import Flask, request, jsonify, render_template, Response

# Carpeta de templates
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)


# ----------------- AUTO-REPAIR DE SYNTAX -----------------
class SyntaxAutoRepair:
    def __init__(self, codigo):
        self.original = codigo
        self.codigo = codigo
        self.cambios = []

    def reparar(self):
        # Intentos limitados para no entrar en loop infinito
        for _ in range(5):
            try:
                ast.parse(self.codigo)
                return self.codigo
            except SyntaxError as e:
                reparado = self._aplicar_fix(e)
                if not reparado:
                    break
        return self.codigo

    def _aplicar_fix(self, error):
        linea = error.lineno
        msg = str(error)
        lines = self.codigo.splitlines()

        # 1. ":" faltante
        if "expected ':'" in msg and linea:
            if re.match(r'\s*(if|for|while|def|class)\b', lines[linea-1]):
                lines[linea-1] += ":"
                self._commit("Se añadió ':' faltante", linea)
                self.codigo = "\n".join(lines)
                return True

        # 2. Indentación
        if "IndentationError" in msg or "unexpected indent" in msg:
            self.codigo = self._fix_indentacion()
            self._commit("Indentación corregida", linea)
            return True

        # 3. Comillas no cerradas
        if "EOL while scanning string literal" in msg:
            lines[linea-1] += "'"
            self._commit("Comilla cerrada automáticamente", linea)
            self.codigo = "\n".join(lines)
            return True

        # 4. Paréntesis o corchetes abiertos
        if "was never closed" in msg:
            self.codigo += "\n)"
            self._commit("Paréntesis cerrado automáticamente", linea)
            return True

        return False

    def _fix_indentacion(self):
        fixed = []
        indent = 0
        for line in self.codigo.splitlines():
            stripped = line.lstrip()
            if stripped.endswith(":"):
                fixed.append(" " * indent + stripped)
                indent += 4
            else:
                fixed.append(" " * indent + stripped)
        return "\n".join(fixed)

    def _commit(self, mensaje, linea):
        self.cambios.append({"tipo": "auto-fix", "linea": linea, "mensaje": mensaje})


# ----------------- AST PARA DOCSTRINGS -----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant(
                value="Documentación automática añadida.")))
            self.cambios += 1
        return self.generic_visit(node)


# ----------------- FUNCIONES DE ANÁLISIS -----------------
def reparar_codigo(code):
    # Primero syntax auto-repair
    reparador = SyntaxAutoRepair(code)
    code_reparado = reparador.reparar()

    # AST docstrings
    try:
        tree = ast.parse(code_reparado)
        motor = AutoRepair()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        code_final = astor.to_source(nuevo_tree)
    except Exception:
        code_final = code_reparado
        motor = AutoRepair()

    # Formateo Black
    try:
        code_final = black.format_str(code_final, mode=black.Mode())
    except Exception:
        pass

    # Formateo autopep8
    code_final = autopep8.fix_code(code_final)

    # Ordenar imports
    code_final = isort.code(code_final)

    cambios_totales = reparador.cambios + motor.cambios
    cambios_detalle = reparador.cambios + [{"tipo": "docstring", "linea": None, "mensaje": "Docstring agregado"}]*motor.cambios

    return code_final, cambios_totales, reparador.cambios


def analizar_errores_flake8(code):
    from flake8.api import legacy as flake8
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

    # Parse inicial
    try:
        ast.parse(code)
        report.append({"linea": 0, "mensaje": "No se encontraron errores críticos", "tipo": "ok"})
    except SyntaxError as e:
        report.append({"linea": e.lineno, "mensaje": str(e), "tipo": "critico"})

    # Reparar código
    fixed_code, cambios, detalle = reparar_codigo(code)

    # Analizar estilo con flake8
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
