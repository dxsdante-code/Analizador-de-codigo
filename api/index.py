from flask import Flask, render_template, request, jsonify, Response
import ast
import astor
import re
import os
import textwrap

# =========================
# FLASK SETUP (VERCEL SAFE)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)


# =========================
# AUTO REPAIR SINTÁCTICO
# =========================
class SyntaxAutoRepair:
    def __init__(self, codigo: str):
        """Motor de reparación sintáctica automática."""
        self.original = codigo
        self.codigo = textwrap.dedent(codigo)
        self.cambios = []
        self.max_intentos = 6

    def reparar(self) -> str:
        """Intenta reparar errores de sintaxis comunes."""
        for _ in range(self.max_intentos):
            try:
                ast.parse(self.codigo)
                return self.codigo
            except SyntaxError as e:
                if not self._aplicar_fix(e):
                    break
        return self.codigo

    def _aplicar_fix(self, error: SyntaxError) -> bool:
        linea = error.lineno or 1
        msg = str(error)
        lineas = self.codigo.splitlines()

        # Proteger índice
        if linea > len(lineas):
            linea = len(lineas)

        # ':' faltante
        if "expected ':'" in msg:
            if re.match(r"\s*(if|for|while|def|class)\b", lineas[linea - 1]):
                lineas[linea - 1] += ":"
                self._commit("Se añadió ':' faltante", linea)
                self.codigo = "\n".join(lineas)
                return True

        # Comillas abiertas
        if "EOL while scanning string literal" in msg:
            lineas[linea - 1] += "'"
            self._commit("Comilla cerrada automáticamente", linea)
            self.codigo = "\n".join(lineas)
            return True

        # Paréntesis o corchetes
        if "was never closed" in msg:
            self.codigo += "\n)"
            self._commit("Paréntesis cerrado automáticamente", linea)
            return True

        # Indentación (heurística)
        if "IndentationError" in msg or "unexpected indent" in msg:
            self.codigo = self._fix_indentacion()
            self._commit("Indentación corregida", linea)
            return True

        # JSON → Python
        if self._parece_json():
            self.codigo = (
                self.codigo.replace("true", "True")
                .replace("false", "False")
                .replace("null", "None")
            )
            self._commit("JSON convertido a Python", 0)
            return True

        return False

    def _fix_indentacion(self) -> str:
        fixed = []
        indent = 0
        for line in self.codigo.splitlines():
            stripped = line.lstrip()
            if not stripped:
                fixed.append("")
                continue
            if stripped.endswith(":"):
                fixed.append(" " * indent + stripped)
                indent += 4
            else:
                fixed.append(" " * indent + stripped)
        return "\n".join(fixed)

    def _parece_json(self) -> bool:
        txt = self.codigo.strip()
        return txt.startswith("{") and ":" in txt and '"' in txt

    def _commit(self, mensaje: str, linea: int):
        self.cambios.append({
            "tipo": "auto-fix",
            "linea": linea,
            "mensaje": mensaje,
            "confianza": 0.9
        })


# =========================
# AST REFACTOR
# =========================
class SuperMotor(ast.NodeTransformer):
    def __init__(self):
        """Motor de mejoras semánticas."""
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(
                    value=ast.Constant(
                        "Documentación generada automáticamente."
                    )
                )
            )
            self.cambios += 1
        return self.generic_visit(node)


# =========================
# ROUTES
# =========================
@app.route("/")
def index():
    """Página principal."""
    return render_template("index.html")


@app.route("/analizar", methods=["POST"])
def analizar():
    try:
        data = request.json or {}
        codigo = data.get("code", "")

        reparador = SyntaxAutoRepair(codigo)
        codigo_reparado = reparador.reparar()

        tree = ast.parse(codigo_reparado)
        motor = SuperMotor()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)

        codigo_final = astor.to_source(nuevo_tree)

        return jsonify({
            "hallazgos": reparador.cambios,
            "codigo_corregido": codigo_final,
            "cambios_realizados": len(reparador.cambios) + motor.cambios
        })

    except Exception as e:
        return jsonify({
            "hallazgos": [{
                "tipo": "critico",
                "linea": 0,
                "mensaje": str(e)
            }],
            "cambios_realizados": 0
        }), 400


@app.route("/descargar", methods=["POST"])
def descargar():
    codigo = request.form.get("code", "")
    return Response(
        codigo,
        mimetype="text/x-python",
        headers={
            "Content-Disposition": "attachment; filename=codigo_reparado.py"
        }
    )
