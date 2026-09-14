"""
Preparações derivadas, calculadas uma vez e reaproveitadas entre as telas.

Motivo: o Streamlit reexecuta o script inteiro a cada troca de tela, clique ou
filtro. Antes, cada execução refazia sobre as 122 mil linhas da base:

  * `Prioridade.apply(prio_short)` e `Aberto.dt.hour.apply(turno_from_hour)`
    — duas passadas linha a linha em Python;
  * `sla_frame()` — join da `previsao_sla` com a base de incidentes;
  * `nlp_themes()` — tokenização de todas as descrições do `cluster_nlp`;
  * `duration_hours()` — cálculo de duração dentro do `resolved_base`.

Nada disso depende da interação do usuário, então tudo passou a ser calculado
uma única vez e servido do cache. As funções não recebem DataFrame por
parâmetro de propósito: assim o Streamlit não precisa hashear a base inteira
para decidir se o cache vale.

O conteúdo dos dados é idêntico ao de antes — só o momento do cálculo mudou.
"""
import numpy as np
import pandas as pd
import streamlit as st

import viz_helpers as V
from bq_loader import load_incident_data, load_prediction_table

TTL = 1800  # mesma janela de atualização usada no carregamento do BigQuery


@st.cache_data(ttl=TTL, show_spinner=False)
def incidentes() -> pd.DataFrame:
    """Base de incidentes com as colunas derivadas usadas por todas as telas.

    Acrescenta `_P` (prioridade curta), `_Turno`/`_T` (turno de abertura),
    `_dur_h` (horas até a resolução) e `_res` (timestamp de resolução).
    """
    df = load_incident_data().copy()

    # Vetorizado: a prioridade tem meia dúzia de valores distintos, então o
    # mapeamento roda sobre os valores únicos e não sobre as 122 mil linhas.
    if "Prioridade" in df.columns:
        mapa = {v: V.prio_short(v) for v in df["Prioridade"].dropna().unique()}
        df["_P"] = df["Prioridade"].map(mapa).fillna("-")
    else:
        df["_P"] = "-"

    if "Aberto" in df.columns:
        h = pd.to_datetime(df["Aberto"], errors="coerce").dt.hour
        df["_T"] = pd.cut(h, bins=[-1, 5, 11, 17, 23], labels=V.TURNOS4).astype("object")
        df["_T"] = df["_T"].fillna("Sem horário")
    else:
        df["_T"] = "Sem horário"
    df["_Turno"] = df["_T"]  # alias usado pelo Painel NOC

    df["_dur_h"] = V.duration_hours(df)
    df["_res"] = (pd.to_datetime(df["Resolvido"], errors="coerce")
                  if "Resolvido" in df.columns else pd.NaT)
    return df


@st.cache_data(ttl=TTL, show_spinner=False)
def sla() -> pd.DataFrame:
    """`previsao_sla` normalizada e enriquecida (ver `viz_helpers.sla_frame`)."""
    return V.sla_frame(load_prediction_table("previsao_sla"), incidentes())


@st.cache_data(ttl=TTL, show_spinner=False)
def temas() -> pd.DataFrame:
    """Temas de `cluster_nlp` com rótulo, volume e tendência."""
    return V.nlp_themes(load_prediction_table("cluster_nlp"), incidentes(), V.REF_DATE)


# ============================================================================
# Inteligência de temas e regimes operacionais
#
# O cluster sozinho só diz "este incidente é do grupo 3". O valor aparece ao
# cruzar o grupo com a base: aí ele passa a dizer quanto custa, quão crítico é
# e se está crescendo.
# ============================================================================

# Nomes derivados das palavras dominantes de cada cluster de NLP. Rótulo
# numérico não se defende em tela executiva.
NOMES_TEMA_NLP = {
    0: "Serviços diversos (residual)",
    1: "Falta de swap",
    2: "Disco I/O sobrecarregado",
    3: "CPU alta / iowait",
    4: "Disco cheio (<20% livre)",
    5: "Erro no hypervisor",
    6: "Apache busy workers",
    7: "Indisponibilidade (ping)",
}

# Temas que representam saturação de recurso: não acontecem de repente, crescem
# até estourar. São os candidatos naturais a virar capacity planning preventivo
# em vez de incidente.
TEMAS_SATURACAO = {
    "Falta de swap", "Disco I/O sobrecarregado",
    "CPU alta / iowait", "Disco cheio (<20% livre)",
}


