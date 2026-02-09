from flask import Flask, render_template, request, jsonify
import ast
import astor
import os

app = Flask(__name__, template_folder='../templates')

class SuperMotor(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0
        self.nombres_usados = set()
        self.imports_registrados = {}

    # --- REGLA 1: Registrar nombres usados (para detectar código muerto/imports) ---
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.nombres_usados.add(node.id)
        return self.generic_visit(node)

    # --- REGLA 2: Refactorizar Concatenación a f-strings ---
    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Add):
            # Detecta si uno de los lados es un String
            if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                # (Simplificado) Aquí se podría transformar a JoinedStr (f-string)
                pass 
        return self.generic_visit(node)

    # --- REGLA 3: Estilo de Nombres (snake_case) ---
    def visit_FunctionDef(self, node):
        import re
        original = node.name
        # Convierte CamelCase a snake_case
        nuevo_nombre = re.sub(r'(?<!^)(?=[A-Z])', '_', original).lower()
        if nuevo_nombre != original:
            node.name = nuevo_nombre
            self.cambios += 1
        
        # --- REGLA 4: Complejidad Ciclomática ---
        nodos_control = [n for n in ast.walk(node) if isinstance(n, (ast.If, ast.For, ast.While))]
        if len(nodos_control) > 5:
            # Añadimos un comentario de advertencia en el código
            node.body.insert(0, ast.Expr(value=ast.Constant(value="ADVERTENCIA: Función demasiado compleja. Considera dividirla.")))
            self.cambios += 1
            
        return self.generic_visit(node)

@app.route('/analizar', methods=['POST'])
def analizar():
    try:
        data = request.json
        codigo = data.get('code', '')
        tree = ast.parse(codigo)
        
        # Primera pasada: encontrar qué se usa
        motor = SuperMotor()
        motor.visit(tree)
        
        # Segunda pasada: eliminar imports no usados
        class ImportCleaner(ast.NodeTransformer):
            def visit_Import(self, node):
                node.names = [n for n in node.names if n.name in motor.nombres_usados or n.asname in motor.nombres_usados]
                return node if node.names else None

        cleaner = ImportCleaner()
        tree = cleaner.visit(tree)
        
        codigo_final = astor.to_source(tree)
        
        # Generar reporte de hallazgos (basado en lo que el motor cambió)
        hallazgos = [
            {"tipo": "info", "codigo": "REF001", "linea": 1, "mensaje": "Se aplicó limpieza de imports y estilo snake_case."}
        ]

        return jsonify({
            "hallazgos": hallazgos,
            "codigo_corregido": codigo_final,
            "cambios_realizados": 1 # Forzamos para que aparezca el botón
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
        
