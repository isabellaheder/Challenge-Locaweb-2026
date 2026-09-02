from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from google.cloud import storage
from sklearn.ensemble import (GradientBoostingRegressor, RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor)
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score)

ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet")

BUCKET_GOLD = "predictops-gold"

Path("artifacts").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

print("Lendo Silver...")
df = pd.read_parquet(ARQUIVO_SILVER)
df["Aberto"] = pd.to_datetime(df["Aberto"], errors="coerce")

df = df.loc[df["Aberto"].notna() & (df["Aberto"] >= "2025-01-01")].copy()
print(df.shape)

# preparação dos dados
df["data"] = df["Aberto"].dt.normalize()

df["turno"] = pd.cut(
    df["Aberto"].dt.hour, bins=[0, 6, 12, 18, 24],
    labels=["Madrugada", "Manhã", "Tarde", "Noite"],
    right=False, include_lowest=True)

serie = (df.groupby(["data", "turno"], observed=False).size().reset_index(name="qtd_incidentes"))

datas = pd.date_range(serie["data"].min(), serie["data"].max(), freq="D")

idx = pd.MultiIndex.from_product([datas, ["Madrugada", "Manhã", "Tarde", "Noite"]], names=["data", "turno"])

serie = (serie.set_index(["data", "turno"]).reindex(idx, fill_value=0).reset_index())

print(f"Total de registros: {len(df):,}")
print(f"Período analisado: {datas.min():%Y-%m-%d} a {datas.max():%Y-%m-%d}")

serie["turno_code"] = serie["turno"].map({"Madrugada": 0, "Manhã": 1, "Tarde": 2, "Noite": 3})

serie["dow"] = serie["data"].dt.dayofweek
serie["mes"] = serie["data"].dt.month
serie["is_weekend"] = (serie["dow"] >= 5).astype(int)

g = serie.groupby("turno", observed=False)["qtd_incidentes"]

serie["lag_1"] = g.shift(1)
serie["lag_7"] = g.shift(7)
serie["lag_14"] = g.shift(14)

serie["media_7d"] = g.transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
serie["media_14d"] = g.transform(lambda s: s.shift(1).rolling(14, min_periods=1).mean())

# features
features_base = ["lag_1", "lag_7", "media_7d", "mes", "dow", "is_weekend"]
features_plus = features_base + ["media_14d", "lag_14"]

serie_model = (serie.dropna(subset=features_plus).reset_index(drop=True))

print(f"Observações modeláveis: {len(serie_model):,}")

# métricas
def safe_mape(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    return (np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
        if mask.any()
        else np.nan)

def metricas(y_true, y_pred):
    return {"mae": mean_absolute_error(y_true, y_pred),
        "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
        "r2": r2_score(y_true, y_pred),
        "mape": safe_mape(y_true, y_pred)}

# split temporal
split = int(len(serie_model) * 0.8)

train = serie_model.iloc[:split]
test = serie_model.iloc[split:]

print(
    f"Treino: {len(train):,} | "
    f"Teste: {len(test):,} | "
    f"corte na linha: {split}")

# modelos

models = {
    "GradientBoosting_base": (
        GradientBoostingRegressor(
            n_estimators=200,
            max_depth=2,
            learning_rate=0.03,
            loss="huber",
            random_state=42), features_base),

    "GradientBoosting_plus": (
        GradientBoostingRegressor(
            n_estimators=200,
            max_depth=2,
            learning_rate=0.03,
            loss="huber",
            random_state=42), features_plus),

    "RandomForest_plus": (
        RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1), features_plus),

    "ExtraTrees_plus": (
        ExtraTreesRegressor(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1), features_plus),

    "HistGradientBoosting_plus": (
        HistGradientBoostingRegressor(
            max_iter=200,
            max_leaf_nodes=15,
            learning_rate=0.04,
            l2_regularization=1.0,
            random_state=42), features_plus)}

# treino
resultados = []
predicoes = {}
modelos_treinados = {}

for nome, (modelo, features) in models.items():
    X_train = train[features + ["turno_code"]]
    X_test = test[features + ["turno_code"]]

    y_train = train["qtd_incidentes"]
    y_test = test["qtd_incidentes"]

    modelo.fit(X_train, y_train)
    previsoes = np.maximum(0, modelo.predict(X_test))

    modelos_treinados[nome] = modelo
    predicoes[nome] = (test[["data", "turno", "qtd_incidentes"]].assign(numero_previsto=previsoes, modelo=nome))
    resultados.append({"modelo": nome, **metricas(y_test, previsoes)})

# baseline
baseline = np.maximum(0, test["lag_1"])
resultados.append({"modelo": "Baseline_lag_1", **metricas(y_test, baseline)})

comparacao = (pd.DataFrame(resultados).sort_values(["mae", "rmse"]).reset_index(drop=True))
best_model = comparacao.iloc[0]["modelo"]
best_pred = predicoes[best_model].copy()
print(f"Melhor modelo: {best_model}")

print("Métricas gerais:", {k: round(v, 4)
        for k, v in metricas(
            best_pred["qtd_incidentes"],
            best_pred["numero_previsto"]).items()})

# métricas por turno
metricas_turno = (best_pred.groupby("turno", observed=False)
    .apply(lambda df:
            pd.Series(metricas(df["qtd_incidentes"], df["numero_previsto"])))
            .reset_index()[["turno", "mae", "mape", "rmse"]].sort_values("turno"))

metricas_turno.to_csv("outputs/metricas_turno.csv", index=False)

# previsoes

df_previsoes_turno = pd.DataFrame({
    "Data": best_pred["data"].dt.strftime("%Y-%m-%d"),
    "Turno": best_pred["turno"],
    "Incidentes_Previstos": best_pred["numero_previsto"].round(0).astype(int),
    "Incidentes_Reais": best_pred["qtd_incidentes"].astype(int)})

df_previsoes_turno = (df_previsoes_turno.sort_values(["Data", "Turno"]))
df_previsoes_turno.to_csv("outputs/previsao_incidentes_turno.csv", index=False)

# salvar modelo

modelo_final = modelos_treinados[best_model]
joblib.dump(modelo_final, "artifacts/modelo_turno.joblib")

# upload gcs

print("\nEnviando para Gold...")
client = storage.Client()
bucket = client.bucket(BUCKET_GOLD)

arquivos = [
    ("artifacts/modelo_turno.joblib", "modelos/modelo_turno.joblib"),
    ("outputs/previsao_incidentes_turno.csv", "previsoes/previsao_incidentes_turno.csv"),
    ("outputs/metricas_turno.csv", "metricas/metricas_turno.csv")]

for local, destino in arquivos:
    blob = bucket.blob(destino)
    blob.upload_from_filename(local)
    print(f"Upload OK: {destino}")

print("\nPipeline de previsão por turno concluído.")
