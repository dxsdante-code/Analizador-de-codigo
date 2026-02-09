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

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

# Configuración de carpetas para Flask
app = Flask(__name__, template_folder="templates")

# ---------------- [AUTO REPAIR & IA LOGIC] ----------------
# (Mantén aquí las clases AutoRepair y las funciones de análisis del código anterior)
# ... [Código omitido para brevedad, mantener igual que el anterior] ...

# ---------------- RUTAS CORREGIDAS ----------------

@app.route("/")
def home():
    # Esta línea es la que hace que veas el HTML y no solo texto
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    code = data.get("code", "")
    # ... (Resto de la lógica de análisis que ya teníamos)
    return jsonify({"status": "ok", "codigo_limpio": code}) # Simplificado para el ejemplo

if __name__ == "__main__":
    app.run(debug=True)
    
