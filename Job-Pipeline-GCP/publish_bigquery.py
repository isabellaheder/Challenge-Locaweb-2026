import pandas as pd
from google.cloud import bigquery

PROJECT_ID = "predictops-challenge-2026"
DATASET = "predictops_gold"

client = bigquery.Client(project=PROJECT_ID)

arquivos = {
    "previsao_d1": "outputs/previsao_incidentes_d1.csv",
    "previsao_d7": "outputs/previsao_incidentes_d7.csv",
    "previsao_sla": "outputs/previsao_sla.csv",
    "previsao_turno": "outputs/previsao_incidentes_turno.csv",
    "previsao_duracao": "outputs/export_previsao_duracao.csv",
    "clusters_incidentes": "outputs/clusters_incidentes.csv",
    "cluster_nlp": "outputs/incident_clusters.csv",
    "previsao_d1_por_cluster": "outputs/previsao_d1_por_cluster.csv",
    "previsao_d7_por_cluster": "outputs/previsao_d7_por_cluster.csv",
    "metricas_previsao_por_cluster": "outputs/metricas_previsao_por_cluster.csv",}

for tabela, arquivo in arquivos.items():
    print(f"Publicando {tabela}")
    df = pd.read_csv(arquivo)

    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    job = client.load_table_from_dataframe(df, f"{PROJECT_ID}.{DATASET}.{tabela}", job_config=job_config)

    job.result()
    print(f"OK -> {tabela}")
