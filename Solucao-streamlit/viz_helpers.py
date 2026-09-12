"""
Camada de visualização do Predict Ops.

Reúne:
  * Data operacional de referência (09/12/2025) e formatação pt-BR.
  * Resolução tolerante de colunas (schemas do BigQuery variam em caixa/acento).
  * Construtores de gráficos modernos e interativos (rosca, ranking, treemap,
    heatmap, radar, scatter, histograma, gauge, forecast com faixa de confiança).
  * Helpers de interação: slicers globais (cross-filter), seleção clicável nos
    gráficos (drill/cross-filter), tabela analítica com busca + coloração de risco
    e botões de exportação (CSV + PNG nativo da modebar).

Os gráficos legados (dynamic_chart, headline_metric, find_*) foram mantidos
para compatibilidade.
"""
from __future__ import annotations

import io
import unicodedata

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from theme import (chip,
    NAVY, NAVY_LIGHT, RED, RED_DARK, TEXT, TEXT_MUTED, BORDER, CARD,
    CHART_SEQUENCE, CHART_SCALE_NAVY, CHART_SCALE_RED, CHART_SCALE_RISK,
    CHART_SCALE_LOAD, RISK_COLORS, RISK_GREEN, RISK_YELLOW, RISK_ORANGE,
    RISK_RED, STATUS_COLORS, PLOTLY_FONT, CHART_CONFIG,
)

# ============================================================================
# Data operacional de referência
# ============================================================================
REF_DATE = pd.Timestamp("2025-12-09")
REF_DATE_STR = "09/12/2025"

# ============================================================================
# Formatação
# ============================================================================
def br(n, casas: int = 0, sufixo: str = "") -> str:
    """Formata número no padrão pt-BR (milhar com ponto, decimal com vírgula)."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "—"
    try:
        s = f"{float(n):,.{casas}f}"
    except (TypeError, ValueError):
        return str(n)
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{s}{sufixo}"


# ============================================================================
# Normalização e resolução de colunas
# ============================================================================
def _norm(s) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _key(s) -> str:
    """Chave de comparação de coluna: sem acento, caixa, espaço, _ ou símbolos."""
    n = _norm(s)
    return "".join(ch for ch in n if ch.isalnum())


def pick_col(df: pd.DataFrame, *names, contains: bool = False):
    """Nome real da 1a coluna que casa (tolerante a acento/caixa/espaço/underscore)."""
    if df is None or df.empty:
        return None
    key_map = {_key(c): c for c in df.columns}
    for name in names:
        k = _key(name)
        if k in key_map:
            return key_map[k]
    if contains:
        for name in names:
            k = _key(name)
            for kc, real in key_map.items():
                if k and k in kc:
                    return real
    return None


# ============================================================================
# Prioridade e turno
# ============================================================================
_PRIO_MAP = {
    "1": "P1", "2": "P2", "3": "P3", "4": "P4", "5": "P5",
    "critica": "P1", "alta": "P2", "media": "P3",
    "baixa": "P4", "muito baixa": "P5",
}
PRIO_ORDER = ["P1", "P2", "P3", "P4", "P5"]
# Prioridade como nível: P1 vermelho → P4/P5 verde (mesma leitura de semáforo das telas).
PRIO_COLORS = {"P1": RISK_RED, "P2": RISK_ORANGE, "P3": RISK_YELLOW, "P4": RISK_GREEN, "P5": "#8FD3A8"}


def prio_short(value) -> str:
    """Converte 'Prioridade' bruta ('2 - Alta', 'P3', 3, 'Critica') em P1..P5."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    raw = str(value).strip()
    head = _norm(raw.split("-")[0])
    if head in _PRIO_MAP:
        return _PRIO_MAP[head]
    n = _norm(raw)
    for k, v in _PRIO_MAP.items():
        if k and k in n:
            return v
    return raw


def add_prio_short(df: pd.DataFrame, col: str = "Prioridade") -> pd.DataFrame:
    if col in df.columns:
        df = df.copy()
        df["_P"] = df[col].apply(prio_short)
    return df


TURNOS4 = ["Madrugada (00h-06h)", "Manhã (06h-12h)", "Tarde (12h-18h)", "Noite (18h-00h)"]
TURNO_HOURS = {TURNOS4[0]: (0, 6), TURNOS4[1]: (6, 12), TURNOS4[2]: (12, 18), TURNOS4[3]: (18, 24)}


def turno_from_hour(hora) -> str:
    if pd.isna(hora):
        return "Sem horário"
    h = int(hora)
    if h < 6:
        return TURNOS4[0]
    if h < 12:
        return TURNOS4[1]
    if h < 18:
        return TURNOS4[2]
    return TURNOS4[3]


# ============================================================================
# Risco
# ============================================================================
def risco_faixa(pct) -> str:
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return "Baixo"
    p = float(pct)
    if p <= 1:
        p *= 100
    if p >= 90:
        return "Crítico"
    if p >= 75:
        return "Alto"
    if p >= 60:
        return "Médio"
    return "Baixo"


def risco_cor(pct) -> str:
    return RISK_COLORS[risco_faixa(pct)]


