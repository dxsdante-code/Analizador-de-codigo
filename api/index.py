from flask import Flask, render_template, request, jsonify
import ast
import astor
import re
import os

# ---------------- CONFIG ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# ---------------- CAPA 1: PRE-PARSER ----------------
class PreParser:
    def __init__(self, code):
        self.code = code
        self.report = []

    def normalize(self):
        self.code = self.code.replace("\t", "    ")
        self.code = re.sub(r"\btrue\b", "True", self.code, flags=re.I)
        self.code = re.sub(r"\bfalse\b", "False", self.code, flags=re.I)
        self.code = re.sub(r"\bnull\b", "None", self.code, flags=re.I)
        return self.code

    def fix_colons(self):
        lines = []
        for i, line in enumerate(self.code.splitlines()):
            if re.match(r"\s*(def|if|for|while|class)\b", line) and not line.rstrip().endswith(":"):
                line += ":"
                self.report.append({
                    "tipo": "auto-fix",
                    "linea": i + 1,
                    "mensaje": "Se añadió ':' faltante"
                })
            lines.append(line)
        self.code = "\n".join(lines)
        return self.code

    def run(self):
        self.normalize()
        self.fix_colons()
        return self.code, self.report


# ---------------- CAPA 2: AUTO-REPAIR SYNTAX ----------------
class SyntaxAutoRepair:
    def __init__(self, code):
        self.code = code
        self.report = []

    def repair(self):
        for _ in range(5):
            try:
                ast.parse(self.code)
                return self.code
            except SyntaxError as e:
                if not self.apply_fix(e):
                    break
        return self.code

    def apply_fix(self, error):
        lines = self.code.splitlines()
        ln = error.lineno - 1 if error.lineno else 0
        msg = str(error)

        if "expected ':'" in msg and ln < len(lines):
            lines[ln] += ":"
            self._log(ln + 1, "Se corrigió ':' faltante")
        elif "EOL while scanning string literal" in msg:
            lines[ln] += "'"
            self._log(ln + 1, "Se cerró comilla automáticamente")
        elif "was never closed" in msg:
            self.code += "\n)"
            self._log(ln + 1, "Se cerró paréntesis automáticamente")
        else:
            return False

        self.code = "\n".join(lines)
        return True

    def _log(self, line, msg):
        self.report.append({
            "tipo": "auto-fix",
            "linea": line,
            "mensaje": msg
        })


# ---------------- CAPA 3: AST REFACTOR ----------------
class ASTRefactor(ast.NodeTransformer):
    def __init__(self):
        self.changes = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(value=ast.Constant("Docstring generado automáticamente."))
            )
            self.changes += 1
        return self.generic_visit(node)


# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analizar", methods=["POST"])
def analizar():
    try:
        code = request.json.get("code", "")

        # Capa 1
        pre = PreParser(code)
        code, report1 = pre.run()

        # Capa 2
        syntax = SyntaxAutoRepair(code)
        code = syntax.repair()

        # AST
        tree = ast.parse(code)
        refactor = ASTRefactor()
        tree = refactor.visit(tree)
        ast.fix_missing_locations(tree)

        final_code = astor.to_source(tree)

        return jsonify({
            "errores": report1 + syntax.report,
            "codigo_corregido": final_code
        })

    except Exception as e:
        return jsonify({
            "errores": [{
                "tipo": "critico",
                "linea": 0,
                "mensaje": str(e)
            }],
            "codigo_corregido": ""
        }), 400


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.run(debug=True)
