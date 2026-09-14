import os
import mysql.connector
from flask import Flask, request, jsonify
from treino import treinar_modelo

# ===== MONITORAMENTO (Application Insights) - Atividade 6 =====
from opencensus.ext.azure.log_exporter import AzureLogHandler
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
conn_str = os.environ.get("APPINSIGHTS_CONNECTION_STRING")
if conn_str:
    logger.addHandler(AzureLogHandler(connection_string=conn_str))
# ==============================================================

app = Flask(__name__)

# ===== TREINA O MODELO ANTES DE QUALQUER PREVISÃO =====
logger.info("Iniciando treino do modelo de previsao de incidentes...")
modelo, features, metricas = treinar_modelo()
logger.info(f"Modelo treinado. Metricas: {metricas}")
# ======================================================

# ===== CONEXÃO COM AZURE DATABASE FOR MYSQL - Atividade 5 =====
def get_conexao():
    return mysql.connector.connect(
        host=os.environ["MYSQL_HOST"],
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DB"],
        ssl_disabled=False
    )

def criar_tabela():
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS previsoes_incidentes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lag_1 FLOAT, lag_7 FLOAT, media_7d FLOAT,
            tem_AM INT, mes INT,
            previsao FLOAT,
            data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

criar_tabela()
# =============================================================

@app.route("/")
def home():
    return jsonify({"status": "API de previsao de incidentes rodando!", "metricas_modelo": metricas})

@app.route("/prever", methods=["POST"])
def prever():
    dados = request.get_json()
    entrada = [[
        dados["lag_1"],
        dados["lag_7"],
        dados["media_7d"],
        dados["tem_AM"],
        dados["mes"]
    ]]

    # Gera o resultado usando o modelo treinado (Atividade 4)
    previsao = float(modelo.predict(entrada)[0])
    logger.info(f"Previsao gerada: {previsao} para entrada {dados}")

    # INSERÇÃO no MySQL (Atividade 5)
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO previsoes_incidentes
        (lag_1, lag_7, media_7d, tem_AM, mes, previsao)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (dados["lag_1"], dados["lag_7"], dados["media_7d"],
          dados["tem_AM"], dados["mes"], previsao))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"previsao_incidentes_dia_seguinte": previsao})

@app.route("/historico", methods=["GET"])
def historico():
    # CONSULTA no MySQL (Atividade 5)
    conn = get_conexao()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM previsoes_incidentes ORDER BY id DESC LIMIT 20")
    registros = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(registros)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)