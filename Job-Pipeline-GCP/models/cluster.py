from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from google.cloud import storage
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet")

BUCKET_GOLD = "predictops-gold"

K_FINAL = 3

Path("artifacts").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

print("Lendo Silver...")
df = pd.read_parquet(ARQUIVO_SILVER)

df["Aberto"] = pd.to_datetime(df["Aberto"])
print(df.shape)

df["mes"] = df["Aberto"].dt.month

df["tem_AM"] = (df["Descrição resumida"].str.contains("Application Monitoring", case=False, na=False).astype(int))

df_cluster = df.copy()

df_cluster["hora_abertura"] = (df_cluster["Aberto"].dt.hour)
df_cluster["dia_semana"] = (df_cluster["Aberto"].dt.dayofweek)
df_cluster["fim_de_semana"] = (df_cluster["dia_semana"] >= 5).astype(int)

top_ic = (df_cluster["Item de configuração"].value_counts().head(100).index)
df_cluster["Item_config_cluster"] = (df_cluster["Item de configuração"].where(df_cluster["Item de configuração"].isin(top_ic), "OUTROS"))

top_categoria = (df_cluster["Categoria"].value_counts().head(30).index)
df_cluster["Categoria_cluster"] = (df_cluster["Categoria"].where(df_cluster["Categoria"].isin(top_categoria), "OUTROS"))

top_subcategoria = (df_cluster["Subcategoria"].value_counts().head(30).index)
df_cluster["Subcategoria_cluster"] = (df_cluster["Subcategoria"].where(df_cluster["Subcategoria"].isin(top_subcategoria), "OUTROS"))

df_cluster["Prioridade_cluster"] = (df_cluster["Prioridade"].replace({"1 - Crítica": "2 - Alta"}))

features_cluster = ["Prioridade_cluster", "Produto", "Categoria_cluster", "Subcategoria_cluster", 
                    "Grupo designado", "Item_config_cluster", "Aberto por", "hora_abertura",
                    "dia_semana", "fim_de_semana", "mes", "tem_AM"]

X_cluster = df_cluster[features_cluster].copy()

colunas_categoricas = ["Prioridade_cluster", "Produto", "Categoria_cluster",
                        "Subcategoria_cluster", "Grupo designado", "Item_config_cluster", "Aberto por"]

X_cluster_encoded = pd.get_dummies(X_cluster, columns=colunas_categoricas, drop_first=False)
print("Shape após One-Hot:", X_cluster_encoded.shape)

scaler = StandardScaler()
X_cluster_scaled = (scaler.fit_transform(X_cluster_encoded))

print("Shape final:", X_cluster_scaled.shape)
print(f"Treinando KMeans ({K_FINAL} clusters)...")

kmeans_final = KMeans(n_clusters=K_FINAL, random_state=42, n_init=10)
df_cluster["cluster"] = (kmeans_final.fit_predict(X_cluster_scaled))
print(df_cluster["cluster"].value_counts().sort_index())

# export csv
df_export = pd.DataFrame()

df_export["Numero_Incidente"] = (df_cluster["Número"])

df_export["Cluster"] = (df_cluster["cluster"])

df_export.to_csv("outputs/clusters_incidentes.csv", index=False)

print("Arquivo clusters_incidentes.csv gerado.")

# salvando modelo
joblib.dump(kmeans_final, "artifacts/modelo_cluster.joblib")
print("Modelo salvo.")

# upload pra gold
print("\nEnviando para Gold...")
client = storage.Client()
bucket = client.bucket(BUCKET_GOLD)

arquivos = [
    ("artifacts/modelo_cluster.joblib",
    "modelos/modelo_cluster.joblib"),

    ("outputs/clusters_incidentes.csv",
    "previsoes/clusters_incidentes.csv")]

for local, destino in arquivos:
    blob = bucket.blob(destino)
    blob.upload_from_filename(local)

    print(f"Upload OK: {destino}")

print("\nPipeline de clusterização concluído.")
