from flask import Flask, render_template, request, jsonify
import ast

app = Flask(__name__, template_folder='../templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analizar', methods=['POST'])
def analizar():
    data = request.json
    codigo = data.get('code', '')
    hallazgos = []

    try:
        tree = ast.parse(codigo)
        for node in ast.walk(tree):
            # Detectar eval()
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'eval':
                hallazgos.append({
                    "tipo": "peligro",
                    "titulo": "Seguridad Crítica",
                    "desc": f"Uso de 'eval()' detectado en línea {node.lineno}."
                })
            # Detectar funciones sin docstring
            if isinstance(node, ast.FunctionDef) and not ast.get_docstring(node):
                hallazgos.append({
                    "tipo": "advertencia",
                    "titulo": "Mejora de Estilo",
                    "desc": f"La función '{node.name}' no tiene documentación (docstring)."
                })
    except Exception as e:
        return jsonify([{"tipo": "error", "titulo": "Error de Sintaxis", "desc": str(e)}])

    return jsonify(hallazgos)
  