def cor_nivel(valor, amarelo: float, vermelho: float) -> str:
    """Semáforo por limiar absoluto: < amarelo verde, < vermelho amarelo, senão vermelho."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return RISK_GREEN
    if np.isnan(v) or v < amarelo:
        return RISK_GREEN
    return RISK_YELLOW if v < vermelho else RISK_RED


def cores_relativas(counts: pd.Series, amarelo: float = 1 / 3,
                    vermelho: float = 2 / 3) -> dict:
    """{categoria: cor} pela fração do maior valor — maior incidência em vermelho.

    Para rankings de volume/esforço, onde não existe limiar absoluto: o topo fica
    vermelho, o meio amarelo e a cauda verde.
    """
    if counts is None or len(counts) == 0:
        return {}
    topo = float(pd.to_numeric(counts, errors="coerce").max() or 0)
    if topo <= 0:
        return {k: RISK_GREEN for k in counts.index}
    return {k: cor_nivel(float(v) / topo, amarelo, vermelho) for k, v in counts.items()}


def as_pct(series: pd.Series) -> pd.Series:
    """Garante escala 0-100 para probabilidades.

    Tolera o que o BigQuery pode devolver em colunas de probabilidade: número
    puro (0-1 ou 0-100), texto com sufixo `%` e decimal com vírgula. Sem isso, um
    `to_numeric` direto zeraria a coluna inteira para NaN e os gráficos de risco
    saíam vazios.
    """
    if series is None or len(series) == 0:
        return pd.Series(dtype="float64")
    s = pd.to_numeric(series, errors="coerce")
    if s.isna().all():
        txt = (series.astype(str)
               .str.replace("%", "", regex=False)
               .str.replace(r"\s", "", regex=True)
               .str.replace(".", "", regex=False)      # separador de milhar pt-BR
               .str.replace(",", ".", regex=False))
        s = pd.to_numeric(txt, errors="coerce")
    if s.dropna().empty:
        return s
    if s.dropna().le(1.0).mean() > 0.9:
        s = s * 100
    return s


# ============================================================================
# Estilo comum das figuras
# ============================================================================
# ============================================================================
# Filtragem por data de referência (09/12/2025) e casamento de turno
# ============================================================================
def to_dt(series: pd.Series) -> pd.Series:
    """Converte para datetime de forma tolerante (aceita DATE do BigQuery, str, etc.)."""
    return pd.to_datetime(series, errors="coerce")


def ref_slice(df: pd.DataFrame, *date_names, ref: pd.Timestamp = REF_DATE,
              fallback_full: bool = False) -> pd.DataFrame:
    """Recorta o DataFrame na data de referência (default 09/12/2025).

    Resolve a coluna de data via pick_col (tolerante a acento/caixa/tipo). Se não
    houver coluna de data, devolve o df inteiro. Por padrão devolve o recorte da
    data (mesmo que vazio); com fallback_full=True devolve o df completo caso o
    recorte fique vazio.
    """
    if df is None or df.empty:
        return df
    names = date_names or ("Data", "data", "dia", "date", "ds", "dt", "periodo", "ref")
    dcol = pick_col(df, *names, contains=True)
    if not dcol:
        return df
    out = df.copy()
    out[dcol] = to_dt(out[dcol])
    sliced = out[out[dcol].dt.date == ref.date()]
    if sliced.empty and fallback_full:
        return out
    return sliced


def turno_canon(value) -> str | None:
    """Normaliza um rótulo de turno para um dos TURNOS4 canônicos."""
    n = _norm(value)
    if "madrug" in n:
        return TURNOS4[0]
    if "manh" in n:
        return TURNOS4[1]
    if "tarde" in n:
        return TURNOS4[2]
    if "noite" in n or "notur" in n:
        return TURNOS4[3]
    return None


def turno_table(prev_turno: pd.DataFrame) -> pd.DataFrame:
    """Normaliza `previsao_turno` (BigQuery) em uma linha por (data, turno).

    Colunas de saída: `_data` (datetime.date), `_turno` (canônico), `_previsto`,
    `_real`.

    Por que existe: a tabela `predictops_gold.previsao_turno` contém a mesma
    previsão gravada mais de uma vez (cargas repetidas em WRITE_APPEND). Quem
    somava as linhas do dia obtinha valores multiplicados — era exatamente o que
    o Jornal de Turno mostrava (2.321 no lugar de 211, 4.290 no lugar de 390:
    11 cópias da mesma linha). Aqui a chave (data, turno) é única, então o card
    lê o valor previsto pelo modelo e não um múltiplo dele.
    """
    empty = pd.DataFrame(columns=["_data", "_turno", "_previsto", "_real"])
    if prev_turno is None or prev_turno.empty:
        return empty

    dcol = pick_col(prev_turno, "Data", "data", "dia", "date", contains=True)
    tcol = pick_col(prev_turno, "Turno", "turno")
    pcol = pick_col(prev_turno, "Incidentes_Previstos", "previsto", contains=True)
    rcol = pick_col(prev_turno, "Incidentes_Reais", "real", contains=True)
    if not (dcol and tcol and pcol):
        return empty

    out = pd.DataFrame({
        "_data": to_dt(prev_turno[dcol]).dt.date,
        "_turno": prev_turno[tcol].apply(turno_canon),
        "_previsto": pd.to_numeric(prev_turno[pcol], errors="coerce"),
        "_real": (pd.to_numeric(prev_turno[rcol], errors="coerce")
                  if rcol else np.nan),
    })
    out = out.dropna(subset=["_data", "_turno"])

    # 1 linha por (data, turno). Cópias idênticas somem no drop_duplicates; se
    # ainda restar mais de uma versão da mesma chave (re-treino do modelo),
    # fica a última gravada — nunca a soma.
    out = (out.drop_duplicates()
              .drop_duplicates(subset=["_data", "_turno"], keep="last")
              .sort_values(["_data", "_turno"])
              .reset_index(drop=True))
    return out


# ============================================================================
# Duração de resolução e MTTR
# ============================================================================
# Fatores aceitos para inferir a unidade da coluna 'Duração' (segundos por unidade).
_DUR_FACTORS = {"s": 1.0, "min": 60.0, "h": 3600.0}


def duration_unit_factor(raw: pd.Series, delta_s: pd.Series) -> float:
    """Segundos por unidade da coluna 'Duração', inferidos do próprio dado.

    Compara a coluna com o delta real (Resolvido − Aberto) e escolhe entre
    segundos, minutos e horas. Na base LW a coluna vem em SEGUNDOS.
    """
    ok = raw.notna() & delta_s.notna() & (raw > 0) & (delta_s > 0)
    if ok.sum() < 20:
        return 1.0
    ratio = float((delta_s[ok] / raw[ok]).median())
    return min(_DUR_FACTORS.values(), key=lambda f: abs(np.log(ratio / f)))


def duration_hours(df: pd.DataFrame, dur_col: str = "Duração",
                   open_col: str = "Aberto", res_col: str = "Resolvido") -> pd.Series:
    """Tempo de resolução em HORAS.

    Prioriza o delta real (Resolvido − Aberto) e usa a coluna 'Duração' apenas
    onde o delta não existe, convertendo pela unidade inferida.

    Bug corrigido: o painel dividia 'Duração' por 60 tratando-a como minutos,
    mas ela está em segundos — o MTTR saía 60x maior que o real.
    """
    idx = df.index
    delta = pd.Series(np.nan, index=idx, dtype="float64")
    if open_col in df.columns and res_col in df.columns:
        delta = (pd.to_datetime(df[res_col], errors="coerce")
                 - pd.to_datetime(df[open_col], errors="coerce")).dt.total_seconds()
    raw = (pd.to_numeric(df[dur_col], errors="coerce") if dur_col in df.columns
           else pd.Series(np.nan, index=idx, dtype="float64"))
    secs = delta.where(delta.notna(), raw * duration_unit_factor(raw, delta))
    return secs / 3600.0


def resolved_base(df: pd.DataFrame, encerrados, max_h: float = 720.0,
                  res_col: str = "Resolvido") -> pd.DataFrame:
    """Incidentes efetivamente resolvidos, com `_dur_h` (horas) e `_res` (timestamp).

    Descarta registros sem data de resolução, com duração não positiva ou acima
    de `max_h` (resíduos de reabertura/registro parado, que distorcem a média).
    """
    if df is None or df.empty:
        return df.assign(_dur_h=pd.Series(dtype=float), _res=pd.Series(dtype="datetime64[ns]"))
    out = df.copy()
    if "Status" in out.columns and encerrados:
        out = out[out["Status"].isin(encerrados)]
    # Reaproveita as colunas já calculadas em data_prep quando existirem — evita
    # refazer o cálculo de duração sobre a base inteira a cada rerun.
    if "_dur_h" not in out.columns:
        out["_dur_h"] = duration_hours(out)
    if "_res" not in out.columns:
        out["_res"] = (pd.to_datetime(out[res_col], errors="coerce")
                       if res_col in out.columns else pd.NaT)
    out = out[out["_res"].notna() & out["_dur_h"].notna() & (out["_dur_h"] > 0)]
    out.attrs["descartados_outlier"] = int((out["_dur_h"] > max_h).sum())
    return out[out["_dur_h"] <= max_h]


def mttr_stats(base: pd.DataFrame, inicio: pd.Timestamp, fim: pd.Timestamp) -> dict:
    """MTTR das resoluções ocorridas em [inicio, fim).

    A janela é ancorada em `Resolvido` (quando o incidente foi fechado) e não em
    `Aberto` — MTTR mede o tempo de reparo concluído no período.
    Devolve média (o MTTR propriamente dito), mediana, p90 e n.
    """
    vazio = dict(n=0, mean=None, p50=None, p90=None)
    if base is None or base.empty:
        return vazio
    s = base[(base["_res"] >= inicio) & (base["_res"] < fim)]["_dur_h"]
    if s.empty:
        return vazio
    return dict(n=int(s.size), mean=float(s.mean()),
                p50=float(s.median()), p90=float(s.quantile(0.90)))


def dur_to_hours(valor, unidade: str = "s"):
    """Converte uma duração dos modelos (`previsao_duracao`) para horas."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    return float(valor) * _DUR_FACTORS.get(unidade, 1.0) / 3600.0


def fmt_hours(horas, casas: int = 1) -> str:
    """Formata horas em pt-BR, caindo para minutos quando for menos de 1 hora."""
    if horas is None or (isinstance(horas, float) and np.isnan(horas)):
        return "—"
    h = float(horas)
    if h < 1:
        return br(h * 60, 0, " min")
    return br(h, casas, " h")


# ============================================================================
# previsao_sla — normalização e enriquecimento
# ============================================================================
def sla_frame(prev_sla: pd.DataFrame, df_inc: pd.DataFrame | None = None) -> pd.DataFrame:
    """Normaliza `previsao_sla` em colunas estáveis para todos os gráficos de risco.

    Saída: `_num`, `_pct`, `_faixa`, `_produto`, `_grupo`, `_prio`, `_categoria`.

    Motivo: os rankings "Top produtos com maior risco" e "Equipes com maior risco
    de violação" agrupavam direto pelas colunas `Produto` / `grupo_designado` da
    própria `previsao_sla`. Quando o modelo grava essas dimensões vazias (ou o
    BigQuery devolve a probabilidade como texto), o groupby não retorna nada e o
    gráfico renderiza sem barras. Aqui a dimensão que estiver faltando é
    recuperada da tabela `incidentes` pelo número do incidente, então o ranking
    sempre tem por onde agrupar.
    """
    cols = ["_num", "_pct", "_faixa", "_produto", "_grupo", "_prio", "_categoria",
            "_dt", "_turno"]
    if prev_sla is None or prev_sla.empty:
        return pd.DataFrame(columns=cols)

    scol = pick_col(prev_sla, "Probabilidade_Violacao_%", "Probabilidade_Violacao",
                    "probabilidade violacao", contains=True)
    if not scol:
        return pd.DataFrame(columns=cols)

    ncol = pick_col(prev_sla, "Numero_Incidente", "Numero", "numero incidente", contains=True)
    out = pd.DataFrame(index=prev_sla.index)
    out["_num"] = prev_sla[ncol].astype(str).str.strip() if ncol else pd.NA
    out["_pct"] = as_pct(prev_sla[scol])
    out["_produto"] = _clean_dim(prev_sla, "Produto", "produto")
    out["_grupo"] = _clean_dim(prev_sla, "grupo_designado", "Grupo designado", "grupo")
    out["_prio"] = _clean_dim(prev_sla, "Prioridade", "prioridade")
    out["_categoria"] = _clean_dim(prev_sla, "Categoria", "categoria")
    out["_dt"] = pd.NaT

    # Completa as dimensões vazias a partir da base de incidentes.
    if df_inc is not None and not df_inc.empty and ncol:
        icol = pick_col(df_inc, "Número", "Numero", "Numero_Incidente", contains=True)
        if icol:
            src = df_inc.copy()
            src["_k"] = src[icol].astype(str).str.strip()
            src = src.drop_duplicates(subset=["_k"]).set_index("_k")
            for destino, origem in [("_produto", "Produto"), ("_grupo", "Grupo designado"),
                                    ("_prio", "Prioridade"), ("_categoria", "Categoria")]:
                if origem not in src.columns:
                    continue
                trazido = out["_num"].map(src[origem])
                out[destino] = out[destino].fillna(trazido) if destino in out else trazido
            if "Aberto" in src.columns:
                out["_dt"] = pd.to_datetime(out["_num"].map(src["Aberto"]), errors="coerce")

    out["_turno"] = out["_dt"].dt.hour.apply(
        lambda h: turno_from_hour(h) if pd.notna(h) else None)
    if "_prio" in out:
        out["_prio"] = out["_prio"].apply(lambda v: prio_short(v) if pd.notna(v) else v)
    out["_faixa"] = out["_pct"].apply(risco_faixa)
    return out[cols]


def _clean_dim(df: pd.DataFrame, *names) -> pd.Series:
    """Lê uma coluna categórica tratando vazio/placeholder como ausente."""
    col = pick_col(df, *names)
    if not col:
        return pd.Series(pd.NA, index=df.index, dtype="object")
    s = df[col].astype("object").where(df[col].notna())
    s = s.astype(str).str.strip()
    vazios = {"", "nan", "none", "<na>", "null", "sem_produto", "sem produto",
              "sem_grupo", "nao informado", "não informado", "-"}
    return s.where(~s.str.lower().isin(vazios), other=pd.NA)


