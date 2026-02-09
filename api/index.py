import ast
import os
import difflib
import requests

import astor
import autopep8
import black
import isort
from flake8.api import legacy as flake8
from flask import Flask, jsonify, render_template, request, Response

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

MODE = "assist"  # strict | assist

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
app = Flask(__name__, template_folder=template_dir)


# ---------------- UTILIDADES ----------------
def ast_ok(code):
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, e


def diff_code(original, fixed):
    diff = []
    for i, s in enumerate(difflib.ndiff(original.splitlines(), fixed.splitlines()), 1):
        if s.startswith("- ") or s.startswith("+ "):
            diff.append({"linea": i, "cambio": s})
    return diff


# ---------------- MOTOR DETERMINISTA ----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant("Docstring automático")))
            self.cambios += 1
        return self.generic_visit(node)


def reparar_determinista(code):
    cambios = 0
    lines = code.splitlines()

    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith(("def ", "if ", "for ", "while ", "class ", "with ", "try", "except")) and not s.endswith(":"):
            lines[i] += ":"
            cambios += 1

    code = "\n".join(lines)

    try:
        tree = ast.parse(code)
        ar = AutoRepair()
        tree = ar.visit(tree)
        ast.fix_missing_locations(tree)
        code = astor.to_source(tree)
        cambios += ar.cambios
    except Exception:
        pass

    try:
        code = black.format_str(code, mode=black.Mode())
    except Exception:
        pass

    code = autopep8.fix_code(code)
    code = isort.code(code)

    return code, cambios


# ---------------- IA LOCAL (CONTROLADA) ----------------
def ia_corregir_error(code, error):
    prompt = f"""
Corrige SOLO el error de sintaxis indicado.
NO cambies la lógica.
NO agregues funciones.
NO reestructures el código.
Devuelve SOLO código Python válido.

Error:
{error}

Código:
{code}
"""
    r = requests.post(
        OPENAI_ENDPOINT,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        },
        timeout=15,
    )

    data = r.json()
    return data["choices"][0]["message"]["content"]


def ia_explicar_y_alternativas(code, error):
    prompt = f"""
Explica el error de este código.
NO lo corrijas.
Propón alternativas si existen.

Error:
{error}

Código:
{code}

Devuelve JSON con:
- descripcion
- alternativas (lista con descripcion y codigo_sugerido)
"""
    r = requests.post(
        OPENAI_ENDPOINT,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=15,
    )
    return r.json()["choices"][0]["message"]["content"]


# ---------------- RUTAS ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    code = request.json.get("code", "")
    original = code
    report = []
    alternatives = []

    code, det_changes = reparar_determinista(code)

    ok, error = ast_ok(code)

    if not ok and MODE == "assist":
        try:
            fixed = ia_corregir_error(code, error)
            ok2, _ = ast_ok(fixed)
            if ok2:
                code = fixed
                report.append({"tipo": "ia", "mensaje": "IA corrigió error local"})
            else:
                alternatives.append(ia_explicar_y_alternativas(code, error))
        except Exception:
            alternatives.append(ia_explicar_y_alternativas(code, error))

    diff = diff_code(original, code)

    return jsonify(
        {
            "fixed_code": code,
            "report": report,
            "alternatives": alternatives,
            "diff": diff,
            "cambios": det_changes,
            "ok": ast_ok(code)[0],
        }
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
