import ast
import os
import re
import requests

import astor
import autopep8
import black
import isort
from flake8.api import legacy as flake8
from flask import Flask, Response, jsonify, render_template, request

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

template_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "templates")
)
app = Flask(__name__, template_folder=template_dir)

# ---------------- PRE SANITIZE ----------------
def pre_sanitize(code: str):
    stripped = code.strip().lower()

    if stripped.startswith("<!doctype") or stripped.startswith("<html"):
        return False, "El contenido parece HTML, no Python"

    if stripped.startswith("{") and stripped.endswith("}"):
        return False, "El contenido parece JSON, no Python"

    if len(stripped) < 5:
        return False, "Código demasiado corto o incompleto"

    return True, None


# ---------------- SYNTAX FIXER ----------------
def fix_common_syntax(code: str):
    lines = code.splitlines()
    fixed = []
    changes = 0

    for line in lines:
        stripped = line.strip()

        if re.match(r".*\b(def|if|for|while|class|elif|else|except|finally)\b$", stripped):
            fixed.append(line + ":")
            changes += 1
            continue

        if stripped.count("(") > stripped.count(")"):
            fixed.append(line + ")")
            changes += 1
            continue

        if stripped.count('"') % 2 != 0:
            fixed.append(line + '"')
            changes += 1
            continue

        fixed.append(line)

    return "\n".join(fixed), changes


# ---------------- AST AUTO REPAIR ----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.changes = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(value=ast.Constant(
                    value="Documentación automática añadida."))
            )
            self.changes += 1
        return self.generic_visit(node)


def ast_repair(code: str):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return code, 0, str(e)

    repairer = AutoRepair()
    tree = repairer.visit(tree)
    ast.fix_missing_locations(tree)

    return astor.to_source(tree), repairer.changes, None


# ---------------- FORMAT ----------------
def format_code(code: str):
    try:
        code = black.format_str(code, mode=black.Mode())
    except Exception:
        pass

    code = autopep8.fix_code(code)
    code = isort.code(code)

    return code


# ---------------- LINT ----------------
def lint(code: str):
    style = flake8.get_style_guide(ignore=["E501"])
    report = style.input_file(filename="temp.py", lines=code.splitlines())

    warnings = []
    for stat in report.get_statistics(""):
        warnings.append(stat)

    return warnings


# ---------------- SEMANTIC IA ----------------
def semantic_ai(code: str):
    if not OPENAI_API_KEY:
        return "IA no configurada (OPENAI_API_KEY no definida)"

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
                    "Analiza el siguiente código Python.\n"
                    "1. ¿Qué intenta hacer?\n"
                    "2. ¿Qué partes están incompletas?\n"
                    "3. ¿Qué errores lógicos existen?\n"
                    "No reescribas el código."
                ),
            },
            {"role": "user", "content": code},
        ],
        "temperature": 0.2,
    }

    try:
        r = requests.post(
            OPENAI_ENDPOINT, headers=headers, json=payload, timeout=15
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error IA: {e}"


# ---------------- SCORE ----------------
def score(code_ok, lint_warnings, semantic_text):
    score = {
        "sintaxis": 100 if code_ok else 40,
        "estilo": max(100 - len(lint_warnings) * 5, 50),
        "semantica": 70 if "incompleta" not in semantic_text.lower() else 50,
        "completitud": 60,
    }
    return score


# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    code = data.get("code", "")

    ok, error = pre_sanitize(code)
    if not ok:
        return jsonify({"ok": False, "error": error}), 400

    code, fix_changes = fix_common_syntax(code)

    code, ast_changes, ast_error = ast_repair(code)
    if ast_error:
        return jsonify({"ok": False, "error": ast_error}), 400

    code = format_code(code)
    lint_warnings = lint(code)

    semantic = semantic_ai(code)
    scores = score(True, lint_warnings, semantic)

    return jsonify(
        {
            "ok": True,
            "codigo_corregido": code,
            "lint": lint_warnings,
            "analisis_semantico": semantic,
            "cambios": fix_changes + ast_changes,
            "score": scores,
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