def rank_dim(frame: pd.DataFrame, dim: str, valor: str = "_pct",
             agg: str = "mean", top: int = 10) -> pd.Series:
    """Ranking de uma dimensão do `sla_frame`, ignorando chaves nulas."""
    if frame is None or frame.empty or dim not in frame.columns or valor not in frame.columns:
        return pd.Series(dtype="float64")
    d = frame[frame[dim].notna() & frame[valor].notna()]
    if d.empty:
        return pd.Series(dtype="float64")
    return d.groupby(dim)[valor].agg(agg).sort_values(ascending=False).head(top)


# ============================================================================
# NLP — temas emergentes a partir de cluster_nlp
# ============================================================================
_STOP = {
    "a", "o", "os", "as", "de", "da", "do", "das", "dos", "em", "no", "na", "nos",
    "nas", "para", "por", "com", "sem", "um", "uma", "e", "ou", "que", "se", "ao",
    "the", "of", "on", "in", "to", "for", "is", "at", "and", "or", "by", "with",
    "problem", "alert", "alerta", "incidente", "incident", "check", "error", "erro",
    "sem", "nao", "não", "null", "nan", "none",
}


def _tokenize(textos: pd.Series) -> list:
    """Lista de conjuntos de tokens úteis por documento."""
    if textos is None or textos.empty:
        return []
    séries = (textos.dropna().astype(str).str.lower()
              .str.replace(r"[^a-zà-ÿ0-9 ]", " ", regex=True)
              .str.split())
    return [{t for t in doc if len(t) >= 3 and t not in _STOP and not t.isdigit()}
            for doc in séries]


def top_terms(textos: pd.Series, n: int = 4) -> list:
    """Termos mais frequentes de um conjunto de descrições."""
    cont = {}
    for doc in _tokenize(textos):
        for t in doc:
            cont[t] = cont.get(t, 0) + 1
    return [t for t, _ in sorted(cont.items(), key=lambda kv: -kv[1])[:n]]


def _distinctive_terms(docs_cluster: list, freq_global: dict, n_global: int,
                       n: int = 3) -> list:
    """Termos que *caracterizam* o cluster, não os que aparecem em todo lugar.

    Frequência relativa dentro do cluster menos a frequência relativa global: um
    termo onipresente (ex.: "monitoring") tem lift ~0 e não vira rótulo, então
    clusters diferentes recebem nomes diferentes.
    """
    if not docs_cluster:
        return []
    n_c = len(docs_cluster)
    local = {}
    for doc in docs_cluster:
        for t in doc:
            local[t] = local.get(t, 0) + 1
    lift = {t: (c / n_c) - (freq_global.get(t, 0) / max(n_global, 1))
            for t, c in local.items() if c >= max(2, 0.05 * n_c)}
    escolhidos = [t for t, _ in sorted(lift.items(), key=lambda kv: -kv[1])[:n]]
    return escolhidos or [t for t, _ in sorted(local.items(), key=lambda kv: -kv[1])[:n]]


def nlp_themes(cluster_nlp: pd.DataFrame, df_inc: pd.DataFrame | None = None,
               ref: pd.Timestamp = REF_DATE) -> pd.DataFrame:
    """Temas do `cluster_nlp` com rótulo, volume e tendência.

    Colunas: `tema` (termos que caracterizam o cluster), `cluster`, `volume`,
    `no_dia`, `media_dia_hist`, `tendencia_%` (dia de referência vs média diária
    anterior). A data vem do join com `incidentes` pelo número do incidente — é o
    que permite dizer quais temas estão *emergindo*, e não só quais são grandes.
    """
    vazio = pd.DataFrame(columns=["tema", "cluster", "volume", "no_dia",
                                  "media_dia_hist", "tendencia_%"])
    if cluster_nlp is None or cluster_nlp.empty:
        return vazio
    ccol = pick_col(cluster_nlp, "cluster", "Cluster")
    dcol = pick_col(cluster_nlp, "descricao_original", "descricao", contains=True)
    ncol = pick_col(cluster_nlp, "numero_incidente", "Numero_Incidente", contains=True)
    if not ccol:
        return vazio

    d = cluster_nlp.copy()
    d["_c"] = d[ccol].astype(str)

    # Data de abertura via incidentes (cluster_nlp não tem data própria).
    d["_dt"] = pd.NaT
    if ncol and df_inc is not None and not df_inc.empty:
        icol = pick_col(df_inc, "Número", "Numero", contains=True)
        if icol and "Aberto" in df_inc.columns:
            mapa = (df_inc.assign(_k=df_inc[icol].astype(str).str.strip())
                          .drop_duplicates(subset=["_k"]).set_index("_k")["Aberto"])
            d["_dt"] = pd.to_datetime(d[ncol].astype(str).str.strip().map(mapa), errors="coerce")

    freq_global, n_global = {}, 0
    docs_por_cluster = {}
    if dcol:
        for cl, g in d.groupby("_c"):
            docs = _tokenize(g[dcol])
            docs_por_cluster[cl] = docs
            n_global += len(docs)
            for doc in docs:
                for t in doc:
                    freq_global[t] = freq_global.get(t, 0) + 1

    linhas = []
    for cl, g in d.groupby("_c"):
        termos = _distinctive_terms(docs_por_cluster.get(cl, []), freq_global, n_global)
        tema = " · ".join(termos) if termos else f"Cluster {cl}"
        no_dia = int((g["_dt"].dt.date == ref.date()).sum()) if g["_dt"].notna().any() else 0
        ant = g[g["_dt"] < ref]
        media = float(ant.groupby(ant["_dt"].dt.date).size().mean()) if not ant.empty else np.nan
        tend = ((no_dia - media) / media * 100) if (media and media > 0) else np.nan
        linhas.append(dict(tema=tema, cluster=cl, volume=int(len(g)), no_dia=no_dia,
                           media_dia_hist=media, **{"tendencia_%": tend}))

    out = pd.DataFrame(linhas).sort_values("volume", ascending=False).reset_index(drop=True)
    # Rótulos precisam ser únicos para o treemap não fundir dois clusters.
    dup = out["tema"].duplicated(keep=False)
    out.loc[dup, "tema"] = out.loc[dup, "tema"] + " (c" + out.loc[dup, "cluster"].astype(str) + ")"
    return out


def _folga(valores, fracao: float = 0.16):
    """Teto do eixo com espaço para o rótulo que fica fora da barra."""
    vals = [float(v) for v in valores if v is not None and not pd.isna(v)]
    if not vals:
        return None
    lo, hi = min(min(vals), 0.0), max(vals)
    if hi <= lo:
        return None
    return [lo, hi + (hi - lo) * fracao]


def _folga_x(fig: go.Figure, valores, fracao: float = 0.16) -> None:
    faixa = _folga(valores, fracao)
    if faixa:
        fig.update_xaxes(range=faixa)


def _folga_y(fig: go.Figure, valores, fracao: float = 0.16) -> None:
    faixa = _folga(valores, fracao)
    if faixa:
        fig.update_yaxes(range=faixa)


def style_fig(fig: go.Figure, height: int = 340, legend: bool = True,
              legend_top: bool = False) -> go.Figure:
    """Acabamento comum das figuras: tipografia, respiro, grade discreta e hover.

    Só aparência — nenhum dado é alterado aqui.
    """
    has_title = bool(getattr(fig.layout.title, "text", None))
    fig.update_layout(
        font=PLOTLY_FONT,
        height=height,
        margin=dict(t=44 if (legend and legend_top) else (36 if has_title else 16),
                    b=16, l=10, r=26),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="rgba(16,24,40,.10)",
                        font=dict(family=PLOTLY_FONT["family"], size=12, color=TEXT),
                        align="left"),
        hoverdistance=24,
        showlegend=legend,
        colorway=CHART_SEQUENCE,
        separators=",.",
        bargap=0.28,
        bargroupgap=0.08,
    )
    # Só formata o título quando ele existe. Passar `title=dict(font=...)` sem
    # `text` faz o Plotly.js desenhar a string "undefined" no topo do gráfico.
    if has_title:
        fig.update_layout(title=dict(font=dict(size=14, color=NAVY), x=0, xanchor="left"))
    else:
        # `title` some por completo do layout. Um objeto de título sem `text`
        # (mesmo vazio) é o que fazia o Plotly.js escrever "undefined" no topo
        # do gráfico.
        fig.layout.title = None
    if legend and legend_top:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.04,
                                      xanchor="left", x=0, title=None,
                                      font=dict(size=11.5, color=TEXT_MUTED),
                                      itemsizing="constant", bgcolor="rgba(0,0,0,0)"))
    elif legend:
        fig.update_layout(legend=dict(font=dict(size=11.5, color=TEXT_MUTED),
                                      title=None, bgcolor="rgba(0,0,0,0)"))
    eixo = dict(zeroline=False, linecolor="rgba(0,0,0,0)", ticks="outside",
                ticklen=4, tickcolor="rgba(0,0,0,0)", automargin=True,
                tickfont=dict(size=11.5, color=TEXT_MUTED),
                title_font=dict(size=11.5, color=TEXT_MUTED))
    fig.update_xaxes(showgrid=False, **eixo)
    fig.update_yaxes(showgrid=True, gridcolor="#EDEFF3", griddash="dot", **eixo)
    return fig


