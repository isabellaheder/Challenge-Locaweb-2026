"""
Camada de acesso ao BigQuery do Predict Ops.

Substitui o carregamento via bucket GCS / Excel: agora a fonte de verdade é o
dataset `predictops-challenge-2026.predictops_gold`, com as tabelas:
  incidentes, cluster_nlp, clusters_incidentes,
  previsao_d1, previsao_d7, previsao_duracao, previsao_sla, previsao_turno.

A tabela `incidentes` equivale ao antigo LW-DATASET-TRATADO.xlsx; as demais são
os resultados dos modelos preditivos.
"""
import os
import re
import time
import unicodedata
import pandas as pd
import streamlit as st

from config import (
    BQ_CREDENTIALS_PATH, BQ_PROJECT, BQ_DATASET, BQ_LOCATION, BQ_TABLES,
    BQ_INCIDENTES_COLUMN_MAP, LOCAL_DATASET_PATH,
)

# ----------------------------------------------------------------------------
# Cliente BigQuery
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_bq_client():
    """Cria (e cacheia) o cliente BigQuery a partir da chave de serviço."""
    from google.cloud import bigquery
    from google.oauth2 import service_account

    if BQ_CREDENTIALS_PATH and os.path.exists(BQ_CREDENTIALS_PATH):
        creds = service_account.Credentials.from_service_account_file(
            BQ_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        project = BQ_PROJECT or creds.project_id
        return bigquery.Client(project=project, credentials=creds, location=BQ_LOCATION)

    # Sem arquivo de chave: tenta Application Default Credentials (ADC).
    return bigquery.Client(project=BQ_PROJECT or None, location=BQ_LOCATION)


def _table_ref(table_name: str) -> str:
    return f"{BQ_PROJECT}.{BQ_DATASET}.{table_name}"


@st.cache_data(ttl=1800, show_spinner=False)
def load_bq_table(logical_name: str) -> pd.DataFrame:
    """Carrega uma tabela inteira do dataset como DataFrame.

    Usa tabledata.list (list_rows), que não consome slot de query nem exige a
    localização do dataset. `logical_name` é uma das chaves de BQ_TABLES.
    """
    from google.cloud import bigquery

    real_name = BQ_TABLES.get(logical_name, logical_name)
    client = get_bq_client()
    table_ref = bigquery.TableReference.from_string(_table_ref(real_name))
    rows = client.list_rows(table_ref)
    df = rows.to_dataframe(create_bqstorage_client=False)
    return df


def run_bq_query(sql: str) -> pd.DataFrame:
    """Executa uma query SQL padrão no BigQuery e devolve um DataFrame."""
    client = get_bq_client()
    job = client.query(sql, location=BQ_LOCATION)
    return job.result().to_dataframe(create_bqstorage_client=False)


# ----------------------------------------------------------------------------
# Mapeamento de colunas da tabela `incidentes` -> nomes amigáveis das telas
# ----------------------------------------------------------------------------
# Colunas exatamente como as telas esperam (idênticas ao Excel original).
_CANONICAL_COLS = [
    "Número", "Prioridade", "Produto", "Categoria", "Subcategoria",
    "Grupo designado", "Item de configuração", "Aberto", "Resolvido",
    "Encerrado", "Duração", "Código de fechamento", "Descrição resumida",
    "Solução", "Aberto por", "Incidente Pai", "Status", "Entrou para KPI?",
    "KPI Violado?", "tem_resolucao", "tem_pai", "tem_produto", "tem_categoria",
    "tem_subcategoria", "tem_item_config", "tem_CF", "kpi_violado",
    "kpi_nao_aplicavel",
]

# Colunas que as telas realmente consultam — garantimos que existam.
_CRITICAL_COLS = [
    "Prioridade", "Produto", "Categoria", "Grupo designado",
    "Aberto", "Status", "KPI Violado?",
]

_DATE_COLS = ["Aberto", "Resolvido", "Encerrado"]
_SIM_NAO = {"SIM", "NAO", "NÃO", "NAO_APLICAVEL", "NAO APLICAVEL", "NÃO APLICÁVEL"}


def _norm_key(name: str) -> str:
    """Chave de comparação: minúsculas, sem acento e só letras/números."""
    nfkd = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _map_incident_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia as colunas vindas do BigQuery para os nomes que as telas usam.

    Faz correspondência por chave normalizada (tolerante a acento/caixa/símbolo).
    O único par realmente ambíguo é 'KPI Violado?' (texto SIM/NAO) vs
    'kpi_violado' (0/1); resolvemos escolhendo, para 'KPI Violado?', a coluna
    cujos valores são SIM/NAO.
    """
    bq_cols = list(df.columns)
    norm_bq = {c: _norm_key(c) for c in bq_cols}
    used = set()
    rename = {}

    for fname in _CANONICAL_COLS:
        fkey = _norm_key(fname)
        candidates = [c for c in bq_cols if c not in used and norm_bq[c] == fkey]
        if not candidates:
            continue

        if fname == "KPI Violado?":
            # Só mapeia para 'KPI Violado?' a coluna de TEXTO (SIM/NAO). Se só
            # houver a versão numérica, não mapeia aqui — deixa para _ensure_view_columns
            # derivar SIM/NAO a partir dela.
            chosen = None
            for c in candidates:
                vals = {str(v).strip().upper() for v in df[c].dropna().unique()[:25]}
                if vals & _SIM_NAO:
                    chosen = c
                    break
            if chosen is None:
                continue
        else:
            chosen = candidates[0]

        rename[chosen] = fname
        used.add(chosen)

    df = df.rename(columns=rename)

    # Override manual do config vence o automático.
    if BQ_INCIDENTES_COLUMN_MAP:
        df = df.rename(columns={k: v for k, v in BQ_INCIDENTES_COLUMN_MAP.items() if k in df.columns})

    return df


def _ensure_view_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que as colunas críticas existam para as telas não quebrarem."""
    def _to_sim_nao(v):
        s = str(v).strip().upper()
        return "SIM" if s in {"1", "1.0", "TRUE", "SIM"} else "NAO"

    # 'KPI Violado?' é a mais usada — se faltar, deriva de um kpi_violado numérico.
    if "KPI Violado?" not in df.columns:
        num_kpi = next((c for c in df.columns if _norm_key(c) == "kpiviolado"), None)
        if num_kpi is not None:
            df["KPI Violado?"] = df[num_kpi].apply(_to_sim_nao)
    else:
        # Existe, mas pode ter vindo numérica (0/1) — normaliza para SIM/NAO.
        col_vals = {str(v).strip().upper() for v in df["KPI Violado?"].dropna().unique()[:25]}
        if col_vals and not (col_vals & _SIM_NAO):
            df["KPI Violado?"] = df["KPI Violado?"].apply(_to_sim_nao)

    for col in _CRITICAL_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    return df


# ----------------------------------------------------------------------------
# Registro de origem dos dados (para o aviso de conexão nas telas)
# ----------------------------------------------------------------------------
# Persiste entre reruns do Streamlit (global de módulo no mesmo processo).
_INCIDENT_SOURCE = {"source": None, "rows": None, "ref": None, "error": None, "ts": None}


def _record_source(source, rows=None, ref=None, error=None):
    _INCIDENT_SOURCE.update(
        source=source, rows=rows, ref=ref, error=error,
        ts=time.strftime("%d/%m/%Y %H:%M:%S"),
    )


def get_incident_source(ensure: bool = False) -> dict:
    """Devolve a origem da última carga de `incidentes` (bigquery/local/erro).
    Com ensure=True, dispara a carga (cacheada) caso ainda não tenha ocorrido."""
    if ensure and _INCIDENT_SOURCE["source"] is None:
        try:
            load_incident_data()
        except Exception as e:
            _record_source("error", error=str(e))
    return dict(_INCIDENT_SOURCE)


def render_data_source_banner(compact: bool = False) -> None:
    """Mostra um aviso indicando se os dados vieram do BigQuery ou do fallback local."""
    status = get_incident_source(ensure=True)
    src = status.get("source")
    rows = status.get("rows")
    rows_txt = f"{rows:,}".replace(",", ".") if isinstance(rows, int) else "?"

    if src == "bigquery":
        st.success(
            f"**BigQuery conectado** — dados sincronizados de "
            f"`{status['ref']}` ({rows_txt} linhas)."
        )
    elif src == "local":
        msg = (
            f"**Fallback LOCAL em uso** — não foi possível ler do BigQuery, "
            f"usando `{status['ref']}` ({rows_txt} linhas)."
        )
        if status.get("error"):
            msg += f"\n\nMotivo: `{status['error']}`"
        st.warning(msg)
    elif src == "error":
        st.error(
            "**Sem dados** — BigQuery indisponível e sem arquivo local de fallback."
            + (f"\n\nMotivo: `{status['error']}`" if status.get("error") else "")
        )
    else:
        st.info("Fonte de dados ainda não carregada.")


# ----------------------------------------------------------------------------
# Carregamento da base de incidentes
# ----------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner="Carregando incidentes do BigQuery (predictops_gold)...")
def load_incident_data() -> pd.DataFrame:
    """Carrega a tabela `incidentes` do BigQuery e a devolve com as colunas
    amigáveis usadas pelas telas. Cai para o Excel local só se o BigQuery falhar."""
    df = None
    bq_error = None
    try:
        df = load_bq_table("incidentes")
        df = _map_incident_columns(df)
        df = _ensure_view_columns(df)
        _record_source(
            "bigquery", rows=len(df),
            ref=f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLES.get('incidentes', 'incidentes')}",
        )
    except Exception as e:
        bq_error = str(e)
        st.warning(
            "Não foi possível carregar a tabela 'incidentes' do BigQuery — "
            f"usando o arquivo local como fallback. Detalhe: {e}"
        )
        df = None

    if df is None:
        if os.path.exists(LOCAL_DATASET_PATH):
            df = pd.read_excel(LOCAL_DATASET_PATH)
            _record_source("local", rows=len(df), ref=os.path.basename(LOCAL_DATASET_PATH), error=bq_error)
        else:
            _record_source("error", error=bq_error or "arquivo local ausente")
            raise FileNotFoundError(
                "Base de incidentes indisponível: BigQuery falhou e não há arquivo "
                f"local em {LOCAL_DATASET_PATH}."
            )

    # Padronização de datas (idempotente).
    for col in _DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


