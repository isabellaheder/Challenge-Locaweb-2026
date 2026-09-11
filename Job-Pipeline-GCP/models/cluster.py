from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = BASE_DIR / "outputs"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

OUTPUT_DIR.mkdir(exist_ok=True)
ARTIFACTS_DIR.mkdir(exist_ok=True)

import joblib
import pandas as pd
from google.cloud import storage
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet")

BUCKET_GOLD = "predictops-gold"
K_FINAL = 3

print("Lendo Silver...")
df = pd.read_parquet(ARQUIVO_SILVER)

df["Aberto"] = pd.to_datetime(df["Aberto"])

print(df.shape)

# feature engineering
df["mes"] = df["Aberto"].dt.month
df["tem_AM"] = (df["Descrição resumida"].str.contains("Application Monitoring", case=False, na=False).astype(int))
df_cluster = df.copy()

df_cluster["hora_abertura"] = df_cluster["Aberto"].dt.hour
df_cluster["dia_semana"] = df_cluster["Aberto"].dt.dayofweek
df_cluster["fim_de_semana"] = (df_cluster["dia_semana"] >= 5).astype(int)

top_ic = (df_cluster["Item de configuração"].value_counts().head(100).index)
df_cluster["Item_config_cluster"] = (df_cluster["Item de configuração"].where(df_cluster["Item de configuração"].isin(top_ic), "OUTROS"))
top_categoria = (df_cluster["Categoria"].value_counts().head(30).index)

df_cluster["Categoria_cluster"] = (df_cluster["Categoria"].where(df_cluster["Categoria"].isin(top_categoria),"OUTROS"))

top_subcategoria = (
    df_cluster["Subcategoria"]
    .value_counts()
    .head(30)
    .index
)

df_cluster["Subcategoria_cluster"] = (
    df_cluster["Subcategoria"]
    .where(
        df_cluster["Subcategoria"].isin(top_subcategoria),
        "OUTROS"
    )
)

df_cluster["Prioridade_cluster"] = (
    df_cluster["Prioridade"]
    .replace(
        {
            "1 - Crítica": "2 - Alta"
        }
    )
)

# ======================================================
# Features do clustering
# ======================================================

features_cluster = [
    "Prioridade_cluster",
    "Produto",
    "Categoria_cluster",
    "Subcategoria_cluster",
    "Grupo designado",
    "Item_config_cluster",
    "Aberto por",
    "hora_abertura",
    "dia_semana",
    "fim_de_semana",
    "mes",
    "tem_AM"
]

X_cluster = df_cluster[features_cluster].copy()

colunas_categoricas = [
    "Prioridade_cluster",
    "Produto",
    "Categoria_cluster",
    "Subcategoria_cluster",
    "Grupo designado",
    "Item_config_cluster",
    "Aberto por"
]

X_cluster_encoded = pd.get_dummies(
    X_cluster,
    columns=colunas_categoricas,
    drop_first=False
)

print("Shape após One-Hot:", X_cluster_encoded.shape)

# ======================================================
# Escalonamento
# ======================================================

scaler = StandardScaler()

X_cluster_scaled = scaler.fit_transform(
    X_cluster_encoded
)

print("Shape final:", X_cluster_scaled.shape)

# ======================================================
# KMeans
# ======================================================

print(f"Treinando KMeans ({K_FINAL} clusters)...")

kmeans_final = KMeans(
    n_clusters=K_FINAL,
    random_state=42,
    n_init=10
)

df_cluster["cluster"] = kmeans_final.fit_predict(
    X_cluster_scaled
)

print("\nDistribuição dos clusters:")
print(
    df_cluster["cluster"]
    .value_counts()
    .sort_index()
)

# ======================================================
# Nome amigável dos clusters
# ======================================================
# AJUSTE SE SUA ANÁLISE INDICAR OUTRA ORDEM

df_cluster["cluster"] = df_cluster["cluster"].astype(int)

nomes_clusters = {
    0: "Ruído de Monitoramento",
    1: "Operação Geral",
    2: "Cauda Crítica"
}

df_cluster["cluster_nome"] = (
    df_cluster["cluster"]
    .map(nomes_clusters)
)

# ======================================================
# Distância ao centroide
# ======================================================

distancias = kmeans_final.transform(
    X_cluster_scaled
)

df_cluster["distancia_centroide"] = [
    distancias[i, cluster]
    for i, cluster in enumerate(df_cluster["cluster"])
]

# ======================================================
# Export CSV
# ======================================================

df_export = pd.DataFrame()

df_export["Numero_Incidente"] = df_cluster["Número"]
df_export["Cluster"] = df_cluster["cluster"]
df_export["Cluster_Nome"] = df_cluster["cluster_nome"]

csv_path = OUTPUT_DIR / "clusters_incidentes.csv"

df_export.to_csv(
    csv_path,
    index=False
)

print(
    "\nArquivo clusters_incidentes.csv gerado."
)

# ======================================================
# Salvar artefatos
# ======================================================

joblib.dump(
    kmeans_final,
    ARTIFACTS_DIR / "modelo_cluster.joblib"
)

joblib.dump(
    scaler,
    ARTIFACTS_DIR / "scaler_cluster.joblib"
)

print("Modelo salvo.")


print(df_cluster["cluster"].value_counts(dropna=False))
print(df_cluster["cluster_nome"].value_counts(dropna=False))

df = pd.read_csv("outputs/clusters_incidentes.csv")
print("nulos:")
print(df["Cluster_Nome"].isna().sum())

# ======================================================
# Upload GCS
# ======================================================

print("\nEnviando para Gold...")

client = storage.Client()
bucket = client.bucket(BUCKET_GOLD)

arquivos = [
    (
        ARTIFACTS_DIR / "modelo_cluster.joblib",
        "modelos/modelo_cluster.joblib"
    ),
    (
        ARTIFACTS_DIR / "scaler_cluster.joblib",
        "modelos/scaler_cluster.joblib"
    ),
    (
        OUTPUT_DIR / "clusters_incidentes.csv",
        "previsoes/clusters_incidentes.csv"
    )
]

for local, destino in arquivos:
    blob = bucket.blob(destino)
    blob.upload_from_filename(local)
    print(f"Upload OK: {destino}")

print("\nPipeline de clusterização concluído.")
