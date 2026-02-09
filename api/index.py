from flask import Flask, request, jsonify, send_from_directory
import ast
import astor

app = Flask(__name__, static_folder=".")

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
    # Intento simple: agrega ":" faltantes al final de def / if / for / while / class
    lines = code.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "if ", "for ", "while ", "class ")) and not stripped.endswith(":"):
            lines[i] += ":"
    repaired = "\n".join(lines)

    try:
        tree = ast.parse(repaired)
        motor = AutoRepair()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        codigo_final = astor.to_source(nuevo_tree)
        return codigo_final, motor.cambios
    except Exception:
        # Si falla, devuelve el código como está
        return repaired, 0

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get("code", "")
    report = []

    try:
        ast.parse(code)
        report.append({"linea": 0, "mensaje": "No se encontraron errores", "tipo": "ok"})
        fixed_code, cambios = reparar_codigo(code)
    except SyntaxError as e:
        report.append({"linea": e.lineno, "mensaje": str(e), "tipo": "critico"})
        fixed_code, cambios = reparar_codigo(code)

    return jsonify(report=report, fixed_code=fixed_code, cambios=cambios)

@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return (code, 200, {
        "Content-Type": "text/x-python",
        "Content-Disposition": "attachment; filename=codigo_reparado.py"
    })

if __name__ == "__main__":
    app.run()
