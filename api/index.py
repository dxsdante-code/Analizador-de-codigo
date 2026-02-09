from flask import Flask, request, jsonify
import ast
import astor

app = Flask(__name__)

# -------------------------------------------------
# Refactorizador seguro
# -------------------------------------------------

class CodeRefactor(ast.NodeTransformer):
    def __init__(self):
        self.cambios = 0
        self.hallazgos = []

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            self.hallazgos.append({
                "tipo": "info",
                "codigo": "STL001",
                "linea": node.lineno,
                "mensaje": f"Docstring agregado automáticamente a '{node.name}'"
            })
            docstring = ast.Expr(
                value=ast.Constant(
                    value=f"Documentación automática para {node.name}."
                )
            )
            node.body.insert(0, docstring)
            self.cambios += 1

        return self.generic_visit(node)

    def visit_If(self, node):
        if isinstance(node.test, ast.Constant) and node.test.value is False:
            self.hallazgos.append({
                "tipo": "advertencia",
                "codigo": "QLT001",
                "linea": node.lineno,
                "mensaje": "Bloque 'if False' eliminado automáticamente"
            })
            self.cambios += 1
            return None

        return self.generic_visit(node)

# -------------------------------------------------
# Endpoint
# -------------------------------------------------

@app.route('/analizar', methods=['POST'])
def analizar():
    data = request.json
    codigo_original = data.get('code', '')

    try:
        tree = ast.parse(codigo_original)

        refactor = CodeRefactor()
        nuevo_tree = refactor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)

        if refactor.cambios > 0:
            codigo_corregido = astor.to_source(nuevo_tree)
        else:
            codigo_corregido = codigo_original

        return jsonify({
            "cambios_realizados": refactor.cambios,
            "hallazgos": refactor.hallazgos,
            "codigo_corregido": codigo_corregido
        })

    except SyntaxError as e:
        return jsonify({
            "error": {
                "tipo": "error",
                "codigo": "SYN001",
                "linea": e.lineno,
                "mensaje": e.msg
            }
        }), 400

# -------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
