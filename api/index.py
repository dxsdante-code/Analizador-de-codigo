import ast
import os
import json
import astor
import autopep8
import black
import isort
import requests
from flask import Flask, jsonify, render_template, request, Response
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

BASE_DIR = os.path.dirname(__file__)
TEMPLATES = os.path.abspath(os.path.join(BASE_DIR, "..", "templates"))

app = Flask(__name__, template_folder=TEMPLATES)

# ---------------- AUTO REPAIR ----------------
class SafeRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(value=ast.Constant("Auto docstring generado"))
            )
            self.cambios += 1
        return self.generic_visit(node)


def motor_reparacion(code: str):
    cambios = 0
    lines = code.splitlines()

    # Reparaciones seguras
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith(("def ", "if ", "for ", "while ", "class ")) and not s.endswith(":"):
            lines[i] += ":"
            cambios += 1

    code = "\n".join(lines)

    try:
        tree = ast.parse(code)
        repair = SafeRepair()
        tree = repair.visit(tree)
        ast.fix_missing_locations(tree)
        code = astor.to_source(tree)
        cambios += repair.cambios
    except SyntaxError as e:
        return None, cambios, str(e)

    try:
        code = black.format_str(code, mode=black.Mode())
    except Exception:
        pass

    code = autopep8.fix_code(code)
    code = isort.code(code)

    return code, cambios, None


def flake_report(code):
    style = flake8.get_style_guide(ignore=["E501"])
    report = style.input_file("tmp.py", lines=code.splitlines())
    return [{"tipo": "warning", "mensaje": x} for x in report.get_statistics("")]


# ---------------- IA SEMÁNTICA ----------------
def analisis_ia(code):
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY no configurada"}

    prompt = f"""
Analiza este código Python.

Devuelve EXCLUSIVAMENTE JSON con este formato:

{{
  "intencion": "...",
  "errores": [
    {{
      "linea": 0,
      "descripcion": "...",
      "clasificacion": "logico | estructura | riesgo",
      "alternativas": [
        {{
          "id": "A",
          "descripcion": "...",
          "codigo": "..."
        }},
        {{
          "id": "B",
          "descripcion": "...",
          "codigo": "..."
        }}
      ]
    }}
  ]
}}

Código:
```python
{code}