def _nome_tema(valor):
    try:
        return NOMES_TEMA_NLP.get(int(valor), f"Tema {valor}")
    except (TypeError, ValueError):
        return str(valor)


@st.cache_data(ttl=TTL, show_spinner=False)
def temas_base() -> pd.DataFrame:
    """`cluster_nlp` cruzado com `incidentes`, com o tema já nomeado."""
    nlp = load_prediction_table("cluster_nlp")
    inc = incidentes()
    if nlp is None or nlp.empty or inc.empty:
        return pd.DataFrame()

    ccol = V.pick_col(nlp, "cluster", "Cluster")
    ncol = V.pick_col(nlp, "numero_incidente", "Numero_Incidente", contains=True)
    icol = V.pick_col(inc, "Número", "Numero", contains=True)
    if not (ccol and ncol and icol):
        return pd.DataFrame()

    chave = nlp[[ncol, ccol]].copy()
    chave[ncol] = chave[ncol].astype(str).str.strip()
    base = inc.copy()
    base["_k"] = base[icol].astype(str).str.strip()

    d = base.merge(chave, left_on="_k", right_on=ncol, how="inner")
    d["_tema"] = d[ccol].map(_nome_tema)
    return d


def perfil_temas_de(d: pd.DataFrame, casas_horas: int = 0) -> pd.DataFrame:
    """Perfil operacional por tema de qualquer recorte que já tenha `_tema`.

    Mesma regra do perfil global, aplicável a um dia/turno: o Jornal de Turno
    passa só os incidentes do turno selecionado (ver `com_tema`).
    """
    if d is None or d.empty or "_tema" not in d.columns:
        return pd.DataFrame()

    d = d.copy()
    d["_P2"] = (d.get("Prioridade", pd.Series(index=d.index, dtype=object))
                == "2 - Alta").astype(int)
    if "tem_pai" in d.columns:
        d["_pai"] = pd.to_numeric(d["tem_pai"], errors="coerce").fillna(0)
    else:
        d["_pai"] = 0
    if "Entrou para KPI?" in d.columns:
        d["_kpi"] = (d["Entrou para KPI?"] == "SIM").astype(int)
    else:
        d["_kpi"] = 0
    if "_dur_h" not in d.columns:
        d["_dur_h"] = np.nan

    perfil = (d.groupby("_tema")
              .agg(incidentes=("_tema", "size"),
                   pct_P2=("_P2", lambda s: s.mean() * 100),
                   pct_com_pai=("_pai", lambda s: s.mean() * 100),
                   duracao_mediana_h=("_dur_h", "median"),
                   entram_kpi=("_kpi", "sum")))

    perfil["duracao_mediana_h"] = perfil["duracao_mediana_h"].fillna(0)
    perfil["horas_estimadas"] = (perfil["incidentes"] *
                                 perfil["duracao_mediana_h"]).round(casas_horas)
    perfil["saturacao"] = perfil.index.isin(TEMAS_SATURACAO)
    return perfil.sort_values("incidentes", ascending=False)


@st.cache_data(ttl=TTL, show_spinner=False)
def perfil_temas() -> pd.DataFrame:
    """Perfil operacional de cada tema: volume, criticidade, esforço, KPI.

    A duração usa mediana e não média — alguns chamados ficam parados semanas
    por motivo administrativo e distorceriam a média.
    """
    return perfil_temas_de(temas_base())


@st.cache_data(ttl=TTL, show_spinner=False)
def evolucao_temas(meses: int = 8) -> pd.DataFrame:
    """Volume mensal por tema — base do alerta de tema emergente."""
    d = temas_base()
    if d.empty or "Aberto" not in d.columns:
        return pd.DataFrame()
    d = d.copy()
    d["_mes"] = pd.to_datetime(d["Aberto"], errors="coerce").dt.to_period("M").astype(str)
    piv = (d.pivot_table(index="_mes", columns="_tema", values="_k", aggfunc="size")
           .fillna(0).astype(int).sort_index())
    return piv.tail(meses)


@st.cache_data(ttl=TTL, show_spinner=False)
def tendencia_temas(janela: int = 3) -> pd.DataFrame:
    """Último mês contra a média dos anteriores — quem está emergindo."""
    piv = evolucao_temas()
    if piv.empty or len(piv) < janela + 1:
        return pd.DataFrame()
    atual = piv.iloc[-1]
    referencia = piv.iloc[-(janela + 1):-1].mean()
    out = pd.DataFrame({"media_anterior": referencia.round(1), "mes_atual": atual})
    out["variacao_%"] = np.where(out["media_anterior"] > 0,
                                 (out["mes_atual"] / out["media_anterior"] - 1) * 100,
                                 np.nan)
    return out.sort_values("variacao_%", ascending=False)


