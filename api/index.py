import ast, json, os, re, requests
import astor, autopep8, black, isort
from flask import Flask, request, jsonify
from flake8.api import legacy as flake8

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-4.1-mini"

app = Flask(__name__)


class Repair(ast.NodeTransformer):
    def __init__(self): self.c = 0
    def visit_FunctionDef(self, n):
        if not ast.get_docstring(n):
            n.body.insert(0, ast.Expr(ast.Constant("Auto doc")))
            self.c += 1
        return self.generic_visit(n)


def pre(code):
    c = 0
    l = code.splitlines()
    for i, x in enumerate(l):
        s = x.strip()
        if s.startswith(("def ", "if ", "for ", "while ", "class ")) and not s.endswith(":"):
            l[i] += ":"; c += 1
    return "\n".join(l), c


def fix(code):
    t = 0
    code, c = pre(code); t += c
    try:
        tree = ast.parse(code)
        r = Repair()
        tree = r.visit(tree)
        code = astor.to_source(tree)
        t += r.c
    except Exception as e:
        return code, t, False, str(e)
    try: code = black.format_str(code, mode=black.Mode())
    except: pass
    return isort.code(autopep8.fix_code(code)), t, True, None


def lint(code):
    s = flake8.get_style_guide(ignore=["E501"])
    r = s.input_file("x.py", lines=code.splitlines())
    return r.get_statistics("")


def ia(code):
    if not OPENAI_API_KEY:
        return {"error": "API KEY no configurada"}
    p = f"""
Devuelve SOLO JSON:
{{"intencion":"","problemas":[{{"linea":0,"descripcion":"","opciones":{{"A":"","B":""}}}}]}}
Código:
```python
{code}
```"""
    r = requests.post(
        OPENAI_ENDPOINT,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": OPENAI_MODEL, "input": p, "temperature": 0.1},
        timeout=20,
    )
    return json.loads(r.json()["output"][0]["content"][0]["text"])


@app.route("/analyze", methods=["POST"])
def analyze():
    code = request.json.get("code", "")
    out = {"ok": True, "cambios": 0, "code": "", "lint": [], "ia": None}
    try: ast.parse(code)
    except Exception: out["ok"] = False
    fixed, c, ok, err = fix(code)
    out["cambios"] = c
    out["code"] = fixed
    if ok: out["lint"] = lint(fixed)
    else: out.update({"ok": False, "error": err})
    if not ok or out["lint"]:
        out["ia"] = ia(code)
    return jsonify(out)


if __name__ == "__main__":
    app.run(debug=True)
