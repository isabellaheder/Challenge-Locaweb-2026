from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from google.cloud import storage
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score)
from sklearn.model_selection import train_test_split

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
df["Duracao_log"] = np.log1p(df["Duração"]) # transformando duração com log1p

df["hora_aberto"] = df["Aberto"].dt.hour
df["dia_semana"] = df["Aberto"].dt.dayofweek
df["fim_semana"] = (df["dia_semana"].isin([5, 6]).astype(int))
df["fora_comercial"] = ((df["hora_aberto"] < 8) | (df["hora_aberto"] >= 18)).astype(int)
df["monitoramento"] = (df["Aberto por"] == "Monitoramento").astype(int)

map_prioridade = {
    "1 - Crítica": 1,
    "2 - Alta": 2,
    "3 - Média": 3,
    "4 - Baixa": 4,
    "5 - Muito Baixa": 5 }

df["prioridade_num"] = (df["Prioridade"].map(map_prioridade))

# features
cat = ["Produto", "Categoria", "Grupo designado"]
num = ["prioridade_num", "hora_aberto", "fim_semana", "fora_comercial", "monitoramento", "tem_pai"]

X = df[cat + num]
y = df["Duracao_log"]

# split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

X_train = pd.get_dummies(X_train, columns=cat)
X_test = pd.get_dummies(X_test, columns=cat)

X_train, X_test = X_train.align(X_test, join="left", axis=1, fill_value=0)

# modelo

model = RandomForestRegressor(
    n_estimators=200,
    random_state=42,
    n_jobs=-1)

print("Treinando modelo...")
model.fit(X_train, y_train)
pred = model.predict(X_test)

# métricas
print("MAE:", mean_absolute_error(y_test, pred))
print("RMSE:", np.sqrt(mean_squared_error(y_test, pred)))
print("r2:", r2_score(y_test, pred))
mape = np.mean(np.abs((y_test - pred) / y_test)) * 100
print(f"MAPE: {mape:.2f}%")

# métricas em hora (tirando o log1p)
real_h = np.expm1(y_test) / 3600
prev_h = np.expm1(pred) / 3600
erro_h = np.abs(prev_h - real_h)

print(f"\nErro mediano: {np.median(erro_h):.1f} horas")
print(f"Dentro de 2h: {(erro_h <= 2).mean()*100:.0f}% dos casos")
print(f"Dentro de 1h: {(erro_h <= 1).mean()*100:.0f}% dos casos")
print(f"Dentro de 30m: {(erro_h <= 0.5).mean()*100:.0f}% dos casos")
print(f"Dentro de 15m: {(erro_h <= 0.25).mean()*100:.0f}% dos casos")

# export
df_export = pd.DataFrame()
df_export["Numero_Incidente"] = (df.loc[X_test.index,"Número"])
df_export["Duracao_Real"] = (np.expm1(y_test))
df_export["Duracao_Prevista"] = (np.expm1(pred))

df_export = df_export.sort_values(by="Duracao_Prevista", ascending=False)
df_export.to_csv("outputs/export_previsao_duracao.csv", index=False)

print("Arquivo export_previsao_duracao.csv gerado com sucesso!")
