"""
Camada de consulta local (NL2SQL / chatbot).

A fonte de dados é o BigQuery (ver bq_loader.py). Para preservar o comportamento
do NL2SQL e dos assistentes de chat — que geram SQL no dialeto SQLite —, as
tabelas do dataset `predictops_gold` são materializadas em um banco SQLite em
memória. Os dados vêm do BigQuery; as consultas geradas pela IA rodam
localmente, sem risco de diferença de dialeto.

Antes só a tabela `incidentes` era materializada, então nenhuma pergunta sobre
previsão (D+1, D+7, risco de SLA, duração, clusters) tinha como ser respondida —
o assistente gerava SQL contra uma tabela que não continha esses dados. Agora
todas as tabelas do dataset ficam disponíveis.
"""
import sqlite3
import unicodedata
import pandas as pd
import streamlit as st

# Reexporta o carregador de incidentes do BigQuery (mantém a API antiga).
from bq_loader import load_incident_data, load_prediction_table, load_bq_table, run_bq_query  # noqa: F401

# Tabelas preditivas expostas ao SQL gerado pela IA, com uma descrição curta que
# entra no prompt para o modelo saber quando usar cada uma.
TABELAS_PREDITIVAS = {
    "previsao_d1": "Previsão de volume de incidentes para D+1 por data (previsto x realizado).",
    "previsao_d7": "Previsão de volume de incidentes para D+7 por data (previsto x realizado).",
    "previsao_turno": "Previsão de volume por data e turno (Madrugada/Manhã/Tarde/Noite).",
    "previsao_sla": "Probabilidade de violação de SLA por incidente, com grupo, produto, prioridade e faixa de risco.",
    "previsao_duracao": "Duração prevista x real de resolução por incidente (em segundos).",
    "clusters_incidentes": "Cluster numérico atribuído a cada incidente.",
    "cluster_nlp": "Cluster de NLP e descrição original de cada incidente.",
}


def normalize_column_name(name: str) -> str:
    """Remove acentos e caracteres especiais para nomes de colunas SQL padrão.

    `%` vira `_pct` de propósito: descartá-lo faria `Probabilidade_Violacao_%`
    colidir com `Probabilidade_Violacao` e a coluna acabaria renomeada para algo
    opaco como `..._2`, que o modelo não teria como interpretar.
    """
    nfkd = unicodedata.normalize('NFKD', str(name))
    no_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    no_accents = no_accents.replace("%", "_pct")
    clean = "".join(
        ch if (ch.isalnum() or ch == "_") else ("_" if ch in " -/" else "")
        for ch in no_accents
    ).strip("_")
    while "__" in clean:
        clean = clean.replace("__", "_")
    if clean and clean[0].isdigit():
        clean = f"c_{clean}"
    return clean or "coluna"


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes de coluna resolvendo colisões case-insensitive."""
    seen, cols = {}, []
    for c in df.columns:
        limpo = normalize_column_name(c)
        chave = limpo.lower()
        if chave in seen:
            seen[chave] += 1
            limpo = f"{limpo}_{seen[chave]}"
        else:
            seen[chave] = 1
        cols.append(limpo)
    out = df.copy()
    out.columns = cols
    # Datas viram texto ISO — o SQLite compara e ordena corretamente assim.
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out


@st.cache_resource(show_spinner="Preparando as tabelas do BigQuery para consulta...")
def get_sqlite_engine():
    """Materializa o dataset do BigQuery em SQLite e devolve (conn, schema).

    `schema` é um dict {nome_da_tabela: [colunas]}. Mantém compatibilidade com o
    uso antigo `conn, cols = get_sqlite_engine()`: quando desempacotado, o
    segundo item continua sendo consultável — use `schema["incidentes"]` para as
    colunas da base de incidentes.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    schema = {}

    inc = _normalizar_df(load_incident_data())
    inc.to_sql("incidentes", conn, index=False, if_exists="replace")
    schema["incidentes"] = list(inc.columns)

    for nome in TABELAS_PREDITIVAS:
        try:
            df = load_prediction_table(nome)
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty:
            continue  # tabela indisponível no BigQuery: fica de fora, sem substituto
        df = _normalizar_df(df)
        df.to_sql(nome, conn, index=False, if_exists="replace")
        schema[nome] = list(df.columns)

    return conn, schema


def descrever_schema() -> str:
    """Schema em texto para o prompt de geração de SQL."""
    _, schema = get_sqlite_engine()
    linhas = []
    for tabela, cols in schema.items():
        desc = TABELAS_PREDITIVAS.get(tabela, "Base de incidentes (fato principal).")
        linhas.append(f"- {tabela} — {desc}\n  colunas: {', '.join(cols)}")
    return "\n".join(linhas)


def tabelas_disponiveis() -> list:
    _, schema = get_sqlite_engine()
    return list(schema.keys())


def run_sql_query(query: str):
    """Executa queries SQL geradas pelo Gemini no SQLite (dados do BigQuery)."""
    conn, _ = get_sqlite_engine()
    return pd.read_sql_query(query, conn)
