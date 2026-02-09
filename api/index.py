from flask import Flask, render_template, request, jsonify, Response
import ast
import astor
import os

# Templates
template_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'templates')
)
app = Flask(__name__, template_folder=template_dir)


class SuperMotor(ast.NodeTransformer):
    """
    Motor de refactorización basado en AST.
    Reglas actuales:
    - Agregar docstrings faltantes
    """

    def __init__(self):
        self.cambios = 0

    def visit_FunctionDef(self, node):
        if not ast.get_docstring(node):
            node.body.insert(
                0,
                ast.Expr(
                    value=ast.Constant(
                        value="Documentación generada automáticamente."
                    )
                )
            )
            self.cambios += 1
        return self.generic_visit(node)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analizar', methods=['POST'])
def analizar():
    try:
        data = request.get_json(silent=True) or {}
        codigo = data.get('code', '')

        if not codigo.strip():
            return jsonify({
                "hallazgos": [],
                "codigo_corregido": codigo,
                "cambios_realizados": 0
            })

        tree = ast.parse(codigo)
        motor = SuperMotor()
        nuevo_tree = motor.visit(tree)
        ast.fix_missing_locations(nuevo_tree)

        codigo_corregido = (
            astor.to_source(nuevo_tree)
            if motor.cambios > 0 else codigo
        )

        hallazgos = []
        if motor.cambios > 0:
            hallazgos.append({
                "tipo": "info",
                "codigo": "REF001",
                "linea": 1,
                "mensaje": f"Se agregaron {motor.cambios} docstrings faltantes."
            })

        return jsonify({
            "hallazgos": hallazgos,
            "codigo_corregido": codigo_corregido,
            "cambios_realizados": motor.cambios
        })

    except SyntaxError as e:
        return jsonify({
            "hallazgos": [{
                "tipo": "critico",
                "codigo": "SYNTAX",
                "linea": e.lineno or 0,
                "mensaje": e.msg
            }],
            "cambios_realizados": 0
        }), 400

    except Exception as e:
        return jsonify({
            "hallazgos": [{
                "tipo": "critico",
                "codigo": "ERR",
                "linea": 0,
                "mensaje": str(e)
            }],
            "cambios_realizados": 0
        }), 500


@app.route('/descargar', methods=['POST'])
def descargar():
    codigo = request.form.get('code', '')
    return Response(
        codigo,
        mimetype='text/x-python',
        headers={
            'Content-Disposition': 'attachment; filename=codigo_corregido.py'
        }
        )