# ----------------------------------------------------------------------------
# Carregadores das tabelas de previsão / clusters (para os gráficos dinâmicos)
# ----------------------------------------------------------------------------
# Chave natural de cada tabela preditiva. As tabelas do `predictops_gold` foram
# gravadas em WRITE_APPEND e contêm a mesma previsão repetida várias vezes; sem
# deduplicar, contagens e somas saem multiplicadas (era a origem dos valores
# errados do Jornal de Turno) e o Top 10 de duração repetia o mesmo incidente.
_PRED_KEYS = {
    "previsao_d1":         ["Data"],
    "previsao_d7":         ["Data"],
    "previsao_turno":      ["Data", "Turno"],
    "previsao_sla":        ["Numero_Incidente"],
    "previsao_duracao":    ["Numero_Incidente"],
    "clusters_incidentes": ["Numero_Incidente"],
    "cluster_nlp":         ["numero_incidente"],
}


def _dedup_prediction(df: pd.DataFrame, logical_name: str) -> pd.DataFrame:
    """Garante uma linha por chave natural, mantendo a última gravada."""
    if df is None or df.empty:
        return df
    out = df.drop_duplicates()
    wanted = _PRED_KEYS.get(logical_name) or []
    norm = {_norm_key(c): c for c in out.columns}
    subset = [norm[_norm_key(k)] for k in wanted if _norm_key(k) in norm]
    if subset:
        out = out.drop_duplicates(subset=subset, keep="last")
    return out.reset_index(drop=True)


def load_prediction_table(logical_name: str) -> pd.DataFrame:
    """Carrega uma tabela preditiva/cluster do BigQuery, já deduplicada.

    Devolve DataFrame vazio se a tabela estiver indisponível — nunca dado
    sintético.
    """
    try:
        return _dedup_prediction(load_bq_table(logical_name), logical_name)
    except Exception as e:
        st.info(f"Tabela '{logical_name}' indisponível no BigQuery no momento. ({e})")
        return pd.DataFrame()
