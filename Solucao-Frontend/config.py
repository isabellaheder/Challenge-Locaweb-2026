import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================================================
# Google Cloud / Gemini (Vertex AI)
# ==============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "predictops-challenge-2026")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# Credenciais do Vertex AI (Gemini). Mantém a chave já usada pelo projeto.
VERTEX_CREDENTIALS_PATH = os.getenv(
    "VERTEX_CREDENTIALS_PATH",
    os.path.join(BASE_DIR, "gcp-credentials.json"),
)

# ==============================================================================
# BigQuery (fonte de dados principal — substitui o bucket GCS)
# ==============================================================================
# Chave de serviço com acesso ao BigQuery (predictops-plataforma@...).
BQ_CREDENTIALS_PATH = os.getenv(
    "BQ_CREDENTIALS_PATH",
    os.path.join(BASE_DIR, "bigquery-credentials.json"),
)
# Projeto onde vive o dataset e que fatura as consultas.
BQ_PROJECT = os.getenv("BQ_PROJECT", "predictops-challenge-2026")
BQ_DATASET = os.getenv("BQ_DATASET", "predictops_gold")
# Localização do dataset (deixe vazio para resolução automática).
BQ_LOCATION = os.getenv("BQ_LOCATION", "") or None

# Tabelas do dataset predictops_gold
BQ_TABLES = {
    "incidentes":            os.getenv("BQ_TABLE_INCIDENTES", "incidentes"),
    "cluster_nlp":           os.getenv("BQ_TABLE_CLUSTER_NLP", "cluster_nlp"),
    "clusters_incidentes":   os.getenv("BQ_TABLE_CLUSTERS_INCIDENTES", "clusters_incidentes"),
    "previsao_d1":           os.getenv("BQ_TABLE_PREVISAO_D1", "previsao_d1"),
    "previsao_d7":           os.getenv("BQ_TABLE_PREVISAO_D7", "previsao_d7"),
    "previsao_duracao":      os.getenv("BQ_TABLE_PREVISAO_DURACAO", "previsao_duracao"),
    "previsao_sla":          os.getenv("BQ_TABLE_PREVISAO_SLA", "previsao_sla"),
    "previsao_turno":        os.getenv("BQ_TABLE_PREVISAO_TURNO", "previsao_turno"),
    # Previsão decomposta por regime operacional (cluster) — D+1 e D+7
    "previsao_d1_por_cluster": os.getenv("BQ_TABLE_PREVISAO_D1_CLUSTER",
                                         "previsao_d1_por_cluster"),
    "previsao_d7_por_cluster": os.getenv("BQ_TABLE_PREVISAO_D7_CLUSTER",
                                         "previsao_d7_por_cluster"),
    "metricas_previsao_por_cluster": os.getenv("BQ_TABLE_METRICAS_CLUSTER",
                                               "metricas_previsao_por_cluster"),
}

# Override manual do mapeamento de colunas da tabela 'incidentes'
# (coluna_no_bigquery -> nome amigável esperado pelas telas). Só preencha se o
# mapeamento automático não acertar alguma coluna. Ex.:
# BQ_INCIDENTES_COLUMN_MAP = {"grupo_designado": "Grupo designado"}
BQ_INCIDENTES_COLUMN_MAP = {}

# Fallback local (usado só se o BigQuery estiver indisponível)
LOCAL_DATASET_PATH = os.getenv("LOCAL_DATASET_PATH", os.path.join(BASE_DIR, "LW-DATASET-TRATADO.xlsx"))

# ==============================================================================
# Métricas operacionais (MTTR e duração)
# ==============================================================================
# Unidade da coluna 'Duração' da tabela `incidentes` e das colunas de
# `previsao_duracao`. Na base LW o valor é o delta Resolvido-Aberto em SEGUNDOS.
# Aceita "s", "min" ou "h". Para a base de incidentes a unidade ainda é
# reconferida em tempo de execução contra o próprio delta das datas.
DURACAO_UNIT = os.getenv("DURACAO_UNIT", "s")
PREV_DURACAO_UNIT = os.getenv("PREV_DURACAO_UNIT", DURACAO_UNIT)

# Limite de SLA por prioridade, em horas. Usado para posicionar as linhas de
# referência nos gráficos de tempo de resolução do Painel NOC. Ajuste conforme
# o contrato — não é derivado dos dados.
SLA_HORAS_POR_PRIORIDADE = {"P1": 4.0, "P2": 4.0, "P3": 12.0, "P4": 24.0, "P5": 96.0}

# Meta operacional de MTTR (horas) e teto de sanidade: resoluções acima disso
# são registros parados/reabertos e ficam fora da média (default 30 dias).
META_MTTR_H = float(os.getenv("META_MTTR_H", "48"))
MTTR_MAX_H = float(os.getenv("MTTR_MAX_H", "720"))

# ==============================================================================
# Power BI (embed opcional)
# ==============================================================================
POWERBI_NOC_URL = os.getenv(
    "POWERBI_NOC_URL",
    "https://app.powerbi.com/view?r=eyJrIjoiZXhhbXBsZS1ub2MtdXJsLTIwMjYtZmlhcCIsImMiOjF9"
)
POWERBI_GESTOR_URL = os.getenv(
    "POWERBI_GESTOR_URL",
    "https://app.powerbi.com/view?r=eyJrIjoiZXhhbXBsZS1nZXN0b3ItdXJsLTIwMjYtZmlhcCIsImMiOjF9"
)

# ==============================================================================
# App
# ==============================================================================
APP_TITLE = "Predict Ops - Locaweb AIOps"
APP_ICON = "P"