# ============================================================================
# Construtores de gráficos
# ============================================================================
def donut(counts: pd.Series, colors: dict | None = None, height: int = 300,
          center: str | None = None) -> go.Figure:
    counts = counts[counts > 0]
    labels = counts.index.astype(str).tolist()
    values = counts.values.tolist()
    seq = [colors.get(l, RED) for l in labels] if colors else CHART_SEQUENCE
    total = float(sum(values)) or 1.0

    # Fatia muito fina não comporta rótulo legível: o texto sai (o valor continua
    # no hover e na legenda). Antes o Plotly espremia o número dentro do arco.
    rotulos = [f"{v / total * 100:,.1f}%".replace(".", ",") if v / total >= 0.05 else ""
               for v in values]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.68, sort=False,
        marker=dict(colors=seq, line=dict(color="#FFFFFF", width=2.5)),
        text=rotulos, textinfo="text", textposition="inside",
        textfont=dict(color="#FFFFFF", size=12, family=PLOTLY_FONT["family"]),
        insidetextorientation="horizontal",
        # Reserva a faixa da direita para a legenda — sem isso o último rótulo
        # ("Crítico") era cortado pela borda do cartão.
        domain=dict(x=[0.0, 0.70], y=[0.02, 0.98]),
        hovertemplate="<b>%{label}</b><br>%{value:,} incidentes<br>%{percent}<extra></extra>",
    ))
    if center:
        fig.add_annotation(text=f"<b>{center}</b>", showarrow=False, x=0.35, y=0.5,
                           xref="paper", yref="paper",
                           font=dict(size=13, color=TEXT_MUTED,
                                     family=PLOTLY_FONT["family"]))
    fig = style_fig(fig, height=height, legend=True)
    fig.update_layout(
        margin=dict(t=16, b=16, l=10, r=10),
        legend=dict(orientation="v", x=0.74, xanchor="left", y=0.5, yanchor="middle",
                    title=None, itemsizing="constant", font=dict(size=12)))
    return fig


def ranking_hbar(labels, values, height: int = 340, risk_pct=None,
                 scale=None, value_suffix: str = "", title: str = "") -> go.Figure:
    d = pd.DataFrame({"cat": [str(x) for x in labels], "val": list(values)})
    if risk_pct is not None and len(list(risk_pct)) == len(d):
        d["risk"] = list(risk_pct)
        d = d.sort_values("val", ascending=True)
        cores = [risco_cor(v) for v in d["risk"]]
        fig = go.Figure(go.Bar(
            x=d["val"], y=d["cat"], orientation="h", marker=dict(color=cores, cornerradius=4),
            text=[br(v, 1, value_suffix) for v in d["val"]],
            textposition="outside", cliponaxis=False,
            textfont=dict(size=11.5, color=TEXT),
            hovertemplate="<b>%{y}</b><br>%{x:.1f}" + value_suffix + "<extra></extra>",
        ))
    else:
        d = d.sort_values("val", ascending=True)
        fig = px.bar(d, x="val", y="cat", orientation="h", color="val",
                     color_continuous_scale=scale or CHART_SCALE_NAVY,
                     text=[br(v, 0, value_suffix) for v in d["val"]])
        fig.update_traces(textposition="outside", cliponaxis=False,
                          textfont=dict(size=11.5, color=TEXT),
                          marker=dict(cornerradius=4),
                          hovertemplate="<b>%{y}</b><br>%{x:,}" + value_suffix + "<extra></extra>")
        fig.update_coloraxes(showscale=False)
    fig.update_layout(title=title, xaxis_title=None, yaxis_title=None)
    fig = style_fig(fig, height=height, legend=False)
    fig.update_yaxes(showgrid=False)
    _folga_x(fig, d["val"])
    return fig


def bar_vertical(labels, values, height: int = 320, scale=None, order_desc: bool = True) -> go.Figure:
    d = pd.DataFrame({"cat": [str(x) for x in labels], "val": list(values)})
    if order_desc:
        d = d.sort_values("val", ascending=False)
    fig = px.bar(d, x="cat", y="val", color="val",
                 color_continuous_scale=scale or CHART_SCALE_RED,
                 text=[br(v) for v in d["val"]])
    fig.update_traces(textposition="outside",
                      hovertemplate="<b>%{x}</b><br>%{y:,} incidentes<extra></extra>")
    fig.update_coloraxes(showscale=False)
    fig.update_traces(cliponaxis=False, textfont=dict(size=11.5, color=TEXT),
                      marker=dict(cornerradius=4))
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    fig = style_fig(fig, height=height, legend=False)
    _folga_y(fig, d["val"])
    return fig


def grouped_bar(categorias, series: dict, height: int = 320, colors: dict | None = None) -> go.Figure:
    fig = go.Figure()
    palette = list(CHART_SEQUENCE)
    for i, (nome, vals) in enumerate(series.items()):
        cor = (colors or {}).get(nome, palette[i % len(palette)])
        fig.add_bar(name=nome, x=list(categorias), y=list(vals), marker_color=cor,
                    hovertemplate="<b>%{x}</b><br>" + nome + ": %{y:,}<extra></extra>")
    fig.update_layout(barmode="group", xaxis_title=None, yaxis_title=None)
    return style_fig(fig, height=height, legend=True, legend_top=True)


def stacked_bar(df: pd.DataFrame, x: str, color: str, height: int = 340,
                colors: dict | None = None) -> go.Figure:
    d = df.groupby([x, color]).size().reset_index(name="Volume")
    fig = px.bar(d, x=x, y="Volume", color=color, barmode="stack",
                 color_discrete_map=colors or {}, color_discrete_sequence=CHART_SEQUENCE)
    fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,}<extra></extra>")
    fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title=None)
    return style_fig(fig, height=height, legend=True, legend_top=True)


def treemap(labels, parents, values, colors_val=None, scale=None,
            height: int = 360, title: str = "") -> go.Figure:
    marker = dict(line=dict(color="#FFFFFF", width=2))
    if colors_val is not None:
        marker["colors"] = list(colors_val)
        marker["colorscale"] = scale or CHART_SCALE_RISK
    else:
        marker["colorscale"] = scale or CHART_SCALE_NAVY
    fig = go.Figure(go.Treemap(
        labels=[str(l) for l in labels],
        parents=[str(p) if p is not None else "" for p in parents],
        values=list(values), marker=marker,
        textinfo="label+value", tiling=dict(pad=4),
        textfont=dict(family=PLOTLY_FONT["family"], size=12),
        hovertemplate="<b>%{label}</b><br>%{value:,}<extra></extra>",
    ))
    fig.update_layout(title=title)
    return style_fig(fig, height=height, legend=False)


def heatmap(pivot: pd.DataFrame, scale=None, height: int = 360, title: str = "",
            value_fmt: str = "%{z:,}") -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=[str(c) for c in pivot.columns], y=[str(i) for i in pivot.index],
        colorscale=scale or CHART_SCALE_LOAD, text=pivot.values, texttemplate=value_fmt,
        textfont=dict(size=11, color=TEXT),
        hovertemplate="<b>%{y}</b> · %{x}<br>%{z:,}<extra></extra>",
        xgap=4, ygap=4,
        colorbar=dict(thickness=8, outlinewidth=0, len=.8, ticks="",
                      tickfont=dict(size=10, color=TEXT_MUTED)),
    ))
    fig.update_layout(title=title, xaxis_title=None, yaxis_title=None)
    fig = style_fig(fig, height=height, legend=False)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    fig.update_xaxes(side="top")
    return fig


def radar(categorias, series: dict, height: int = 360, colors=None) -> go.Figure:
    fig = go.Figure()
    palette = colors or [RED, NAVY_LIGHT]
    cats = list(categorias) + [categorias[0]]
    for i, (nome, vals) in enumerate(series.items()):
        v = list(vals) + [vals[0]]
        cor = palette[i % len(palette)]
        fig.add_trace(go.Scatterpolar(
            r=v, theta=cats, name=nome, fill="toself", line=dict(color=cor, width=2),
            opacity=0.85, hovertemplate="<b>%{theta}</b><br>" + nome + ": %{r:.0f}<extra></extra>",
        ))
    fig.update_layout(polar=dict(
        radialaxis=dict(visible=True, range=[0, 100], gridcolor="#E6E9EE",
                        tickfont=dict(size=10, color=TEXT_MUTED)),
        angularaxis=dict(gridcolor="#E6E9EE"), bgcolor="rgba(0,0,0,0)",
    ))
    return style_fig(fig, height=height, legend=True, legend_top=True)


def scatter_risk(df: pd.DataFrame, x: str, y: str, text: str,
                 size: str | None = None, height: int = 380) -> go.Figure:
    d = df.copy()
    faixa = d[y].apply(risco_faixa)
    fig = go.Figure()
    sizeref = (2.0 * float(d[size].max()) / (55 ** 2)) if (size and d[size].max()) else None
    for f in ["Baixo", "Médio", "Alto", "Crítico"]:
        sub = d[faixa == f]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub[x], y=sub[y], mode="markers+text" if len(sub) <= 12 else "markers",
            name=f, text=sub[text], textposition="top center",
            textfont=dict(size=10, color=TEXT_MUTED),
            marker=dict(size=(sub[size] if size else 15),
                        sizemode="area" if size else "diameter", sizeref=sizeref,
                        color=RISK_COLORS[f], line=dict(color="#FFFFFF", width=1), opacity=0.9),
            hovertemplate="<b>%{text}</b><br>" + x + ": %{x:,}<br>" + y + ": %{y:.1f}%<extra></extra>",
        ))
    fig.update_layout(xaxis_title=x, yaxis_title=y)
    return style_fig(fig, height=height, legend=True, legend_top=True)


