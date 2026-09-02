import re
import unicodedata
import pandas as pd
from google.cloud import bigquery

PROJECT_ID = "predictops-challenge-2026"
DATASET = "predictops_gold"
TABELA = "incidentes"
ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet")

print("Lendo Silver...")
df = pd.read_parquet(ARQUIVO_SILVER)
print(f"Shape original: {df.shape}")

def limpar_coluna(col):
    col = unicodedata.normalize("NFKD", str(col))
    col = (col.encode("ascii", "ignore").decode("utf-8"))
    col = col.lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)
    col = col.strip("_")
    return col

df.columns = [
    limpar_coluna(col)
    for col in df.columns]

duplicadas = df.columns[df.columns.duplicated()]

if len(duplicadas) > 0:
    print("\nColunas duplicadas encontradas:")

    for col in duplicadas:
        print(col)

    df = df.loc[
        :,
        ~df.columns.duplicated(
            keep="first")]

print(f"\nQuantidade de colunas: "
    f"{len(df.columns)}")

for col in df.columns:
    try:
        if pd.api.types.is_object_dtype(
            df[col]
        ):
            df[col] = df[col].astype(str)

    except Exception as e:
        print(f"Erro na coluna {col}: {e}")


print("\nPrimeiras colunas:")
print(df.columns.tolist()[:20])

print("\nTipos:")
print(df.dtypes.head(20))

print(f"\nShape final: {df.shape}")

client = bigquery.Client(project=PROJECT_ID)

table_id = (
    f"{PROJECT_ID}."
    f"{DATASET}."
    f"{TABELA}")

job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")

print(
    f"\nPublicando tabela:"
    f"\n{table_id}")

job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
job.result()

print("\nTabela incidentes publicada com sucesso.")
