import ast
import json
import os
import requests

import astor
import autopep8
import black
import isort
from flask import Flask, jsonify, request, render_template
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-4.1-mini"

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# ---------------- MOTOR DETERMINÍSTICO ----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(ast.Constant("Docstring generado automáticamente"))
            )
            self.cambios += 1
        return self.generic_visit(node)


def pre_reparar(code: str):
    cambios = 0
    lines = code.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(("def ", "if ", "for ", "while ", "class ")) and not s.endswith(":"):
            lines[i] += ":"
            cambios += 1
    return "\n".join(lines), cambios


def reparar_codigo(code: str):
    total = 0
    code, c = pre_reparar(code)
    total += c

    try:
        tree = ast.parse(code)
        r = AutoRepair()
        tree = r.visit(tree)
        ast.fix_missing_locations(tree)
        code = astor.to_source(tree)
        total += r.cambios
    except Exception as e:
        return code, total, False, str(e)

    try:
        code = black.format_str(code, mode=black.Mode())
    except Exception:
        pass

    code = autopep8.fix_code(code)
    code = isort.code(code)

    return code, total, True, None


def analizar_flake8(code: str):
    style = flake8.get_style_guide(ignore=["E501"])
    report = style.input_file("tmp.py", lines=code.splitlines())
    return report.get_statistics("")

# ---------------- IA SEMÁNTICA (A/B) ----------------
def analisis_ia(code: str):
    if not OPENAI_API_KEY:
        return {"error": "IA no configurada"}

    prompt = f"""
Devuelve SOLO JSON válido:

{{
  "intencion": "",
  "problemas": [
    {{
      "linea": 0,
      "descripcion": "",
      "alternativas": [
        {{ "id": "A", "codigo": "" }},
        {{ "id": "B", "codigo": "" }}
      ]
    }}
  ]
}}

Código:
```python
{code}