def histogram(series: pd.Series, nbins: int = 20, height: int = 320, faixas_75_90: bool = True) -> go.Figure:
    s = pd.to_numeric(series, errors="coerce").dropna()
    fig = go.Figure(go.Histogram(
        x=s, nbinsx=nbins, marker=dict(color=NAVY_LIGHT, line=dict(color="#FFFFFF", width=1)),
        hovertemplate="Faixa: %{x}<br>%{y} incidentes<extra></extra>",
    ))
    if faixas_75_90:
        fig.add_vline(x=75, line=dict(color=RISK_ORANGE, dash="dash", width=1.5),
                      annotation_text="75%", annotation_position="top")
        fig.add_vline(x=90, line=dict(color=RISK_RED, dash="dash", width=1.5),
                      annotation_text="90%", annotation_position="top")
    fig.update_layout(xaxis_title="Probabilidade de violação (%)", yaxis_title="Incidentes")
    return style_fig(fig, height=height, legend=False)


def gauge(value: float, target: float = 95.0, height: int = 300, suffix: str = "%") -> go.Figure:
    value = float(value) if value is not None else 0.0
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=value,
        number={"suffix": suffix, "font": {"size": 40, "color": NAVY_LIGHT}},
        delta={"reference": target, "increasing": {"color": RISK_GREEN},
               "decreasing": {"color": RISK_RED}, "suffix": suffix},
        gauge={"axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": BORDER},
               "bar": {"color": NAVY_LIGHT, "thickness": 0.28}, "bgcolor": "rgba(0,0,0,0)",
               "borderwidth": 0,
               "steps": [{"range": [0, 85], "color": "#FBE3E9"},
                         {"range": [85, 92], "color": "#FCEFD6"},
                         {"range": [92, 100], "color": "#E4F3E9"}],
               "threshold": {"line": {"color": RED, "width": 4}, "thickness": 0.85, "value": target}},
    ))
    return style_fig(fig, height=height, legend=False)


def forecast_line(df: pd.DataFrame, date_col: str, real_col: str, prev_col: str,
                  height: int = 360, band_pct: float = 0.12) -> go.Figure:
    d = df[[date_col, real_col, prev_col]].copy()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d = d.dropna(subset=[date_col]).sort_values(date_col)
    prev = pd.to_numeric(d[prev_col], errors="coerce")
    real = pd.to_numeric(d[real_col], errors="coerce")
    upper, lower = prev * (1 + band_pct), prev * (1 - band_pct)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d[date_col], y=upper, mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d[date_col], y=lower, mode="lines", fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(31,39,51,0.10)", name="Faixa de confiança", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d[date_col], y=prev, mode="lines+markers", name="Previsto",
                             line=dict(color=NAVY_LIGHT, width=2, dash="dot"), marker=dict(size=6),
                             hovertemplate="%{x|%d/%m}<br>Previsto: %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=d[date_col], y=real, mode="lines+markers", name="Realizado",
                             line=dict(color=RED, width=2.5), marker=dict(size=7),
                             hovertemplate="%{x|%d/%m}<br>Realizado: %{y:,.0f}<extra></extra>"))
    fig.update_layout(xaxis_title=None, yaxis_title="Incidentes")
    fig = style_fig(fig, height=height, legend=True, legend_top=True)
    fig.update_xaxes(showgrid=False)
    return fig


# ============================================================================
# Interação: seleção clicável (cross-filter / drill) e slicers globais
# ============================================================================
def cor_desvio(desvio, base, tolerancia: float = 0.25) -> str:
    """Nível do desvio contra o baseline: verde / amarelo / vermelho.

    Verde: no normal ou abaixo. Amarelo: acima, mas dentro da tolerância
    (até `tolerancia` × baseline, ou menos de 1 incidente a mais). Vermelho:
    acima da tolerância — inclui categoria que não existia no baseline.
    """
    try:
        dv, b = float(desvio), float(base)
    except (TypeError, ValueError):
        return RISK_YELLOW
    if dv <= 0:
        return RISK_GREEN
    if dv < 1 or (b > 0 and dv <= tolerancia * b):
        return RISK_YELLOW
    return RISK_RED


def divergent_bar(labels, valores, baseline, height: int = 340,
                  sufixo: str = "", nome_base: str = "média histórica",
                  tolerancia: float | None = None) -> go.Figure:
    """Barras de desvio: quanto cada categoria está acima/abaixo de um baseline.

    Verde = abaixo do esperado, vermelho = acima. Com `tolerancia`, o desvio
    positivo pequeno fica amarelo (ver `cor_desvio`). Serve para a passagem de
    turno responder "quem está fora do normal agora", que uma barra de volume
    não diz.
    """
    d = pd.DataFrame({"cat": [str(x) for x in labels], "val": list(valores),
                      "base": list(baseline)})
    d["desvio"] = d["val"] - d["base"]
    d = d.sort_values("desvio")
    if tolerancia is None:
        cores = [RISK_RED if v > 0 else RISK_GREEN for v in d["desvio"]]
    else:
        cores = [cor_desvio(v, b, tolerancia) for v, b in zip(d["desvio"], d["base"])]
    fig = go.Figure(go.Bar(
        x=d["desvio"], y=d["cat"], orientation="h", marker_color=cores,
        text=[("+" if v > 0 else "") + br(v, 0, sufixo) for v in d["desvio"]],
        textposition="outside", cliponaxis=False,
        textfont=dict(size=11.5, color=TEXT),
        customdata=np.stack([d["val"], d["base"]], axis=-1),
        hovertemplate=("<b>%{y}</b><br>agora: %{customdata[0]:,.0f}"
                       f"<br>{nome_base}: " + "%{customdata[1]:,.1f}<extra></extra>"),
    ))
    fig.add_vline(x=0, line=dict(color=NAVY_LIGHT, width=1))
    fig.update_layout(xaxis_title=f"desvio vs {nome_base}", yaxis_title=None)
    fig = style_fig(fig, height=height, legend=False)
    fig.update_yaxes(showgrid=False)
    return fig


def hour_bar(serie: pd.Series, height: int = 300, destaque=None) -> go.Figure:
    """Volume por hora do dia, com destaque opcional numa faixa (turno)."""
    horas = list(serie.index)
    cores = [RED if (destaque and destaque[0] <= h < destaque[1]) else "#C9CED6" for h in horas]
    fig = go.Figure(go.Bar(
        x=[f"{h:02d}h" for h in horas], y=list(serie.values),
        marker=dict(color=cores, cornerradius=3),
        hovertemplate="%{x}<br>%{y:,} incidentes<extra></extra>"))
    fig.update_layout(xaxis_title=None, yaxis_title="Incidentes")
    return style_fig(fig, height=height, legend=False)


def simple_hbar(counts: pd.Series, height: int = 300, cor: str = RED,
                sufixo: str = "", casas: int = 0, cor_fn=None,
                inverter: bool = False, cores: dict | None = None) -> go.Figure:
    """Barra horizontal de leitura direta (valor escrito na barra).

    Versão para o perfil gestor: sem escala de cor contínua, sem colorbar e sem
    interação — só o ranking e o número. `cor_fn(valor) -> cor` pinta cada barra
    por nível (ex.: `risco_cor`); sem ela, todas usam `cor`. `inverter=True` põe
    o MENOR valor no topo (rankings em que menor é pior, ex.: tempo entre falhas).
    """
    d = pd.DataFrame({"cat": [str(x) for x in counts.index],
                      "val": list(counts.values)}).sort_values("val", ascending=not inverter)
    if cores:
        cores_barra = [cores.get(c, cor) for c in d["cat"]]
    else:
        cores_barra = [cor_fn(v) for v in d["val"]] if cor_fn else cor
    fig = go.Figure(go.Bar(
        x=d["val"], y=d["cat"], orientation="h",
        marker=dict(color=cores_barra, cornerradius=4),
        text=[br(v, casas, sufixo) for v in d["val"]],
        textposition="outside", cliponaxis=False,
        textfont=dict(size=11.5, color=TEXT),
        hovertemplate="<b>%{y}</b><br>%{x:,.1f}" + sufixo + "<extra></extra>"))
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    fig = style_fig(fig, height=height, legend=False)
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(visible=False)
    _folga_x(fig, d["val"])
    return fig


def semaforo(valor, meta: float, height: int = 220, sufixo: str = "%",
             rotulo: str = "") -> go.Figure:
    """Indicador grande com seta de comparação contra a meta (leitura executiva)."""
    v = float(valor) if valor is not None and not (isinstance(valor, float) and np.isnan(valor)) else 0.0
    cor = RISK_GREEN if v >= meta else (RISK_YELLOW if v >= meta * 0.85 else RISK_RED)
    fig = go.Figure(go.Indicator(
        mode="number+delta", value=v,
        number=dict(suffix=sufixo, font=dict(size=46, color=cor)),
        delta=dict(reference=meta, suffix=sufixo, relative=False,
                   increasing=dict(color=RISK_GREEN), decreasing=dict(color=RISK_RED)),
        title=dict(text=rotulo or f"meta {br(meta,0,sufixo)}",
                   font=dict(size=13, color=TEXT_MUTED)),
    ))
    return style_fig(fig, height=height, legend=False)


def stacked_hbar(pivot: pd.DataFrame, colors: dict | None = None,
                 height: int = 320, sufixo: str = "", rotulos: bool = False,
                 casas: int = 0) -> go.Figure:
    """Barras horizontais empilhadas (categoria × série).

    A primeira linha do `pivot` fica embaixo (convenção do Plotly). `rotulos`
    escreve o valor dentro de cada segmento — útil em composição 100%.
    """
    fig = go.Figure()
    for serie in pivot.columns:
        vals = pivot[serie]
        fig.add_trace(go.Bar(
            y=[str(i) for i in pivot.index], x=vals, orientation="h",
            name=str(serie),
            marker_color=(colors or {}).get(serie, None),
            text=([br(v, casas, sufixo) if v >= (8 if sufixo == "%" else 1) else ""
                   for v in vals] if rotulos else None),
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=11, color="#FFFFFF"),
            hovertemplate="<b>%{y}</b><br>" + str(serie) + ": %{x:,.1f}" + sufixo
                          + "<extra></extra>"))
    fig.update_layout(barmode="stack", xaxis_title=None, yaxis_title=None)
    fig = style_fig(fig, height=height, legend=True, legend_top=True)
    fig.update_yaxes(showgrid=False)
    return fig


