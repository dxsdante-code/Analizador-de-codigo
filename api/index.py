import os
import ast
import astor
import autopep8
import black
import isort
import requests
from flask import Flask, request, jsonify, render_template, Response
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY no configurada en variables de entorno")

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
app = Flask(__name__, template_folder=template_dir)

# ---------------- AUTO REPAIR ----------------
class AutoRepair(ast.NodeTransformer):
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

def reparar_codigo(code):
    cambios = 0

    # Reglas simples
    lines = code.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "if ", "for ", "while ", "class ")) and not stripped.endswith(":"):
            lines[i] += ":"
            cambios += 1

    repaired = "\n".join(lines)

    try:
        tree = ast.parse(repaired)
        motor = AutoRepair()
        tree = motor.visit(tree)
        ast.fix_missing_locations(tree)
        repaired = astor.to_source(tree)
        cambios += motor.cambios
    except Exception:
        pass

    try:
        repaired = black.format_str(repaired, mode=black.Mode())
    except Exception:
        pass

    repaired = autopep8.fix_code(repaired)
    repaired = isort.code(repaired)

    return repaired, cambios

def analizar_flake8(code):
    style = flake8.get_style_guide(ignore=["E501"])
    report = style.input_file(filename="temp.py", lines=code.splitlines())
    errores = []
    for stat in report.get_statistics(""):
        errores.append({"tipo": "warning", "mensaje": stat})
    return errores

# ---------------- IA SEMÁNTICA ----------------
def analisis_semantico_ia(code):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un analizador experto de código Python. "
                    "Explica qué hace el código, qué intenta lograr y "
                    "qué cosas faltan o podrían mejorarse."
                ),
            },
            {
                "role": "user",
                "content": code,
            },
        ],
        "temperature": 0.2,
    }

    try:
        r = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error de conexión al modelo: {e}"

# ---------------- RUTAS ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get("code", "")

    report = []

    try:
        ast.parse(code)
        report.append({"tipo": "ok", "mensaje": "No se detectaron errores críticos"})
    except SyntaxError as e:
        report.append({
            "tipo": "critico",
            "linea": e.lineno,
            "mensaje": str(e)
        })

    fixed_code, cambios = reparar_codigo(code)
    report.extend(analizar_flake8(fixed_code))

    semantic = analisis_semantico_ia(fixed_code)

    return jsonify({
        "report": report,
        "fixed_code": fixed_code,
        "semantic": semantic,
        "cambios": cambios
    })

@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(
        code,
        mimetype="text/x-python",
        headers={"Content-Disposition": "attachment; filename=codigo_reparado.py"}
    )

# ---------------- LOCAL ----------------
if __name__ == "__main__":
    app.run(debug=True)
