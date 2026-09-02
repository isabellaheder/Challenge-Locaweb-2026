from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score)
from google.cloud import storage

ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet")

BUCKET_GOLD = "predictops-gold"

Path("artifacts").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

print("Lendo Silver...")
df = pd.read_parquet(ARQUIVO_SILVER)
df["Aberto"] = pd.to_datetime(df["Aberto"])
print(df.shape)

# feature engineering

df["mes"] = df["Aberto"].dt.month
df["tem_AM"] = (df["Descrição resumida"].str.contains("Application Monitoring", case=False, na=False).astype(int))

df_model = df[df["Aberto"] >= "2025-01-01"].copy() # usando dados a partir de 2025 (melhorou a previsão)

serie = (df_model.groupby(df_model["Aberto"].dt.date).size().reset_index(name="qtd_incidentes"))
serie.columns = ["data", "qtd_incidentes"]
serie["data"] = pd.to_datetime(serie["data"])

indicadores = (df.groupby(df["Aberto"].dt.date).agg({"tem_AM": "mean"}).reset_index().rename(columns={"Aberto": "data"}))
indicadores["data"] = pd.to_datetime(indicadores["data"])

serie = serie.merge(indicadores, on="data", how="left")

serie["lag_1"] = serie["qtd_incidentes"].shift(1)
serie["lag_2"] = serie["qtd_incidentes"].shift(2)
serie["lag_7"] = serie["qtd_incidentes"].shift(7)
serie["lag_14"] = serie["qtd_incidentes"].shift(14)
serie["lag_30"] = serie["qtd_incidentes"].shift(30)

serie["media_3d"] = (serie["qtd_incidentes"].rolling(3).mean())
serie["media_7d"] = (serie["qtd_incidentes"].rolling(7).mean())
serie["media_14d"] = (serie["qtd_incidentes"].rolling(14).mean())
serie["media_30d"] = (serie["qtd_incidentes"].rolling(30).mean())

serie["std_7d"] = (serie["qtd_incidentes"].rolling(7).std())
serie["trend_7_30"] = (serie["media_7d"] - serie["media_30d"])

serie["variacao_1d"] = (serie["lag_1"] - serie["lag_2"])
serie["variacao_7d"] = (serie["lag_1"] - serie["lag_7"])

serie["mes"] = serie["data"].dt.month
serie["dia_semana"] = serie["data"].dt.dayofweek

# targets 
serie["target_d1"] = (serie["qtd_incidentes"].shift(-1))
serie["target_d7"] = (serie["qtd_incidentes"].shift(-7))

serie_model = (serie.dropna().copy())
print(f"Linhas para modelagem: {len(serie_model)}")

# features finais
features = ["lag_1", "lag_7", "media_7d", "tem_AM", "mes"]

split = int(len(serie_model) * 0.8) # split temporal

train = serie_model.iloc[:split]
test = serie_model.iloc[split:]

X_train = train[features]
X_test = test[features]

# modelo D+1
print("\nTreinando D+1")

y_train = train["target_d1"]
y_test = test["target_d1"]

model_d1 = GradientBoostingRegressor(
    n_estimators=100,
    max_depth=4,
    learning_rate=0.03,
    random_state=42)

model_d1.fit(X_train, y_train)
pred_d1 = model_d1.predict(X_test)

print("\nMODELO D+1")

print("MAE:", mean_absolute_error(y_test, pred_d1))
print("RMSE:", np.sqrt(mean_squared_error(y_test, pred_d1)))
print("r2:",r2_score(y_test, pred_d1))

df_prev_d1 = pd.DataFrame({
    "Data": test["data"],
    "Incidentes_Previstos": pred_d1.round(0).astype(int),
    "Incidentes_Reais": y_test.values})

# joblib modelo
joblib.dump(model_d1, "artifacts/modelo_d1.joblib")

# export csv
df_prev_d1.to_csv("outputs/previsao_incidentes_d1.csv", index=False)

# modelo D+7
print("\nTreinando D+7")

y_train = train["target_d7"]
y_test = test["target_d7"]

model_d7 = GradientBoostingRegressor(
    n_estimators=100,
    max_depth=2,
    learning_rate=0.05,
    random_state=42)

model_d7.fit(X_train, y_train)
pred_d7 = model_d7.predict(X_test)

print("\nMODELO D+7")

print("MAE:", mean_absolute_error(y_test, pred_d7))
print("RMSE:", np.sqrt(mean_squared_error(y_test, pred_d7)))
print("r2:",r2_score(y_test, pred_d7))

mape = np.mean(np.abs((y_test - pred_d7) / y_test)) * 100
print(f'MAPE: {mape:.2f}%')

df_prev_d7 = pd.DataFrame({
    "Data": test["data"],
    "Incidentes_Previstos_D7": pred_d7.round(0).astype(int),
    "Incidentes_Reais_D7": y_test.values})

# joblib modelo
joblib.dump(model_d7, "artifacts/modelo_d7.joblib")

# export csv
df_prev_d7.to_csv("outputs/previsao_incidentes_d7.csv", index=False)

# upload gold
print("\nEnviando para Gold...")

client = storage.Client()
bucket = client.bucket(BUCKET_GOLD)

arquivos = [
    ("artifacts/modelo_d1.joblib", "modelos/modelo_d1.joblib"),
    ("artifacts/modelo_d7.joblib", "modelos/modelo_d7.joblib"),
    ("outputs/previsao_incidentes_d1.csv", "previsoes/previsao_incidentes_d1.csv"),
    ("outputs/previsao_incidentes_d7.csv", "previsoes/previsao_incidentes_d7.csv")]

for local, destino in arquivos:
    blob = bucket.blob(destino)
    blob.upload_from_filename(local)
    print(f"Upload OK: {destino}")

print("\nPipeline concluído.")