def pareto(labels, values, height: int = 360, sufixo: str = "",
           corte: float = 80.0, niveis: bool = False) -> go.Figure:
    """Barras ordenadas + curva de % acumulado, com linha no corte (80/20).

    Responde "quantos itens concentram a maior parte da carga" — a pergunta que
    um ranking simples não responde.
    """
    d = (pd.DataFrame({"cat": [str(x) for x in labels], "val": list(values)})
         .sort_values("val", ascending=False))
    total = d["val"].sum()
    d["acum"] = d["val"].cumsum() / total * 100 if total else 0

    fig = go.Figure()
    cor_barras = (list(cores_relativas(d.set_index("cat")["val"]).values()) if niveis
                  else NAVY_LIGHT)
    fig.add_trace(go.Bar(x=d["cat"], y=d["val"], name="Incidentes", marker_color=cor_barras,
                         hovertemplate="<b>%{x}</b><br>%{y:,}" + sufixo + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=d["cat"], y=d["acum"], name="% acumulado", yaxis="y2",
                             mode="lines+markers", line=dict(color=RED, width=2.5),
                             hovertemplate="<b>%{x}</b><br>%{y:.1f}% acumulado<extra></extra>"))
    fig.update_layout(
        yaxis=dict(title=None),
        yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%",
                    showgrid=False, tickfont=dict(color=RED)),
        xaxis_title=None)
    fig = style_fig(fig, height=height, legend=True, legend_top=True)
    fig.add_hline(y=corte, yref="y2", line=dict(color=TEXT_MUTED, dash="dot", width=1),
                  annotation_text=f"{corte:.0f}%", annotation_position="right")
    return fig


def cumulative_flow(rotulos, chegadas, resolucoes, height: int = 340) -> go.Figure:
    """Chegadas x resoluções acumuladas ao longo do dia.

    A distância vertical entre as duas curvas é a fila pendente naquele momento —
    é o que mostra se a operação acompanhou o ritmo de entrada ou ficou para trás.
    """
    ch = np.cumsum(list(chegadas))
    rs = np.cumsum(list(resolucoes))
    x = [str(r) for r in rotulos]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=ch, name="Abertos (acum.)", mode="lines",
                             line=dict(color=RED, width=2.5), fill="tozeroy",
                             fillcolor="rgba(240,8,74,0.10)",
                             hovertemplate="%{x}<br>%{y:,} abertos<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=rs, name="Resolvidos (acum.)", mode="lines",
                             line=dict(color=RISK_GREEN, width=2.5), fill="tozeroy",
                             fillcolor="rgba(18,161,80,0.12)",
                             hovertemplate="%{x}<br>%{y:,} resolvidos<extra></extra>"))
    fig.update_layout(xaxis_title=None, yaxis_title="Acumulado no dia")
    return style_fig(fig, height=height, legend=True, legend_top=True)


def box_by_group(df: pd.DataFrame, col_grupo: str, col_valor: str, ordem=None,
                 height: int = 360, log: bool = True, colors: dict | None = None,
                 titulo_y: str = "") -> go.Figure:
    """Distribuição (caixa) de um valor por grupo — mediana, quartis e cauda.

    Escala logarítmica por padrão: os tempos de resolução variam de segundos a
    dias, e numa escala linear tudo colapsa contra o eixo.
    """
    d = df[[col_grupo, col_valor]].dropna()
    d = d[d[col_valor] > 0]
    grupos = [g for g in (ordem or sorted(d[col_grupo].unique())) if g in set(d[col_grupo])]
    fig = go.Figure()
    for g in grupos:
        vals = d[d[col_grupo] == g][col_valor]
        fig.add_trace(go.Box(y=vals, name=str(g), boxpoints=False,
                             marker_color=(colors or {}).get(g, NAVY_LIGHT),
                             line=dict(width=1.5),
                             hovertemplate="<b>" + str(g) + "</b><br>%{y:.2f}<extra></extra>"))
    fig.update_layout(xaxis_title=None, yaxis_title=titulo_y or col_valor)
    fig = style_fig(fig, height=height, legend=False)
    if log:
        fig.update_yaxes(type="log")
    return fig


def bar_com_meta(counts: pd.Series, meta: float, height: int = 320, cor: str = NAVY_LIGHT,
                 sufixo: str = "", casas: int = 1, rotulo_meta: str = "meta") -> go.Figure:
    """Barras verticais com linha de meta — verde até 80% da meta, amarelo até a meta,
    vermelho acima."""
    d = pd.DataFrame({"cat": [str(i) for i in counts.index], "val": list(counts.values)})
    cores = [RISK_GREEN if v <= 0.8 * meta else (RISK_YELLOW if v <= meta else RISK_RED)
             for v in d["val"]]
    fig = go.Figure(go.Bar(
        x=d["cat"], y=d["val"], marker=dict(color=cores, cornerradius=4),
        text=[br(v, casas, sufixo) for v in d["val"]], textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y:,.1f}" + sufixo + "<extra></extra>"))
    fig.update_traces(cliponaxis=False, textfont=dict(size=11.5, color=TEXT))
    fig.add_hline(y=meta, line=dict(color=TEXT_MUTED, dash="dash", width=1.5),
                  annotation_text=f"{rotulo_meta} {br(meta, 0, sufixo)}")
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    fig = style_fig(fig, height=height, legend=False)
    _folga_y(fig, list(d["val"]) + [meta])
    return fig


def area_stacked(rotulos, series: dict, height: int = 340, colors: dict | None = None,
                 titulo_y: str = "") -> go.Figure:
    """Área empilhada para composição ao longo do tempo."""
    x = [str(r) for r in rotulos]
    fig = go.Figure()
    for i, (nome, vals) in enumerate(series.items()):
        fig.add_trace(go.Scatter(
            x=x, y=list(vals), name=str(nome), mode="lines", stackgroup="um",
            line=dict(width=0.5, color=(colors or {}).get(nome, CHART_SEQUENCE[i % len(CHART_SEQUENCE)])),
            fillcolor=(colors or {}).get(nome, CHART_SEQUENCE[i % len(CHART_SEQUENCE)]),
            hovertemplate="%{x}<br>" + str(nome) + ": %{y:,}<extra></extra>"))
    fig.update_layout(xaxis_title=None, yaxis_title=titulo_y)
    return style_fig(fig, height=height, legend=True, legend_top=True)


def render_ranking(counts: pd.Series, key: str, motivo_vazio: str,
                   risco: bool = False, simples: bool = False, **kw) -> None:
    """Desenha um ranking — ou explica por que ele está vazio.

    Um gráfico sem barras não distingue "sem dado" de "erro de coluna"; aqui a
    tela diz qual dos dois é.
    """
    if counts is None or len(counts) == 0 or pd.isna(pd.Series(counts.values)).all():
        st.info(motivo_vazio)
        return
    if simples:
        fig = simple_hbar(counts, **kw)
    elif risco:
        fig = ranking_hbar(counts.index, counts.values, risk_pct=counts.values, **kw)
    else:
        fig = ranking_hbar(counts.index, counts.values, **kw)
    plot(fig, key=key)


def selectable(fig: go.Figure, key: str, field: str = "label") -> list:
    try:
        event = st.plotly_chart(fig, use_container_width=True, key=key,
                                on_select="rerun", selection_mode="points", config=CHART_CONFIG)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        return []
    points = []
    try:
        points = event["selection"]["points"]
    except (TypeError, KeyError):
        sel = getattr(event, "selection", None)
        if isinstance(sel, dict):
            points = sel.get("points", [])
        else:
            points = getattr(sel, "points", None) or []
    out = []
    for p in points or []:
        val = p.get(field) if isinstance(p, dict) else None
        if val is not None:
            out.append(val)
    return list(dict.fromkeys(out))


def plot(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG, key=key)


def global_slicers(df: pd.DataFrame, page_key: str, dims) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    cols = st.columns(len(dims))
    out = df
    for i, (label, col) in enumerate(dims):
        with cols[i]:
            if col not in df.columns:
                st.multiselect(label, [], disabled=True, key=f"{page_key}_{col}_off")
                continue
            opts = sorted([o for o in df[col].dropna().unique().tolist()], key=lambda x: str(x))
            sel = st.multiselect(label, opts, default=[], key=f"{page_key}_{col}", placeholder="Todos")
            if sel:
                out = out[out[col].isin(sel)]
    return out


def cross_filter_chip(page_key: str, label: str) -> None:
    state_key = f"{page_key}_xfilter"
    active = st.session_state.get(state_key)
    if active:
        c1, c2 = st.columns([4, 1])
        with c1:
            chip(f"Cross-filter ativo: <b>{label} = {active}</b>")
        if c2.button("Limpar seleção", key=f"{page_key}_clear", use_container_width=True):
            st.session_state[state_key] = None
            st.rerun()


# ============================================================================
# Tabela analítica crítica (busca + coloração de risco + export)
# ============================================================================
# ============================================================================
# Tabela analítica crítica (coloração de risco + export)
# ============================================================================
def critical_table(df: pd.DataFrame, prob_col: str, key: str,
                   height: int = 380, search_cols=None) -> pd.DataFrame:
    if df is None or df.empty:
        st.info("Sem registros para exibir.")
        return df

    d = df.copy()

    def _bg(v):
        try:
            p = float(v)
        except (TypeError, ValueError):
            return ""
        if p <= 1:
            p *= 100
        if p >= 90:
            return f"background-color: {RISK_RED}; color: #fff; font-weight:600;"
        if p >= 75:
            return f"background-color: {RISK_ORANGE}; color: #fff;"
        if p >= 60:
            return f"background-color: {RISK_YELLOW}; color: #1F2733;"
        return ""

    styler = d.style
    if prob_col in d.columns:
        # pandas >= 2.1 usa Styler.map; versões antigas usam applymap.
        _apply = getattr(styler, "map", None) or styler.applymap
        styler = _apply(_bg, subset=[prob_col]).format({prob_col: lambda v: br(v, 1, "%")})
    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)
    csv_download(d, "Exportar tabela (CSV)", f"{key}.csv", key=f"{key}_csv")
    return d


