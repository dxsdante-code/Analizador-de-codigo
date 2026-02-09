from flask import Flask, render_template, request, jsonify
import ast

app = Flask(__name__, template_folder='../templates')

# -----------------------------
# Configuración de reglas
# -----------------------------

FUNCIONES_CRITICAS = ['eval', 'exec']
IMPORTS_PELIGROSOS = ['os', 'subprocess']
SEVERIDAD = {
    "info": 1,
    "advertencia": 2,
    "peligro": 3,
    "critico": 4
}

# -----------------------------
# Utilidades AST
# -----------------------------

def es_llamada_peligrosa(node, nombres):
    if isinstance(node.func, ast.Name):
        return node.func.id in nombres
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in nombres
    return False


def recolectar_imports(tree):
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    imports[alias.asname or alias.name] = node.module
    return imports


# -----------------------------
# Rutas Flask
# -----------------------------

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
        imports = recolectar_imports(tree)

        for node in ast.walk(tree):

            # -----------------------------
            # Detectar eval / exec
            # -----------------------------
            if isinstance(node, ast.Call) and es_llamada_peligrosa(node, FUNCIONES_CRITICAS):
                nivel = "advertencia"
                if node.args and not isinstance(node.args[0], ast.Constant):
                    nivel = "critico"

                hallazgos.append({
                    "tipo": nivel,
                    "codigo": "SEC001",
                    "linea": node.lineno,
                    "mensaje": f"Uso de '{node.func.id}' con entrada {'dinámica' if nivel == 'critico' else 'literal'}"
                })

            # -----------------------------
            # Detectar imports peligrosos
            # -----------------------------
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    base = node.value.id
                    if imports.get(base) in IMPORTS_PELIGROSOS:
                        hallazgos.append({
                            "tipo": "peligro",
                            "codigo": "SEC002",
                            "linea": node.lineno,
                            "mensaje": f"Uso del módulo peligroso '{imports.get(base)}'"
                        })

            # -----------------------------
            # Código muerto
            # -----------------------------
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Constant) and node.test.value is False:
                    hallazgos.append({
                        "tipo": "advertencia",
                        "codigo": "QLT001",
                        "linea": node.lineno,
                        "mensaje": "Bloque de código inalcanzable (if False)"
                    })

            # -----------------------------
            # Funciones sin docstring
            # -----------------------------
            if isinstance(node, ast.FunctionDef):
                if not ast.get_docstring(node):
                    hallazgos.append({
                        "tipo": "info",
                        "codigo": "STL001",
                        "linea": node.lineno,
                        "mensaje": f"La función '{node.name}' no tiene docstring"
                    })

                if len(node.args.args) > 5:
                    hallazgos.append({
                        "tipo": "advertencia",
                        "codigo": "STL002",
                        "linea": node.lineno,
                        "mensaje": f"La función '{node.name}' tiene demasiados parámetros"
                    })

    except SyntaxError as e:
        return jsonify([{
            "tipo": "error",
            "codigo": "SYN001",
            "linea": e.lineno,
            "mensaje": f"Error de sintaxis: {e.msg}"
        }])

    return jsonify(hallazgos)


# -----------------------------
# Arranque
# -----------------------------

if __name__ == '__main__':
    app.run(debug=True)  