@st.cache_data(ttl=TTL, show_spinner=False)
def evolucao_prioridade(dim: str, prioridades: tuple = ("P2", "P3"),
                        meses: int = 8, top: int = 6) -> pd.DataFrame:
    """Volume mensal de incidentes P2/P3 por `dim` (Produto ou Categoria).

    Mesma lógica de `evolucao_temas`, mas filtrando pela prioridade em vez de
    tema NLP — cobre o requisito de identificar tendência de P2/P3 sem
    precisar de um modelo novo.
    """
    df = incidentes()
    if df.empty or dim not in df.columns or "_P" not in df.columns:
        return pd.DataFrame()
    d = df[df["_P"].isin(prioridades) & df[dim].notna()].copy()
    if d.empty or "Aberto" not in d.columns:
        return pd.DataFrame()
    top_vals = d[dim].value_counts().head(top).index
    d = d[d[dim].isin(top_vals)]
    d["_mes"] = pd.to_datetime(d["Aberto"], errors="coerce").dt.to_period("M").astype(str)
    d["_cnt"] = 1
    piv = (d.pivot_table(index="_mes", columns=dim, values="_cnt", aggfunc="sum")
           .fillna(0).astype(int).sort_index())
    return piv.tail(meses)


@st.cache_data(ttl=TTL, show_spinner=False)
def tendencia_prioridade(dim: str, prioridades: tuple = ("P2", "P3"),
                         janela: int = 3) -> pd.DataFrame:
    """Último mês contra a média dos anteriores, para P2/P3 por `dim`."""
    piv = evolucao_prioridade(dim, prioridades)
    if piv.empty or len(piv) < janela + 1:
        return pd.DataFrame()
    atual = piv.iloc[-1]
    referencia = piv.iloc[-(janela + 1):-1].mean()
    out = pd.DataFrame({"media_anterior": referencia.round(1), "mes_atual": atual})
    out["variacao_%"] = np.where(out["media_anterior"] > 0,
                                 (out["mes_atual"] / out["media_anterior"] - 1) * 100,
                                 np.nan)
    return out.sort_values("variacao_%", ascending=False)


@st.cache_data(ttl=TTL, show_spinner=False)
def regimes_base() -> pd.DataFrame:
    """`clusters_incidentes` cruzado com `incidentes`, com o regime já nomeado."""
    cl = load_prediction_table("clusters_incidentes")
    inc = incidentes()
    if cl is None or cl.empty or inc.empty:
        return pd.DataFrame()

    ncol = V.pick_col(cl, "Numero_Incidente", "numero_incidente", contains=True)
    nome = V.pick_col(cl, "Cluster_Nome", "cluster_nome", contains=True)
    ccol = V.pick_col(cl, "Cluster", "cluster")
    icol = V.pick_col(inc, "Número", "Numero", contains=True)
    if not (ncol and icol and (nome or ccol)):
        return pd.DataFrame()

    chave = cl[[ncol] + ([nome] if nome else [ccol])].copy()
    chave[ncol] = chave[ncol].astype(str).str.strip()
    base = inc.copy()
    base["_k"] = base[icol].astype(str).str.strip()

    d = base.merge(chave, left_on="_k", right_on=ncol, how="inner")
    d["_regime"] = d[nome] if nome else ("Cluster " + d[ccol].astype(str))
    return d


def perfil_regimes(d: pd.DataFrame) -> pd.DataFrame:
    """Agregado por regime de qualquer recorte que já tenha `_regime`.

    Usado sem filtro pelo Painel Gerencial e recortado por dia/turno pelo
    Jornal de Turno (ver `com_regime`).
    """
    if d is None or d.empty or "_regime" not in d.columns:
        return pd.DataFrame()
    d = d.copy()
    d["_P2"] = (d.get("Prioridade", pd.Series(index=d.index, dtype=object))
                == "2 - Alta").astype(int)
    d["_manual"] = (d.get("Aberto por", pd.Series(index=d.index, dtype=object))
                    == "Manual").astype(int)
    if "_dur_h" not in d.columns:
        d["_dur_h"] = np.nan

    return (d.groupby("_regime")
            .agg(incidentes=("_regime", "size"),
                 pct_P2=("_P2", lambda s: s.mean() * 100),
                 pct_manual=("_manual", lambda s: s.mean() * 100),
                 duracao_mediana_h=("_dur_h", "median"))
            .sort_values("incidentes", ascending=False))