def csv_download(df: pd.DataFrame, label: str, filename: str, key: str | None = None) -> None:
    if df is None or df.empty:
        return
    buf = io.StringIO()
    df.to_csv(buf, index=False, sep=";")
    st.download_button(label, data=buf.getvalue().encode("utf-8-sig"),
                       file_name=filename, mime="text/csv", key=key)


# ============================================================================
# COMPATIBILIDADE — helpers legados
# ============================================================================
_DATE_HINTS = ("data", "date", "dia", "ds", "timestamp", "dt", "periodo", "mes", "ref")
_VALUE_HINTS = ("previsao", "prev", "forecast", "pred", "yhat", "valor", "value", "qtd",
                "quantidade", "qtde", "total", "incidentes", "volume", "count", "n_",
                "prob", "risco", "score", "duracao", "media", "taxa", "percent", "pct")
_CAT_HINTS = ("cluster", "grupo", "categoria", "produto", "turno", "equipe", "team",
              "prioridade", "status", "label", "classe", "tipo", "topico", "termo")


def find_datetime_col(df: pd.DataFrame):
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    for c in df.columns:
        if any(h in _norm(c) for h in _DATE_HINTS):
            try:
                if pd.to_datetime(df[c], errors="coerce").notna().mean() > 0.6:
                    return c
            except Exception:
                continue
    return None


def find_numeric_col(df: pd.DataFrame, exclude=()):
    num_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in exclude]
    if not num_cols:
        return None
    for c in num_cols:
        if any(h in _norm(c) for h in _VALUE_HINTS):
            return c
    return num_cols[0]


def find_categorical_col(df: pd.DataFrame, exclude=()):
    obj_cols = [c for c in df.columns if c not in exclude
                and not pd.api.types.is_numeric_dtype(df[c])
                and not pd.api.types.is_datetime64_any_dtype(df[c])]
    for c in obj_cols:
        if any(h in _norm(c) for h in _CAT_HINTS):
            return c
    for c in obj_cols:
        if 1 < df[c].nunique(dropna=True) <= 40:
            return c
    return obj_cols[0] if obj_cols else None


def dynamic_chart(df: pd.DataFrame, title: str = "", scale=None):
    if df is None or df.empty:
        return None
    scale = scale or CHART_SCALE_NAVY
    dt_col = find_datetime_col(df)
    num_col = find_numeric_col(df, exclude=(dt_col,) if dt_col else ())
    cat_col = find_categorical_col(df, exclude=(dt_col, num_col))
    if dt_col and num_col:
        d = df[[dt_col, num_col]].copy()
        d[dt_col] = pd.to_datetime(d[dt_col], errors="coerce")
        d = d.dropna(subset=[dt_col]).sort_values(dt_col)
        color = cat_col if (cat_col and df[cat_col].nunique() <= 8) else None
        if color:
            d[color] = df.loc[d.index, color]
        fig = px.line(d, x=dt_col, y=num_col, color=color, markers=True, title=title,
                      color_discrete_sequence=CHART_SEQUENCE)
        return style_fig(fig)
    if cat_col and num_col:
        d = df.groupby(cat_col, dropna=False)[num_col].sum().reset_index().sort_values(num_col, ascending=False).head(15)
        fig = px.bar(d, x=cat_col, y=num_col, color=num_col, title=title, color_continuous_scale=scale)
        return style_fig(fig, legend=False)
    if cat_col:
        d = df[cat_col].value_counts().head(15).reset_index()
        d.columns = [cat_col, "Quantidade"]
        fig = px.bar(d, x=cat_col, y="Quantidade", color="Quantidade", title=title, color_continuous_scale=scale)
        return style_fig(fig, legend=False)
    if num_col:
        fig = px.histogram(df, x=num_col, title=title, color_discrete_sequence=CHART_SEQUENCE)
        return style_fig(fig, legend=False)
    return None


def headline_metric(df: pd.DataFrame, kind: str = "sum"):
    if df is None or df.empty:
        return None
    num_col = find_numeric_col(df)
    if not num_col:
        return None
    series = pd.to_numeric(df[num_col], errors="coerce").dropna()
    if series.empty:
        return None
    return (float(series.mean()) if kind == "mean" else float(series.sum())), num_col


def render_table_expander(df: pd.DataFrame, label: str = "Ver dados da tabela (BigQuery)"):
    if df is not None and not df.empty:
        with st.expander(f"{label} — {len(df):,} linha(s)"):
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================================
# Gráficos de inteligência operacional
#
# Acrescentados para dar leitura acionável aos modos de falha (cluster NLP),
# aos regimes operacionais (cluster tabular) e à confiabilidade dos modelos.
# ============================================================================
def line_multi(rotulos, series: dict, destaques=None, height: int = 360,
               titulo_y: str = "") -> go.Figure:
    """Várias séries no tempo, com destaque para as que importam.

    Uma linha por tema em cinza claro esconde o sinal. Aqui as séries listadas
    em `destaques` ficam grossas e coloridas; o resto vira contexto de fundo.
    """
    destaques = set(destaques or [])
    fig = go.Figure()
    paleta = [RED, RISK_ORANGE, RISK_YELLOW, NAVY_LIGHT, RED_DARK, RISK_GREEN]
    i = 0
    for nome, valores in series.items():
        realce = nome in destaques or not destaques
        cor = paleta[i % len(paleta)] if realce else "#D3D8E0"
        if realce:
            i += 1
        fig.add_trace(go.Scatter(
            x=[str(r) for r in rotulos], y=list(valores), name=str(nome),
            mode="lines+markers" if realce else "lines",
            line=dict(color=cor, width=3 if realce else 1.2),
            marker=dict(size=6 if realce else 0),
            opacity=1.0 if realce else 0.55,
            hovertemplate="%{x}<br>" + str(nome) + ": %{y:,.0f}<extra></extra>",
        ))
    fig.update_layout(xaxis_title=None, yaxis_title=titulo_y)
    return style_fig(fig, height=height, legend=True, legend_top=True)


def bubble_matrix(df: pd.DataFrame, x: str, y: str, size: str, text: str,
                  height: int = 420, x_log: bool = True,
                  rotulo_x: str = "", rotulo_y: str = "", cores=None) -> go.Figure:
    """Matriz de decisão: volume × criticidade, com quadrantes pela mediana.

    Responde 'onde agir primeiro' melhor que um ranking de volume: o item mais
    frequente quase nunca é o mais crítico. `cores` (lista alinhada às linhas)
    substitui a cor por faixa de risco.
    """
    d = df.copy()
    cores = list(cores) if cores is not None else [risco_cor(v) for v in d[y]]
    ref = float(d[size].max()) or 1.0
    fig = go.Figure(go.Scatter(
        x=d[x], y=d[y], mode="markers+text", text=d[text],
        textposition="top center", textfont=dict(size=10.5, color=TEXT_MUTED),
        marker=dict(size=d[size], sizemode="area",
                    sizeref=2.0 * ref / (46 ** 2), sizemin=6,
                    color=cores, line=dict(color="#FFFFFF", width=1.5), opacity=.85),
        customdata=np.stack([d[size]], axis=-1),
        hovertemplate=("<b>%{text}</b><br>" + (rotulo_x or x) + ": %{x:,.0f}<br>"
                       + (rotulo_y or y) + ": %{y:.1f}%<extra></extra>"),
    ))
    fig.add_vline(x=float(d[x].median()), line=dict(color="#B9C0CC", dash="dash", width=1))
    fig.add_hline(y=float(d[y].median()), line=dict(color="#B9C0CC", dash="dash", width=1))
    fig.update_layout(xaxis_title=rotulo_x or x, yaxis_title=rotulo_y or y)
    fig = style_fig(fig, height=height, legend=False)
    if x_log:
        fig.update_xaxes(type="log")
    return fig


def calibration_chart(faixas, taxa_real, volume, height: int = 340) -> go.Figure:
    """Faixa de risco prevista × taxa real de violação observada.

    É o gráfico que responde 'dá para confiar na probabilidade que o modelo
    mostra?'. Se as barras sobem da esquerda para a direita, a ordenação do
    risco é útil mesmo que a probabilidade absoluta não seja perfeita.
    """
    d = pd.DataFrame({"faixa": [str(f) for f in faixas],
                      "real": list(taxa_real), "n": list(volume)})
    fig = go.Figure(go.Bar(
        x=d["faixa"], y=d["real"],
        marker=dict(color=[risco_cor(v) for v in d["real"]], cornerradius=4),
        text=[br(v, 1, "%") for v in d["real"]], textposition="outside",
        cliponaxis=False, textfont=dict(size=11.5, color=TEXT),
        customdata=np.stack([d["n"]], axis=-1),
        hovertemplate=("<b>%{x}</b><br>violação real: %{y:.1f}%"
                       "<br>incidentes na faixa: %{customdata[0]:,}<extra></extra>"),
    ))
    fig.update_layout(xaxis_title="faixa de probabilidade prevista",
                      yaxis_title="% que realmente violou")
    return style_fig(fig, height=height, legend=False)


