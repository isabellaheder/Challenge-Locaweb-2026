from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from google.cloud import storage
from imblearn.under_sampling import RandomUnderSampler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (accuracy_score,classification_report, confusion_matrix, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight

ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet")

BUCKET_GOLD = "predictops-gold"
THRESHOLD = 0.30

Path("artifacts").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

print("Lendo Silver...")
df = pd.read_parquet(ARQUIVO_SILVER)
df["Aberto"] = pd.to_datetime(df["Aberto"])
print(f"Dataset carregado: {df.shape}")

# filtro kpi

df_kpi = df[df["Entrou para KPI?"] == "SIM"].copy()
print(f"Incidentes elegíveis para KPI: {df_kpi.shape}")

# target 
y = df_kpi["kpi_violado"]

# remover leaks

colunas_remover = [
    # leak
    "Resolvido", "Encerrado", "Duração",
    "Código de fechamento", "Solução",
    "Status", "tem_resolucao", "tem_CF",

    # sem uso
    "KPI Violado?", "Entrou para KPI?",
    "kpi_nao_aplicavel", "Incidente Pai",
    "tem_pai",

    # id
    "Número",

    # texto livre
    "Descrição resumida"]

X = df_kpi.drop(columns=colunas_remover, errors="ignore")

# features datas
X["hora_abertura"] = (df_kpi["Aberto"].dt.hour)
X["dia_semana"] = (df_kpi["Aberto"].dt.dayofweek)
X["fim_de_semana"] = (df_kpi["Aberto"].dt.dayofweek >= 5).astype(int)

X = X.drop(columns=["Aberto"], errors="ignore")
X = X.drop(columns=["kpi_violado"], errors="ignore")

# split
X_train, X_test, y_train, y_test = train_test_split(X, y,
    test_size=0.20, random_state=42, stratify=y)

print(f"Treino: {X_train.shape}")
print(f"Teste: {X_test.shape}")

# categoricas
colunas_dummy = [
    "Prioridade", "Produto", "Categoria", "Subcategoria",
    "Grupo designado", "Item de configuração", "Aberto por"]

colunas_presentes = [c for c in colunas_dummy
                    if c in X_train.columns]

X_train = pd.get_dummies(X_train, columns=colunas_presentes, drop_first=True)
X_test = pd.get_dummies(X_test, columns=colunas_presentes, drop_first=True)

X_train, X_test = X_train.align(X_test, join="left", axis=1, fill_value=0)

# salvar features
joblib.dump(list(X_train.columns), "artifacts/sla_features.joblib")

# undersampling

rus = RandomUnderSampler(random_state=42)
X_train_under, y_train_under = (rus.fit_resample(X_train, y_train))

print("\nDistribuição original:")
print(y_train.value_counts())

print("\nApós undersampling:")
print(y_train_under.value_counts())

# pesos
sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)

# treino
print("\nTreinando modelo SLA...")
gb = GradientBoostingClassifier(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=3,
    random_state=42)

gb.fit(X_train, y_train, sample_weight=sample_weights)

# previsao
y_proba = gb.predict_proba(X_test)[:, 1]
y_pred = (y_proba >= THRESHOLD).astype(int)

# metricas
print("\nRESULTADOS")
print(f"Acurácia: {accuracy_score(y_test, y_pred):.4f}")
print(f"Precisão: {precision_score(y_test, y_pred):.4f}")
print(f"Recall: {recall_score(y_test, y_pred):.4f}")
print(f"ROC AUC: {roc_auc_score(y_test, y_pred):.4f}")

print("\nClassification Report")
print(classification_report(y_test, y_pred))

print("\nConfusion Matrix")
print(confusion_matrix(y_test, y_pred))

# salvando modelo
joblib.dump(gb, "artifacts/modelo_sla.joblib")
print("\nModelo salvo.")

# exportar csv

# exportar csv
df_export = pd.DataFrame({
    "Numero_Incidente": df_kpi.loc[X_test.index, "Número"],
    "KPI_Violado_Real": y_test.values,
    "Probabilidade_Violacao": y_proba,
    "Probabilidade_Violacao_%": (y_proba * 100).round(2),})

df_export["Risco"] = np.select([y_proba >= 0.7, y_proba >= 0.3],["ALTO", "MEDIO"], default="BAIXO")
df_export = df_export.sort_values("Probabilidade_Violacao", ascending=False)

arquivo_saida = "outputs/previsao_sla.csv"
df_export.to_csv(arquivo_saida, index=False)

print(f"\nArquivo salvo: {arquivo_saida}")

# upload gold
print("\nEnviando para Gold...")

client = storage.Client()
bucket = client.bucket(BUCKET_GOLD)

arquivos = [
    ("artifacts/modelo_sla.joblib", "modelos/modelo_sla.joblib"),
    ("artifacts/sla_features.joblib", "modelos/sla_features.joblib"),
    ("outputs/previsao_sla.csv", "previsoes/previsao_sla.csv")]

for local, destino in arquivos:
    blob = bucket.blob(destino)
    blob.upload_from_filename(local)
    print(f"Upload OK: {destino}")

print("\nPipeline SLA finalizado.")