@st.cache_data(ttl=TTL, show_spinner=False)
def regimes() -> pd.DataFrame:
    """`clusters_incidentes` cruzado com a base — os três regimes operacionais.

    Diferente dos temas de NLP (que dizem *o que* quebrou), o regime diz *que
    tipo de trabalho* o incidente gera: ruído automático, operação ou cauda
    crítica.
    """
    return perfil_regimes(regimes_base())


# ============================================================================
# Recorte por dia/turno (Jornal de Turno)
#
# O Jornal não pode mostrar regime nem tema da base inteira: tudo ali precisa
# responder pelo dia e turno escolhidos. Em vez de copiar a base cruzada inteira
# a cada rerun, o cache guarda só o mapa número -> regime/tema, e o recorte já
# filtrado (com os slicers do operador) é anexado a ele na hora.
# ============================================================================
@st.cache_data(ttl=TTL, show_spinner=False)
def mapa_regimes() -> pd.DataFrame:
    """Número do incidente -> `_regime` (`clusters_incidentes`)."""
    cl = load_prediction_table("clusters_incidentes")
    if cl is None or cl.empty:
        return pd.DataFrame(columns=["_regime"])
    ncol = V.pick_col(cl, "Numero_Incidente", "numero_incidente", contains=True)
    nome = V.pick_col(cl, "Cluster_Nome", "cluster_nome", contains=True)
    ccol = V.pick_col(cl, "Cluster", "cluster")
    if not (ncol and (nome or ccol)):
        return pd.DataFrame(columns=["_regime"])
    m = pd.DataFrame({
        "_k": cl[ncol].astype(str).str.strip(),
        "_regime": (cl[nome].astype(str) if nome else "Cluster " + cl[ccol].astype(str)),
    })
    return m.drop_duplicates(subset=["_k"], keep="last").set_index("_k")


@st.cache_data(ttl=TTL, show_spinner=False)
def mapa_temas() -> pd.DataFrame:
    """Número do incidente -> `_tema` nomeado e `_cluster` (`cluster_nlp`)."""
    nlp = load_prediction_table("cluster_nlp")
    if nlp is None or nlp.empty:
        return pd.DataFrame(columns=["_tema", "_cluster"])
    ccol = V.pick_col(nlp, "cluster", "Cluster")
    ncol = V.pick_col(nlp, "numero_incidente", "Numero_Incidente", contains=True)
    if not (ccol and ncol):
        return pd.DataFrame(columns=["_tema", "_cluster"])
    m = pd.DataFrame({"_k": nlp[ncol].astype(str).str.strip(), "_cluster": nlp[ccol]})
    nomes = {v: _nome_tema(v) for v in m["_cluster"].dropna().unique()}
    m["_tema"] = m["_cluster"].map(nomes)
    return m.drop_duplicates(subset=["_k"], keep="last").set_index("_k")