def gain_curve(pct_fila, pct_capturado, height: int = 340) -> go.Figure:
    """Curva de ganho: revisando os X% mais arriscados, quantos % das violações
    a operação alcança. A diagonal é o resultado de revisar a fila em ordem
    aleatória — a distância entre as duas curvas é o valor do modelo."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0] + list(pct_fila), y=[0] + list(pct_capturado), mode="lines",
        name="com o modelo", line=dict(color=RED, width=3),
        hovertemplate="revisando %{x:.0f}% da fila<br>captura %{y:.0f}% das violações<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[0, 100], y=[0, 100], mode="lines", name="sem modelo (aleatório)",
        line=dict(color=NAVY_LIGHT, width=2, dash="dash"), hoverinfo="skip"))
    fig.update_layout(xaxis_title="% da fila revisada (do maior risco para o menor)",
                      yaxis_title="% das violações capturadas")
    return style_fig(fig, height=height, legend=True, legend_top=True)


def scatter_pred_real(real, previsto, height: int = 360, sufixo: str = " h",
                      max_pontos: int = 4000) -> go.Figure:
    """Previsto × real com a linha de acerto perfeito.

    Pontos acima da diagonal = modelo superestimou; abaixo = subestimou.
    """
    d = pd.DataFrame({"real": pd.to_numeric(real, errors="coerce"),
                      "prev": pd.to_numeric(previsto, errors="coerce")}).dropna()
    if len(d) > max_pontos:
        d = d.sample(max_pontos, random_state=42)
    limite = float(max(d["real"].max(), d["prev"].max())) if not d.empty else 1.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["real"], y=d["prev"], mode="markers", name="incidentes",
        marker=dict(size=6, color=RED, opacity=.35, line=dict(width=0)),
        hovertemplate="real: %{x:,.1f}" + sufixo + "<br>previsto: %{y:,.1f}" + sufixo + "<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[0, limite], y=[0, limite], mode="lines", name="acerto perfeito",
        line=dict(color=NAVY_LIGHT, width=2, dash="dash"), hoverinfo="skip"))
    fig.update_layout(xaxis_title="real" + sufixo, yaxis_title="previsto" + sufixo)
    return style_fig(fig, height=height, legend=True, legend_top=True)


def waterfall(labels, values, height: int = 360, sufixo: str = "") -> go.Figure:
    """Composição em cascata — de onde vem o volume e quanto é endereçável."""
    medidas = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=medidas,
        x=[str(l) for l in labels], y=list(values),
        text=[br(abs(v), 0, sufixo) for v in values],
        textposition="outside", cliponaxis=False,
        connector=dict(line=dict(color="#C9CED6", width=1)),
        increasing=dict(marker=dict(color=RISK_RED)),
        decreasing=dict(marker=dict(color=RISK_GREEN)),
        totals=dict(marker=dict(color=NAVY_LIGHT)),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    return style_fig(fig, height=height, legend=False)


def lollipop(counts: pd.Series, height: int = 340, cor: str = None,
             sufixo: str = "", casas: int = 0, cores: dict | None = None) -> go.Figure:
    """Ranking em pirulito — mesma leitura da barra, menos tinta na tela.

    Usado onde a comparação entre poucas categorias nomeadas importa mais que a
    área preenchida (o caso em que um treemap atrapalha em vez de ajudar).
    `cores` ({categoria: cor}) pinta cada ponto por nível; sem ele, todos usam `cor`.
    """
    cor = cor or RED
    d = counts.sort_values(ascending=True)
    y = [str(i) for i in d.index]
    cor_pontos = [(cores or {}).get(n, (cores or {}).get(i, cor))
                  for n, i in zip(y, d.index)] if cores else cor
    fig = go.Figure()
    for nome, valor in zip(y, d.values):
        fig.add_trace(go.Scatter(
            x=[0, valor], y=[nome, nome], mode="lines",
            line=dict(color="#D8DDE5", width=2), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=d.values, y=y, mode="markers+text", showlegend=False,
        marker=dict(size=13, color=cor_pontos, line=dict(color="#FFFFFF", width=1.5)),
        text=[br(v, casas, sufixo) for v in d.values], textposition="middle right",
        textfont=dict(size=11.5, color=TEXT),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f}" + sufixo + "<extra></extra>"))
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    fig = style_fig(fig, height=height, legend=False)
    fig.update_yaxes(showgrid=False)
    _folga_x(fig, list(d.values), 0.22)
    return fig


# ============================================================================
# Helpers adicionados para o Painel NOC (clusters, SRE e confiança dos modelos)
# ============================================================================
def cores_regime(nomes, pct_p2=None) -> dict:
    """{regime: cor} pelo tipo de trabalho — ruído verde, operação amarelo, cauda vermelho.

    Lê o nome do regime (`Cluster_Nome` / `cluster`). Se nenhum nome indicar o
    tipo, usa `pct_p2` ({regime: % alta prioridade}): maior vermelho, menor verde.
    """
    nomes = list(nomes)
    cores = {}
    for nome in nomes:
        n = str(nome).lower()
        if any(t in n for t in ("ruído", "ruido", "autom")):
            cores[nome] = RISK_GREEN
        elif any(t in n for t in ("crític", "critic", "cauda", "grave")):
            cores[nome] = RISK_RED
    if not cores and pct_p2 is not None and len(nomes) > 1:
        r = pd.Series(pct_p2).reindex(nomes).rank(method="first")
        return {k: (RISK_RED if v == r.max() else RISK_GREEN if v == r.min() else RISK_YELLOW)
                for k, v in r.items()}
    return {k: cores.get(k, RISK_YELLOW) for k in nomes}


def bar_niveis(labels, values, cores, height: int = 320, sufixo: str = "",
               casas: int = 1, linha=None, rotulo_linha: str = "",
               titulo_y: str = "", rotulos: bool = True) -> go.Figure:
    """Barras verticais com cor por nível já decidida e linha de referência opcional."""
    x = [str(l) for l in labels]
    vals = [float(v) if v is not None and not pd.isna(v) else 0.0 for v in values]
    fig = go.Figure(go.Bar(
        x=x, y=vals, marker=dict(color=list(cores), cornerradius=4),
        text=([br(v, casas, sufixo) for v in vals] if rotulos else None), textposition="outside",
        cliponaxis=False, textfont=dict(size=11, color=TEXT),
        hovertemplate="<b>%{x}</b><br>%{y:,.2f}" + sufixo + "<extra></extra>"))
    if linha is not None:
        fig.add_hline(y=linha, line=dict(color=TEXT_MUTED, dash="dash", width=1.5),
                      annotation_text=rotulo_linha, annotation_position="top left")
    fig.update_layout(xaxis_title=None, yaxis_title=titulo_y)
    fig = style_fig(fig, height=height, legend=False)
    _folga_y(fig, vals + ([linha] if linha is not None else []))
    return fig


def metricas_regressao(real, previsto) -> dict:
    """MAE, MAPE, R², viés e % de pontos dentro de ±10% — sobre pares válidos."""
    d = pd.DataFrame({"r": pd.to_numeric(pd.Series(list(real)), errors="coerce"),
                      "p": pd.to_numeric(pd.Series(list(previsto)), errors="coerce")}).dropna()
    if d.empty:
        return {}
    err = d["p"] - d["r"]
    rel = err.abs() / d["r"].where(d["r"] > 0)
    ss_tot = float(((d["r"] - d["r"].mean()) ** 2).sum())
    return dict(
        n=int(len(d)),
        mae=float(err.abs().mean()),
        mape=float(rel.mean() * 100) if rel.notna().any() else np.nan,
        r2=(1 - float((err ** 2).sum()) / ss_tot) if ss_tot > 0 else np.nan,
        vies=float(err.mean()),
        dentro10=float((rel <= 0.10).mean() * 100) if rel.notna().any() else np.nan,
    )


def auc_score(score, alvo) -> float:
    """Área sob a curva ROC pela estatística de Mann-Whitney (sem sklearn)."""
    d = pd.DataFrame({"s": pd.to_numeric(pd.Series(list(score)), errors="coerce"),
                      "y": pd.to_numeric(pd.Series(list(alvo)), errors="coerce")}).dropna()
    pos = d["y"] >= 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if not n1 or not n0:
        return np.nan
    r = d["s"].rank()
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def cartoes_semaforo(itens) -> None:
    """Cartões de veredito (verde/amarelo/vermelho) em grade.

    `itens`: sequência de dicts com `titulo`, `valor`, `metrica`, `cor`, `veredito`
    e `nota` opcional.
    """
    html = []
    for it in itens:
        html.append(
            f'<div style="flex:1 1 220px;background:#FFFFFF;border:1px solid #EAECF0;'
            f'border-left:5px solid {it["cor"]};border-radius:10px;padding:.8rem 1rem;">'
            f'<div style="font-size:.78rem;color:{TEXT_MUTED};font-weight:600;'
            f'text-transform:uppercase;letter-spacing:.03em">{it["titulo"]}</div>'
            f'<div style="font-size:1.55rem;font-weight:700;color:{TEXT};margin:.15rem 0">'
            f'{it["valor"]} <span style="font-size:.8rem;color:{TEXT_MUTED};font-weight:500">'
            f'{it["metrica"]}</span></div>'
            f'<div style="font-size:.85rem;font-weight:650;color:{it["cor"]}">{it["veredito"]}</div>'
            + (f'<div style="font-size:.76rem;color:{TEXT_MUTED};margin-top:.2rem">{it["nota"]}</div>'
               if it.get("nota") else "")
            + "</div>")
    st.markdown('<div style="display:flex;flex-wrap:wrap;gap:.75rem;margin:.3rem 0 .6rem">'
                + "".join(html) + "</div>", unsafe_allow_html=True)

