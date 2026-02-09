from flask import Flask, request, jsonify, render_template, Response
import ast
import astor
import parso
import black
import re
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)


# =========================
# AUTO REPAIR SINTÁCTICO
# =========================
class SyntaxAutoRepair:
    def __init__(self, codigo):
        self.codigo = codigo
        self.cambios = []
        self.max_intentos = 5

    def reparar(self):
        for _ in range(self.max_intentos):
            try:
                ast.parse(self.codigo)
                return self.codigo
            except SyntaxError as e:
                if not self._fix(e):
                    break
        return self.codigo

    def _fix(self, error):
        linea = error.lineno or 1
        msg = str(error)
        lines = self.codigo.splitlines()

        # ':' faltante
        if "expected ':'" in msg and linea <= len(lines):
            if re.match(r"\s*(if|for|while|def|class)\b", lines[linea - 1]):
                lines[linea - 1] += ":"
                self._log("':' agregado", linea)
                self.codigo = "\n".join(lines)
                return True

        # comillas abiertas
        if "EOL while scanning string literal" in msg:
            lines[linea - 1] += "'"
            self._log("Comilla cerrada", linea)
            self.codigo = "\n".join(lines)
            return True

        # paréntesis sin cerrar
        if "was never closed" in msg:
            self.codigo += "\n)"
            self._log("Paréntesis cerrado", linea)
            return True

        return False

    def _log(self, mensaje, linea):
        self.cambios.append({
            "tipo": "auto-fix",
            "linea": linea,
            "mensaje": mensaje,
            "confianza": 0.95
        })


# =========================
# AST REFACTOR
# =========================
class SuperMotor(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(value=ast.Constant("Documentación generada automáticamente."))
            )
            self.cambios += 1
        return self.generic_visit(node)


# =========================
# ROUTES
# =========================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analizar", methods=["POST"])
def analizar():
    data = request.json
    codigo = data.get("code", "")

    # 1️⃣ Parso (análisis tolerante)
    parso.parse(codigo)

    # 2️⃣ Auto-repair
    reparador = SyntaxAutoRepair(codigo)
    codigo_reparado = reparador.reparar()

    # 3️⃣ AST refactor
    tree = ast.parse(codigo_reparado)
    motor = SuperMotor()
    tree = motor.visit(tree)
    ast.fix_missing_locations(tree)

    codigo_final = astor.to_source(tree)

    # 4️⃣ Black (formato seguro)
    try:
        codigo_final = black.format_str(codigo_final, mode=black.FileMode())
    except Exception:
        pass

    return jsonify({
        "hallazgos": reparador.cambios,
        "codigo_corregido": codigo_final,
        "cambios_realizados": len(reparador.cambios) + motor.cambios
    })


@app.route("/descargar", methods=["POST"])
def descargar():
    codigo = request.form.get("code", "")
    return Response(
        codigo,
        mimetype="text/x-python",
        headers={"Content-Disposition": "attachment; filename=codigo_corregido.py"}
    )