def _anexar(frame: pd.DataFrame, mapa: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or mapa is None or mapa.empty:
        return pd.DataFrame(columns=list(getattr(frame, "columns", [])) + list(mapa.columns))
    icol = V.pick_col(frame, "Número", "Numero", contains=True)
    if not icol:
        return frame.iloc[0:0]
    out = frame.assign(_k=frame[icol].astype(str).str.strip())
    return out.join(mapa, on="_k", how="inner")


def com_regime(frame: pd.DataFrame) -> pd.DataFrame:
    """Recorte de incidentes (ex.: dia + turno) com a coluna `_regime`."""
    return _anexar(frame, mapa_regimes())


def com_tema(frame: pd.DataFrame) -> pd.DataFrame:
    """Recorte de incidentes (ex.: dia + turno) com `_tema` e `_cluster`."""
    return _anexar(frame, mapa_temas())


@st.cache_data(ttl=TTL, show_spinner=False)
def previsao_regime(horizonte: str = "D+1") -> pd.DataFrame:
    """Previsão decomposta por regime (`previsao_d1_por_cluster`).

    É o que transforma "1.200 incidentes amanhã" em três números com dono.
    """
    tabela = "previsao_d1_por_cluster" if horizonte == "D+1" else "previsao_d7_por_cluster"
    prev = load_prediction_table(tabela)
    if prev is None or prev.empty:
        return pd.DataFrame()

    d = prev.copy()
    dcol = V.pick_col(d, "data", "Data")
    if dcol:
        d[dcol] = pd.to_datetime(d[dcol], errors="coerce")
        d = d.rename(columns={dcol: "data"})
    for origem, destino in [("previsto", "previsto"), ("real", "real"),
                            ("cluster", "cluster"), ("origem", "origem")]:
        col = V.pick_col(d, origem, origem.capitalize())
        if col and col != destino:
            d = d.rename(columns={col: destino})
    return d


def previsao_cluster(horizonte: str = "D+1") -> pd.DataFrame:
    """`previsao_d1/d7_por_cluster` normalizada: data, cluster, previsto, real, origem.

    Uma linha por (data, cluster) — protege contra cargas repetidas em WRITE_APPEND.
    """
    d = previsao_regime(horizonte)
    vazio = pd.DataFrame(columns=["data", "cluster", "previsto", "real", "origem"])
    if d is None or d.empty or not {"data", "cluster", "previsto"} <= set(d.columns):
        return vazio
    d = d.copy()
    d["data"] = pd.to_datetime(d["data"], errors="coerce")
    d["cluster"] = d["cluster"].astype(str).str.strip()
    d["previsto"] = pd.to_numeric(d["previsto"], errors="coerce")
    d["real"] = pd.to_numeric(d["real"], errors="coerce") if "real" in d.columns else np.nan
    if "origem" not in d.columns:
        d["origem"] = np.where(d["real"].notna(), "backtest", "projecao")
    return (d.dropna(subset=["data"])
             .drop_duplicates(subset=["data", "cluster"], keep="last")
             .sort_values(["data", "cluster"]).reset_index(drop=True))


def metricas_cluster() -> pd.DataFrame:
    """`metricas_previsao_por_cluster` normalizada (MAPE sempre em %)."""
    met = load_prediction_table("metricas_previsao_por_cluster")
    cols = ["cluster", "horizonte", "escolhido", "MAE", "RMSE", "R2", "MAPE"]
    if met is None or met.empty:
        return pd.DataFrame(columns=cols)
    ccol = V.pick_col(met, "cluster", "Cluster")
    hcol = V.pick_col(met, "horizonte", "Horizonte")
    if not (ccol and hcol):
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame({"cluster": met[ccol].astype(str).str.strip(),
                        "horizonte": met[hcol].astype(str).str.strip()})
    ecol = V.pick_col(met, "escolhido", "modelo", contains=True)
    out["escolhido"] = met[ecol].astype(str) if ecol else "—"
    for nome in ["MAE", "RMSE", "R2", "MAPE"]:
        c = V.pick_col(met, nome)
        out[nome] = pd.to_numeric(met[c], errors="coerce") if c else np.nan
    if out["MAPE"].notna().any() and out["MAPE"].median() <= 1.5:
        out["MAPE"] = out["MAPE"] * 100   # veio como fração
    return out.drop_duplicates(subset=["cluster", "horizonte"], keep="last")


def tema_x_regime(tema_frame: pd.DataFrame):
    """% de cada tema NLP em cada regime operacional.

    Devolve (pivot %, cores). Colunas ordenadas cauda → operação → ruído e linhas
    do tema mais "ruído" para o menos. Sem `clusters_incidentes`, divide por
    intervenção humana (Status). Devolve (DataFrame vazio, {}) sem dados.
    """
    if tema_frame is None or tema_frame.empty or "_tema" not in tema_frame.columns:
        return pd.DataFrame(), {}
    tr = com_regime(tema_frame)
    if not tr.empty:
        pv = pd.crosstab(tr["_tema"], tr["_regime"], normalize="index") * 100
        cores = V.cores_regime(pv.columns)
        ordem = {V.RISK_RED: 0, V.RISK_YELLOW: 1, V.RISK_GREEN: 2}
        pv = pv[sorted(pv.columns, key=lambda c: ordem.get(cores[c], 3))]
        verdes = [c for c in pv.columns if cores[c] == V.RISK_GREEN]
        if verdes:
            pv = pv.loc[pv[verdes].sum(axis=1).sort_values(ascending=False).index]
        return pv.round(1), cores
    if "Status" not in tema_frame.columns:
        return pd.DataFrame(), {}
    tipo = np.where(tema_frame["Status"] == "Sem Intervenção", "Auto-resolvido", "Com intervenção")
    pv = pd.crosstab(tema_frame["_tema"], tipo, normalize="index") * 100
    if "Auto-resolvido" in pv.columns:
        pv = pv.sort_values("Auto-resolvido", ascending=False)
    return pv.round(1), {"Auto-resolvido": V.RISK_GREEN, "Com intervenção": V.RISK_RED}

