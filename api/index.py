import ast
import json
import os
import re

import astor
import autopep8
import black
import isort
import requests
from flask import Flask, jsonify, render_template, request
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

template_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "templates")
)
app = Flask(__name__, template_folder=template_dir)

# ---------------- AUTO REPAIR ----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(value=ast.Constant("Documentación automática añadida."))
            )
            self.cambios += 1
        return self.generic_visit(node)


def pre_reparar(code: str):
    cambios = 0
    lines = code.splitlines()
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith(("def ", "if ", "for ", "while ", "class ")) and not s.endswith(":"):
            lines[i] += ":"
            cambios += 1
    return "\n".join(lines), cambios


def reparar_codigo(code: str):
    total_cambios = 0

    code, c = pre_reparar(code)
    total_cambios += c

    try:
        tree = ast.parse(code)
        motor = AutoRepair()
        tree = motor.visit(tree)
        ast.fix_missing_locations(tree)
        code = astor.to_source(tree)
        total_cambios += motor.cambios
    except Exception:
        return code, total_cambios, False

    try:
        code = black.format_str(code, mode=black.Mode())
    except Exception:
        pass

    code = autopep8.fix_code(code)
    code = isort.code(code)

    return code, total_cambios, True


def analizar_flake8(code: str):
    style = flake8.get_style_guide(ignore=["E501"])
    report = style.input_file("temp.py", lines=code.splitlines())
    return [{"tipo": "warning", "mensaje": s} for s in report.get_statistics("")]


# ---------------- IA SEMÁNTICA (CONTRATO) ----------------
def analisis_semantico_ia(code: str):
    if not OPENAI_API_KEY:
        return {"error": "IA no configurada"}

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
                    "Eres un analizador experto de código Python.\n"
                    "Responde EXCLUSIVAMENTE en JSON válido siguiendo el contrato definido.\n"
                    "NO devuelvas código corregido."
                ),
            },
            {"role": "user", "content": code},
        ],
        "temperature": 0.1,
    }

    try:
        r = requests.post(
            OPENAI_ENDPOINT, headers=headers, json=payload, timeout=20
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        return {"error": str(e)}


# ---------------- RUTAS ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    code = request.json.get("code", "")
    reporte = []

    # 1️⃣ AST inicial
    try:
        ast.parse(code)
        ast_ok = True
    except SyntaxError as e:
        reporte.append(
            {"tipo": "critico", "linea": e.lineno, "mensaje": str(e)}
        )
        ast_ok = False

    # 2️⃣ Motor clásico
    fixed_code, cambios, reparado = reparar_codigo(code)

    if reparado:
        reporte.extend(analizar_flake8(fixed_code))

    # 3️⃣ IA solo si hay dudas
    ia = None
    if not reparado or not ast_ok:
        ia = analisis_semantico_ia(code)

    return jsonify(
        {
            "ok": reparado,
            "cambios": cambios,
            "report": reporte,
            "fixed_code": fixed_code,
            "ia": ia,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
