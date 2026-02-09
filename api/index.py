import ast, json, os, requests
from flask import Flask, jsonify, request, render_template
import astor, autopep8, black, isort
from flake8.api import legacy as flake8

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-4.1-mini"

app = Flask(__name__, template_folder="../templates")

# ---------------- MOTOR DETERMINÍSTICO ----------------
class AutoRepair(ast.NodeTransformer):
    def __init__(self): self.cambios = 0
    def visit_FunctionDef(self,node):
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(ast.Constant("Docstring auto")))
            self.cambios += 1
        return self.generic_visit(node)

def reparar_codigo(code:str):
    cambios = 0
    # ':' faltantes
    lines = code.splitlines()
    for i,l in enumerate(lines):
        s=l.strip()
        if s.startswith(("def ","if ","for ","while ","class ")) and not s.endswith(":"):
            lines[i]+=":"
            cambios +=1
    code = "\n".join(lines)
    try:
        tree = ast.parse(code)
        tree = AutoRepair().visit(tree)
        ast.fix_missing_locations(tree)
        code = astor.to_source(tree)
    except: pass
    try: code = black.format_str(code, mode=black.Mode())
    except: pass
    code = autopep8.fix_code(code)
    code = isort.code(code)
    return code, cambios

def flake_report(code:str):
    style = flake8.get_style_guide(ignore=["E501"])
    rep = style.input_file("tmp.py", lines=code.splitlines())
    return [{"tipo":"warning","mensaje":s} for s in rep.get_statistics("")]

# ---------------- IA SEMÁNTICA (A/B) ----------------
def analisis_ia(code:str):
    if not OPENAI_API_KEY: return {"error":"IA no configurada"}
    prompt = f"""
Analiza este código Python y devuelve JSON válido con alternativas A/B:

{code}

Formato JSON:
{{
  "intencion": "Qué intenta hacer el código",
  "problemas": [
    {{
      "linea": 0,
      "descripcion": "Descripción del problema",
      "alternativas": [
        {{"id":"A","codigo":""}},
        {{"id":"B","codigo":""}}
      ]
    }}
  ]
}}
"""
    try:
        r = requests.post(
            OPENAI_ENDPOINT,
            headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"},
            json={"model":OPENAI_MODEL,"input":prompt,"temperature":0.1},
            timeout=15
        )
        r.raise_for_status()
        text = r.json()["output"][0]["content"][0]["text"]
        return json.loads(text)
    except Exception as e:
        return {"error":"Error al consultar IA","detalle":str(e)}

# ---------------- RUTAS ----------------
@app.route("/")
def home(): return render_template("index.html")

@app.route("/analyze",methods=["POST"])
def analyze():
    code = request.json.get("code","")
    fixed, cambios = reparar_codigo(code)
    report = flake_report(fixed)
    ia = None
    if report or code != fixed: ia = analisis_ia(code)
    return jsonify({"fixed_code":fixed,"cambios":cambios,"report":report,"ia":ia})

# ⚠️ No app.run() para Vercel
