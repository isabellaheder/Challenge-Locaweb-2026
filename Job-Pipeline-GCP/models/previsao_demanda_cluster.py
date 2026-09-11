from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from google.cloud import storage

from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
from sklearn.preprocessing import StandardScaler

# =====================================================
# CONFIG
# =====================================================

ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet"
)

BUCKET_GOLD = "predictops-gold"

DATA_INICIO = "2025-01-01"
FRACAO_TESTE = 0.20
SEED = 42

Path("artifacts").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

np.random.seed(SEED)

# =====================================================
# LEITURA
# =====================================================

print("Lendo Silver...")

df = pd.read_parquet(ARQUIVO_SILVER)

df["Aberto"] = pd.to_datetime(
    df["Aberto"],
    errors="coerce"
)

print(f"Incidentes: {len(df):,}")

# =====================================================
# FEATURES CLUSTER
# =====================================================

df["mes"] = df["Aberto"].dt.month

df["hora_abertura"] = df["Aberto"].dt.hour

df["dia_semana"] = df["Aberto"].dt.dayofweek

df["fim_de_semana"] = (
    df["dia_semana"] >= 5
).astype(int)

df["tem_AM"] = (
    df["Descrição resumida"]
    .str.contains(
        "Application Monitoring",
        case=False,
        na=False
    )
    .astype(int)
)

# =====================================================
# REDUÇÃO DE CARDINALIDADE
# =====================================================

def manter_top(coluna, n):

    mais_frequentes = (
        coluna
        .value_counts()
        .head(n)
        .index
    )

    return coluna.where(
        coluna.isin(mais_frequentes),
        "OUTROS"
    )

df["Item_config_cluster"] = manter_top(
    df["Item de configuração"],
    100
)

df["Categoria_cluster"] = manter_top(
    df["Categoria"],
    30
)

df["Subcategoria_cluster"] = manter_top(
    df["Subcategoria"],
    30
)

df["Prioridade_cluster"] = (
    df["Prioridade"]
    .replace({
        "1 - Crítica": "2 - Alta"
    })
)

# =====================================================
# CLUSTERIZAÇÃO
# =====================================================

COLUNAS_CATEGORICAS = [

    "Prioridade_cluster",
    "Produto",
    "Categoria_cluster",
    "Subcategoria_cluster",
    "Grupo designado",
    "Item_config_cluster",
    "Aberto por"

]

COLUNAS_NUMERICAS = [

    "hora_abertura",
    "dia_semana",
    "fim_de_semana",
    "mes",
    "tem_AM"

]

X = pd.get_dummies(
    df[
        COLUNAS_CATEGORICAS +
        COLUNAS_NUMERICAS
    ],
    columns=COLUNAS_CATEGORICAS
)

scaler = StandardScaler()

X_padronizado = scaler.fit_transform(X)

kmeans = KMeans(
    n_clusters=3,
    random_state=SEED,
    n_init=10
)

df["cluster"] = (
    kmeans.fit_predict(
        X_padronizado
    )
)

NOMES = {

    0: "Ruído de monitoramento",
    1: "Operação geral",
    2: "Cauda crítica"

}

df["cluster_nome"] = (
    df["cluster"]
    .map(NOMES)
)

# =====================================================
# PREPARAÇÃO DAS SÉRIES
# =====================================================

base = df.loc[
    df["Aberto"] >= DATA_INICIO
].copy()

base["data"] = (
    base["Aberto"]
    .dt.normalize()
)

CALENDARIO = pd.date_range(
    base["data"].min(),
    base["data"].max(),
    freq="D"
)

VARIAVEIS = [

    "lag_1",
    "lag_7",
    "media_7d",
    "tem_AM",
    "mes",
    "dia_semana"

]

def montar_serie(incidentes_cluster):

    por_dia = (
        incidentes_cluster
        .groupby("data")
    )

    serie = pd.DataFrame({

        "qtd_incidentes":
            por_dia.size(),

        "tem_AM":
            por_dia["tem_AM"].mean()

    })

    serie = (
        serie
        .reindex(CALENDARIO)
        .fillna(0)
    )

    serie.index.name = "data"

    serie = serie.reset_index()

    qtd = serie["qtd_incidentes"]

    serie["lag_1"] = qtd.shift(1)

    serie["lag_7"] = qtd.shift(7)

    serie["media_7d"] = qtd.rolling(7).mean()

    serie["mes"] = serie["data"].dt.month

    serie["dia_semana"] = serie["data"].dt.dayofweek

    serie["alvo_d1"] = qtd.shift(-1)

    serie["alvo_d7"] = qtd.shift(-7)

    return serie

series = {}

for nome in NOMES.values():

    series[nome] = montar_serie(
        base[
            base["cluster_nome"] == nome
        ]
    )

# =====================================================
# MÉTRICAS
# =====================================================

def calcular_metricas(real, previsto):

    real = np.asarray(real)
    previsto = np.asarray(previsto)

    sem_zero = real != 0

    return {

        "MAE":
            mean_absolute_error(
                real,
                previsto
            ),

        "RMSE":
            np.sqrt(
                mean_squared_error(
                    real,
                    previsto
                )
            ),

        "R2":
            r2_score(
                real,
                previsto
            ),

        "MAPE":
            np.mean(
                np.abs(
                    (
                        real[sem_zero]
                        -
                        previsto[sem_zero]
                    )
                    /
                    real[sem_zero]
                )
            ) * 100

    }

def criar_modelo():

    return GradientBoostingRegressor(

        n_estimators=200,
        max_depth=2,
        learning_rate=0.03,
        loss="huber",
        random_state=SEED

    )

