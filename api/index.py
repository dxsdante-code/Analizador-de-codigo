import ast
import json
import os
import tempfile
import autopep8
import black
import isort
import requests
from flask import Flask, jsonify, render_template, request
from flake8.api import legacy as flake8

app = Flask(__name__)

# Configuración de OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

class AutoRepair(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0
    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant(value="Docstring automático.")))
            self.cambios += 1
        return self.generic_visit(node)

def reparar_codigo(code):
    try:
        # Pre-reparación básica (añadir colons)
        lines = code.splitlines()
        for i, l in enumerate(lines):
            if l.strip().startswith(("def ", "if ", "for ")) and not l.strip().endswith(":"):
                lines[i] += ":"
        code = "\n".join(lines)
        
        # AST y Formateo
        tree = ast.parse(code)
        motor = AutoRepair()
        tree = motor.visit(tree)
        code = ast.unparse(tree)
        code = black.format_str(code, mode=black.Mode())
        return code, motor.cambios, True
    except Exception as e:
        return code, 0, False

@app.route("/")
def home():
    try:
        return render_template("index.html")
    except Exception as e:
        return f"Error: No se encuentra index.html en /templates. Detalle: {str(e)}", 500

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    code = data.get("code", "")
    fixed_code, cambios, ok = reparar_codigo(code)
    
    return jsonify({
        "codigo_limpio": fixed_code,
        "cambios": cambios,
        "status": "ok" if ok else "error"
    })

# Requisito para Vercel
app.debug = False
    
