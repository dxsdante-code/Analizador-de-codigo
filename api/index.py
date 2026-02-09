import os
import ast
import astor
import json
import requests

import black
import autopep8
import isort
from flask import Flask, request, jsonify, render_template, Response

# ---------------- CONFIG ----------------
HF_MODEL = "bigcode/starcoder"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HF_TOKEN = os.environ.get("HF_API_TOKEN")  # ← VARIABLE DE ENTORNO

template_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "templates")
)
app = Flask(__name__, template_folder=template_dir)

# ---------------- AST MOTOR ----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(
                    value=ast.Constant(
                        value="Documentación automática añadida."
                    )
                ),
            )
            self.cambios += 1
        return self.generic_visit(node)


def reparar_codigo_local(code):
    """Corrección sintáctica básica + formato"""
    lines = code.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(
            ("def ", "if ", "for ", "while ", "class ")
        ) and not stripped.endswith(":"):
            lines[i] += ":"

    repaired = "\n".join(lines)

    try:
        tree = ast.parse(repaired)
        motor = AutoRepair()
        new_tree = motor.visit(tree)
        ast.fix_missing_locations(new_tree)
        repaired = astor.to_source(new_tree)
    except Exception:
        motor = AutoRepair()

    try:
        repaired = black.format_str(repaired, mode=black.Mode())
    except Exception:
        pass

    repaired = autopep8.fix_code(repaired)
    repaired = isort.code(repaired)

    return repaired, motor.cambios


# ---------------- IA SEMÁNTICA ----------------
def analizar_semantica_ia(code):
    """Llamada a StarCoder para corrección semántica"""
    if not HF_TOKEN:
        return None, "Token de IA no configurado"

    prompt = f"""
Eres un experto en Python.
Corrige el siguiente código respetando su intención original.
No inventes nuevas funcionalidades.
Devuelve SOLO el código Python corregido y ejecutable.

Código:
{code}
"""

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 900,
            "temperature": 0.2,
            "return_full_text": False,
        },
    }

    try:
        resp = requests.post(
            HF_API_URL,
            headers=headers,
            json=payload,
            timeout=25,
        )

        if resp.status_code != 200:
            return None, f"Error IA {resp.status_code}"

        data = resp.json()

        if isinstance(data, list) and "generated_text" in data[0]:
            return data[0]["generated_text"], None

        return None, "Respuesta IA no válida"

    except Exception as e:
        return None, str(e)


# ---------------- RUTAS ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get("code", "")

    report = []

    # 1️⃣ Sintaxis básica
    try:
        ast.parse(code)
        report.append(
            {"tipo": "ok", "mensaje": "Sintaxis válida"}
        )
    except SyntaxError as e:
        report.append(
            {
                "tipo": "critico",
                "linea": e.lineno,
                "mensaje": str(e),
            }
        )

    # 2️⃣ Corrección LOCAL
    fixed_local, cambios = reparar_codigo_local(code)

    # 3️⃣ IA SEMÁNTICA
    fixed_ai, ia_error = analizar_semantica_ia(code)

    if fixed_ai:
        codigo_final = fixed_ai
        report.append(
            {"tipo": "ia", "mensaje": "Corrección semántica aplicada"}
        )
    else:
        codigo_final = fixed_local
        report.append(
            {
                "tipo": "warning",
                "mensaje": f"IA no disponible: {ia_error}",
            }
        )

    return jsonify(
        report=report,
        fixed_code=codigo_final,
        cambios=cambios,
    )


@app.route("/download", methods=["POST"])
def download():
    code = request.json.get("code", "")
    return Response(
        code,
        mimetype="text/x-python",
        headers={
            "Content-Disposition": "attachment; filename=codigo_corregido.py"
        },
    )


if __name__ == "__main__":
    app.run()
