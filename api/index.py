from flask import Flask, render_template, request, jsonify
import ast
import astor
import os

# Ajuste de ruta para que Vercel no se pierda
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)

class CodeRefactor(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0
    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            docstring = ast.Expr(value=ast.Constant(value="Corrección: Se añadió descripción a la función."))
            node.body.insert(0, docstring)
            self.cambios += 1
        return self.generic_visit(node)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analizar', methods=['POST'])
def analizar():
    try:
        data = request.json
        codigo = data.get('code', '')
        tree = ast.parse(codigo)
        
        # Recolectar hallazgos
        hallazgos = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not ast.get_docstring(node):
                hallazgos.append({
                    "tipo": "info",
                    "codigo": "STL001",
                    "linea": node.lineno,
                    "mensaje": f"La función '{node.name}' no tiene docstring."
                })

        # Aplicar corrección
        refactor = CodeRefactor()
        nuevo_tree = refactor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        
        codigo_listo = astor.to_source(nuevo_tree) if refactor.cambios > 0 else codigo

        return jsonify({
            "hallazgos": hallazgos,
            "codigo_corregido": codigo_listo,
            "cambios_realizados": refactor.cambios
        })
    except Exception as e:
        return jsonify({"hallazgos": [{"tipo": "error", "codigo": "ERR", "linea": 0, "mensaje": str(e)}], "cambios_realizados": 0})
        