def separar_treino_teste(
    serie,
    alvo
):

    limpa = (
        serie
        .dropna(
            subset=VARIAVEIS + [alvo]
        )
        .reset_index(drop=True)
    )

    corte = int(
        len(limpa)
        * (1 - FRACAO_TESTE)
    )

    return (
        limpa.iloc[:corte],
        limpa.iloc[corte:]
    )

def prever_com(
    candidato,
    treino,
    dias,
    alvo
):

    if candidato == "Persistencia":

        return dias["qtd_incidentes"].values

    if candidato == "Media7d":

        return dias["media_7d"].values

    if candidato == "ModeloGB":

        modelo = criar_modelo()

        modelo.fit(
            treino[VARIAVEIS],
            treino[alvo]
        )

        return np.maximum(
            0,
            modelo.predict(
                dias[VARIAVEIS]
            )
        )

    raise ValueError(candidato)

CANDIDATOS = [

    "ModeloGB",
    "Persistencia",
    "Media7d"

]

def treinar_e_escolher(
    serie,
    alvo
):

    treino, teste = (
        separar_treino_teste(
            serie,
            alvo
        )
    )

    corte = int(len(treino) * 0.8)

    treino_menor = treino.iloc[:corte]

    validacao = treino.iloc[corte:]

    mae_validacao = {

        c: mean_absolute_error(

            validacao[alvo],

            prever_com(
                c,
                treino_menor,
                validacao,
                alvo
            )

        )

        for c in CANDIDATOS

    }

    escolhido = min(
        mae_validacao,
        key=mae_validacao.get
    )

    previsao = prever_com(
        escolhido,
        treino,
        teste,
        alvo
    )

    resultado = {
        "escolhido": escolhido,
        **calcular_metricas(
            teste[alvo],
            previsao
        )
    }

    detalhe = pd.DataFrame({

        "data":
            teste["data"],

        "real":
            teste[alvo],

        "previsto":
            previsao

    })

    return (
        escolhido,
        resultado,
        detalhe
    )

# =====================================================
# TREINO
# =====================================================

escolhidos = {}
metricas = []
previsoes = {}

for nome in NOMES.values():

    for alvo, horizonte in [

        ("alvo_d1", "D+1"),
        ("alvo_d7", "D+7")

    ]:

        escolhido, resultado, detalhe = (
            treinar_e_escolher(
                series[nome],
                alvo
            )
        )

        escolhidos[(nome, horizonte)] = escolhido

        previsoes[(nome, horizonte)] = detalhe

        metricas.append({

            "cluster":
                nome,

            "horizonte":
                horizonte,

            **resultado

        })

        print(
            f"{nome} {horizonte} -> {escolhido}"
        )

tabela = pd.DataFrame(metricas)

# =====================================================
# PREVISÃO FUTURA
# =====================================================

linhas = []

for nome in NOMES.values():

    serie = series[nome]

    for alvo, horizonte, dias_a_frente in [

        ("alvo_d1", "D+1", 1),
        ("alvo_d7", "D+7", 7)

    ]:

        estimador = escolhidos[
            (nome, horizonte)
        ]

        historico = (
            serie.dropna(
                subset=VARIAVEIS + [alvo]
            )
        )

        ultimo_dia = (
            serie.dropna(
                subset=VARIAVEIS
            )
            .iloc[[-1]]
        )

        valor = prever_com(
            estimador,
            historico,
            ultimo_dia,
            alvo
        )[0]

        linhas.append({

            "cluster":
                nome,

            "horizonte":
                horizonte,

            "estimador":
                estimador,

            "data_prevista":
                (
                    ultimo_dia["data"]
                    .iloc[0]
                    +
                    pd.Timedelta(
                        days=dias_a_frente
                    )
                ).date(),

            "incidentes_previstos":
                int(round(valor))

        })

previsao_final = pd.DataFrame(linhas)

# =====================================================
# EXPORTS
# =====================================================

for horizonte, arquivo in [

    (
        "D+1",
        "outputs/previsao_d1_por_cluster.csv"
    ),

    (
        "D+7",
        "outputs/previsao_d7_por_cluster.csv"
    )

]:

    historico = pd.concat(

        [

            previsoes[
                (nome, horizonte)
            ]
            .assign(
                cluster=nome,
                origem="backtest"
            )

            for nome in NOMES.values()

        ],
        ignore_index=True

    )

    futuro = (

        previsao_final[
            previsao_final["horizonte"]
            == horizonte
        ]

        .rename(
            columns={
                "data_prevista":
                    "data",

                "incidentes_previstos":
                    "previsto"
            }
        )

        [["data", "cluster", "previsto"]]

        .assign(
            real=np.nan,
            origem="projecao"
        )

    )

    saida = pd.concat(
        [historico, futuro],
        ignore_index=True
    )

    saida["horizonte"] = horizonte

    saida.to_csv(
        arquivo,
        index=False
    )

tabela.to_csv(
    "outputs/metricas_previsao_por_cluster.csv",
    index=False
)

# =====================================================
# UPLOAD GCS
# =====================================================

client = storage.Client()

bucket = client.bucket(
    BUCKET_GOLD
)

arquivos = [

    (
        "outputs/previsao_d1_por_cluster.csv",
        "previsoes/previsao_d1_por_cluster.csv"
    ),

    (
        "outputs/previsao_d7_por_cluster.csv",
        "previsoes/previsao_d7_por_cluster.csv"
    ),

    (
        "outputs/metricas_previsao_por_cluster.csv",
        "metricas/metricas_previsao_por_cluster.csv"
    )

]

for local, destino in arquivos:

    blob = bucket.blob(destino)

    blob.upload_from_filename(local)

    print(
        f"Upload OK: {destino}"
    )

print(
    "\nPipeline de previsão de demanda por cluster concluído."
)
