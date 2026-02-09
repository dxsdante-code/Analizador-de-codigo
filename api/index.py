from flask import Flask, render_template, request, jsonify, Response
import ast
import astor
import os

# Configuración de rutas para evitar el "Not Found"
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)

class SuperMotor(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0
    
    def visit_FunctionDef(self, node):
        # Regla: Añadir docstrings automáticos
        if not ast.get_docstring(node):
            node.body.insert(0, ast.Expr(value=ast.Constant(value="Refactored: Added missing docstring.")))
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
        
        # Aplicar Refactorización
        motor = SuperMotor()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)
        
        codigo_corregido = astor.to_source(nuevo_tree) if motor.cambios > 0 else codigo
        
        # Generar reporte basado en cambios
        hallazgos = []
        if motor.cambios > 0:
            hallazgos.append({
                "tipo": "info",
                "codigo": "REF001",
                "linea": 1,
                "mensaje": f"Se aplicaron {motor.cambios} mejoras de documentación."
            })

        return jsonify({
            "hallazgos": hallazgos,
            "codigo_corregido": codigo_corregido,
            "cambios_realizados": motor.cambios
        })
    except Exception as e:
        return jsonify({"hallazgos": [{"tipo": "critico", "codigo": "ERR", "linea": 0, "mensaje": str(e)}], "cambios_realizados": 0})

@app.route('/descargar', methods=['POST'])
def descargar():
    codigo = request.form.get('code', '')
    return Response(
        codigo,
        mimetype="text/x-python",
        headers={"Content-disposition": "attachment; filename=codigo_refactorizado.py"}
    )
    
