"""Painel NOC (Operacional) — monitoramento ancorado em 09/12/2025.

Abas:
* Visão do dia            — tudo recortado em 09/12 (inclusive o ritmo abertos × resolvidos).
* Demanda por tipo de trabalho — `clusters_incidentes` + `previsao_d1/d7_por_cluster`.
* Tipos de problema (NLP) — `cluster_nlp`: o que quebrou, quando, com quem e se está crescendo.
* Ritmo e sazonalidade
* Risco e SLA
* Confiabilidade e reincidência — leitura SRE: orçamento de erro, prazo, MTBF,
  recaída, reincidência e tempestades de evento.
* Confiança dos modelos   — semáforo + métricas de cada modelo publicado.
"""
import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import (POWERBI_NOC_URL, META_MTTR_H, MTTR_MAX_H,
                    SLA_HORAS_POR_PRIORIDADE, PREV_DURACAO_UNIT)
from data_loader import load_prediction_table
from theme import (apply_theme, STATUS_COLORS, CHART_SCALE_LOAD,
                   CHART_SCALE_RISK, RISK_RED, RISK_YELLOW, RISK_GREEN,
                   RED, NAVY_LIGHT)
import theme as T
import viz_helpers as V
import data_prep

PAGE = "NOC"
META_KPI = 95.0            # meta de cumprimento de SLA/KPI (%) — define o orçamento de erro
ENCERRADOS = {"Encerrado", "Encerrado Automaticamente"}
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
CINZA = "#C9CED6"

# Faixas de duração usadas para avaliar o modelo de duração.
_BINS_DUR = [0, 0.25, 1, 4, 12, 24, 72, np.inf]
_ROT_DUR = ["<15 min", "15 min–1 h", "1–4 h", "4–12 h", "12–24 h", "1–3 dias", ">3 dias"]
_VAZIOS = {"", "NAN", "NONE", "NULL", "<NA>", "-", "SEM_IC", "SEM IC"}


def sanitize_iframe_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    raw_url = raw_url.strip()
    m = re.search(r'src=["\'](https?://[^"\']+)["\']', raw_url, re.IGNORECASE)
    return m.group(1).strip() if m else raw_url


def _prev_real_for_ref(prev_d1: pd.DataFrame):
    """Devolve (previsto, real, real_dia_anterior) do modelo D+1 para 09/12/2025."""
    if prev_d1 is None or prev_d1.empty:
        return None, None, None
    dcol = V.pick_col(prev_d1, "Data", "date", "dia")
    pcol = V.pick_col(prev_d1, "Incidentes_Previstos", "previsto", contains=True)
    rcol = V.pick_col(prev_d1, "Incidentes_Reais", "real", contains=True)
    if not (dcol and pcol):
        return None, None, None
    d = prev_d1.copy()
    d[dcol] = pd.to_datetime(d[dcol], errors="coerce")
    d = d.dropna(subset=[dcol]).sort_values(dcol)
    row = d[d[dcol].dt.date == V.REF_DATE.date()]
    if row.empty:
        row = d.tail(1)
    prev = float(row[pcol].iloc[0]) if pcol else None
    real = float(row[rcol].iloc[0]) if rcol and rcol in row else None
    idx = d.index.get_loc(row.index[0]) if row.index[0] in d.index else None
    ant = float(d[rcol].iloc[idx - 1]) if (rcol and idx and idx > 0) else None
    return prev, real, ant


# ============================================================================
# Helpers de dados da tela
# ============================================================================
def _janela(df: pd.DataFrame, dias: int) -> pd.DataFrame:
    """Incidentes abertos nos `dias` dias que terminam na data de referência."""
    ref = V.REF_DATE
    return df[(df["Aberto"] >= ref - pd.Timedelta(days=dias - 1)) &
              (df["Aberto"] < ref + pd.Timedelta(days=1))]


def _res(frame: pd.DataFrame) -> pd.Series:
    if "_res" in frame.columns:
        return frame["_res"]
    if "Resolvido" in frame.columns:
        return pd.to_datetime(frame["Resolvido"], errors="coerce")
    return pd.Series(pd.NaT, index=frame.index)


def _cor_relativa(topo: float):
    """Função valor -> cor pela fração do maior valor (maior incidência em vermelho)."""
    topo = float(topo or 0)
    return lambda v: V.cor_nivel((float(v) / topo) if topo > 0 else 0, 1 / 3, 2 / 3)


def _cor_mape(v) -> str:
    if v is None or pd.isna(v):
        return CINZA
    return V.cor_nivel(v, 10, 20)


def _serie_volume(tabela: str) -> pd.DataFrame:
    """`previsao_d1` / `previsao_d7` normalizadas em data, previsto, real (1 linha por data)."""
    bruto = load_prediction_table(tabela)
    vazio = pd.DataFrame(columns=["data", "previsto", "real"])
    if bruto is None or bruto.empty:
        return vazio
    dcol = V.pick_col(bruto, "Data", "data", "date")
    pcol = V.pick_col(bruto, "Incidentes_Previstos", "previsto", contains=True)
    rcol = V.pick_col(bruto, "Incidentes_Reais", "real", contains=True)
    if not (dcol and pcol):
        return vazio
    out = pd.DataFrame({
        "data": pd.to_datetime(bruto[dcol], errors="coerce"),
        "previsto": pd.to_numeric(bruto[pcol], errors="coerce"),
        "real": pd.to_numeric(bruto[rcol], errors="coerce") if rcol else np.nan,
    }).dropna(subset=["data"])
    return (out.drop_duplicates(subset=["data"], keep="last")
               .sort_values("data").reset_index(drop=True))


def _prev_cluster(horizonte: str) -> pd.DataFrame:
    return data_prep.previsao_cluster(horizonte)


def _metricas_cluster() -> pd.DataFrame:
    return data_prep.metricas_cluster()


def _mape_regime(met: pd.DataFrame, cluster, horizonte: str):
    if met.empty:
        return None
    h = met[met["horizonte"].map(V._key).str.contains(V._key(horizonte).replace("d", ""), regex=False)]
    linha = h[h["cluster"].map(V._key) == V._key(cluster)]
    return float(linha["MAPE"].iloc[0]) if not linha.empty and pd.notna(linha["MAPE"].iloc[0]) else None


def _ic_base(frame: pd.DataFrame) -> pd.DataFrame:
    """Incidentes com item de configuração, ordenados por IC, com gaps de recorrência.

    `_gap_h`: horas desde a abertura anterior no mesmo IC.
    `_ate_prox_h`: horas entre a resolução deste e a próxima abertura no mesmo IC.
    `_recaida24`: o IC voltou a falhar em até 24 h depois deste incidente ser resolvido.
    """
    if frame is None or frame.empty or "Item de configuração" not in frame.columns:
        return pd.DataFrame()
    ic = frame["Item de configuração"].astype(str).str.strip()
    ok = frame["Item de configuração"].notna() & ~ic.str.upper().isin(_VAZIOS)
    if not ok.any():
        return pd.DataFrame()
    d = frame[ok].assign(_ic=ic[ok]).sort_values(["_ic", "Aberto"])
    g = d.groupby("_ic", sort=False)
    d["_gap_h"] = g["Aberto"].diff().dt.total_seconds() / 3600
    prox = g["Aberto"].shift(-1)
    d["_ate_prox_h"] = (prox - _res(d)).dt.total_seconds() / 3600
    d["_recaida24"] = d["_ate_prox_h"].between(0, 24)
    return d


# ============================================================================
def render_operador_painel():
    apply_theme()
    T.hero("Painel NOC — Centro de Operações",
           "Monitoramento contínuo, SLA/OLA, distribuição de carga e alertas preventivos. "
           f"Data operacional de referência: <code>{V.REF_DATE_STR}</code>.")

    # ---------------- Dados base ----------------
    df = data_prep.incidentes()
    prev_d1 = load_prediction_table("previsao_d1")

    # ---------------- Filtros globais (slicers) ----------------
    T.section("# Filtros globais", ico="filter")
    df = V.global_slicers(df, PAGE, [
        ("Prioridade", "_P"), ("Turno", "_Turno"), ("Grupo Designado", "Grupo designado"),
    ])

    # ---------------- Cross-filter (clique nas roscas) ----------------
    xf = st.session_state.get(f"{PAGE}_xfilter")
    if xf:
        col, val = xf
        if col in df.columns:
            df = df[df[col] == val]
        V.cross_filter_chip(PAGE, {"Status": "Status", "_P": "Prioridade"}.get(col, col))

    ref = V.REF_DATE
    df_ref = df[df["Aberto"].dt.date == ref.date()]

    # ---------------- Cards operacionais ----------------
    prev_dia, real_d1, real_ant = _prev_real_for_ref(prev_d1)
    inc_dia = len(df_ref)
    delta_prev = (inc_dia - prev_dia) / prev_dia * 100 if prev_dia else None
    hist_media = df[df["Aberto"] < ref].groupby(df["Aberto"].dt.date).size().mean()

    # MTTR: 'Duração' em segundos, janela ancorada em 'Resolvido', média sem
    # registros parados acima de MTTR_MAX_H.
    resolvidos = V.resolved_base(df, ENCERRADOS, max_h=MTTR_MAX_H)
    d_ini, d_fim = ref, ref + pd.Timedelta(days=1)
    st_dia = V.mttr_stats(resolvidos, d_ini, d_fim)
    st_wk = V.mttr_stats(resolvidos, ref - pd.Timedelta(days=6), d_fim)
    mttr_dia_h, mttr_wk_h = st_dia["mean"], st_wk["mean"]

    p12_dia = int(df_ref["_P"].isin(["P1", "P2"]).sum())
    tratados_dia = int((df_ref["Status"] != "Sem Intervenção").sum())
    auto_dia = int((df_ref["Status"] == "Sem Intervenção").sum())

    sla = data_prep.sla()
    quase = int((sla["_pct"] > 75).sum()) if not sla.empty else 0
    criticos = int((sla["_pct"] > 90).sum()) if not sla.empty else 0

    mes_ref = df[(df["Aberto"].dt.year == ref.year) & (df["Aberto"].dt.month == ref.month)]
    mes_ant = df[(df["Aberto"].dt.year == ref.year) & (df["Aberto"].dt.month == ref.month - 1)]
    viol_mes = int((mes_ref["KPI Violado?"] == "SIM").sum())
    viol_ant = int((mes_ant["KPI Violado?"] == "SIM").sum())

    r1 = st.columns(4)
    r1[0].metric("Incidentes do Dia", V.br(inc_dia),
                 delta=(f"{V.br(delta_prev, 1, '%')} vs previsto" if delta_prev is not None else None),
                 delta_color="inverse")
    r1[1].metric("Previstos no Dia (D+1)", V.br(prev_dia),
                 delta=(f"{V.br(prev_dia - hist_media, 0)} vs média hist." if (prev_dia and pd.notna(hist_media)) else None))
    r1[2].metric("MTTR do Dia", V.fmt_hours(mttr_dia_h),
                 delta=(f"{V.br(mttr_dia_h - META_MTTR_H, 1, ' h')} vs meta" if mttr_dia_h is not None else None),
                 delta_color="inverse")
    r1[3].metric("MTTR da Semana", V.fmt_hours(mttr_wk_h),
                 delta=(f"{V.br(mttr_wk_h - META_MTTR_H, 1, ' h')} vs meta" if mttr_wk_h is not None else None),
                 delta_color="inverse")

    r2 = st.columns(4)
    r2[0].metric("Incidentes P1/P2 no Dia", V.br(p12_dia),
                 delta=("criticidade elevada" if p12_dia > 0 else "sob controle"),
                 delta_color="inverse")
    r2[1].metric("Exigiram intervenção humana", V.br(tratados_dia),
                 delta=(f"{V.br(auto_dia)} fecharam sozinhos" if auto_dia else None),
                 delta_color="off")
    r2[2].metric("Quase Violações (prob > 75%)", V.br(quase),
                 delta=(f"{V.br(criticos)} em risco crítico (>90%)" if quase else None),
                 delta_color="inverse")
    r2[3].metric("Violações SLA no Mês", V.br(viol_mes),
                 delta=(f"{V.br(viol_mes - viol_ant)} vs mês anterior" if viol_ant else None),
                 delta_color="inverse")

    st.caption(
        f"Cards ancorados em {V.REF_DATE_STR} · **MTTR** = média de (Resolvido − Aberto) dos "
        f"incidentes encerrados **no período**, meta {META_MTTR_H:.0f} h · "
        f"Dia: n={V.br(st_dia['n'])}, mediana {V.fmt_hours(st_dia['p50'])}, p90 {V.fmt_hours(st_dia['p90'])} · "
        f"Semana: n={V.br(st_wk['n'])}, mediana {V.fmt_hours(st_wk['p50'])}, p90 {V.fmt_hours(st_wk['p90'])} · "
        f"Fora da média: {V.br(resolvidos.attrs.get('descartados_outlier', 0))} registros acima de "
        f"{MTTR_MAX_H/24:.0f} dias · Quase violações e risco vêm do modelo `previsao_sla`."
    )
    st.divider()

    # Abas em ordem de valor operacional: o dia e o risco de OLA primeiro; ritmo
    # histórico e confiança dos modelos por último.
    (aba_dia, aba_risco, aba_regime, aba_nlp, aba_sre, aba_ritmo,
     aba_modelos) = st.tabs(
        ["Visão do dia", "Risco e OLA", "Demanda por tipo de trabalho", "Tipos de problema (NLP)",
         "Confiabilidade e reincidência", "Ritmo e sazonalidade", "Confiança dos modelos"])

    with aba_dia:
        _aba_dia(df, df_ref)
    with aba_regime:
        _aba_regime(df, df_ref)
    with aba_nlp:
        _aba_nlp(df, sla)
    with aba_ritmo:
        _aba_ritmo(df, prev_dia)
    with aba_risco:
        _aba_risco(df, sla, resolvidos)
    with aba_sre:
        _aba_confiabilidade(df, resolvidos)
    with aba_modelos:
        _aba_modelos()


# ============================================================================
# VISÃO DO DIA — tudo recortado em 09/12
# ============================================================================
def _aba_dia(df: pd.DataFrame, df_ref: pd.DataFrame):
    ref = V.REF_DATE
    # Ordem: ritmo e esforço humano do dia → o que chegou (regime/tema) → onde a
    # carga se concentra → distribuição por status/prioridade (filtros clicáveis).
    f1, f2 = st.columns([1.3, 1])
    with f1:
        T.section(f"Fila do dia: incidentes abertos vs resolvidos ({V.REF_DATE_STR})", ico="flow")
        if not df_ref.empty:
            # As duas curvas são da mesma coorte — incidentes abertos em 09/12. Antes
            # entravam fechamentos de incidentes abertos em datas anteriores.
            ch = df_ref.groupby(df_ref["Aberto"].dt.hour).size().reindex(range(24), fill_value=0)
            coorte = df_ref[_res(df_ref).dt.date == ref.date()]
            rs = (coorte.groupby(_res(coorte).dt.hour).size().reindex(range(24), fill_value=0)
                  if not coorte.empty else pd.Series(0, index=range(24)))
            V.plot(V.cumulative_flow([f"{h:02d}h" for h in range(24)], ch, rs, height=340),
                   key=f"{PAGE}_cfd")
            fila = ch.cumsum() - rs.cumsum()
            pico_h = int(fila.idxmax()) if fila.max() > 0 else None
            virou = len(df_ref) - len(coorte)
            st.caption(
                f"Só incidentes abertos em {V.REF_DATE_STR}. A distância entre as curvas é o que "
                "estava pendente naquela hora"
                + (f" — pico de **{V.br(int(fila.max()))}** às {pico_h:02d}h" if pico_h is not None else "")
                + f". **{V.br(virou)}** incidentes do dia só foram resolvidos depois da meia-noite.")
        else:
            st.info(f"Sem incidentes em {V.REF_DATE_STR} para o filtro atual.")
    with f2:
        T.section("Precisaram de pessoa vs fecharam sozinhos", ico="users")
        if not df_ref.empty:
            comp = pd.Series({
                "Auto-resolvido": int((df_ref["Status"] == "Sem Intervenção").sum()),
                "Com intervenção": int((df_ref["Status"] != "Sem Intervenção").sum())})
            V.plot(V.donut(comp, colors={"Auto-resolvido": CINZA, "Com intervenção": RED},
                           center="Dia", height=340), key=f"{PAGE}_auto")
            st.caption(f"{V.br(int(comp['Com intervenção']))} de {V.br(int(comp.sum()))} incidentes "
                       f"precisaram de intervenção humana. O restante fechou sozinho.")
        else:
            st.info("Sem incidentes na data de referência.")

    st.divider()
    T.section("O que chegou hoje", ico="layers")
    c1, c2 = st.columns(2)
    with c1:
        T.section("Incidentes de hoje: ruído automático, operação ou crítico", sub="clusters_incidentes", ico="layers")
        reg = data_prep.perfil_regimes(data_prep.com_regime(df_ref))
        if not reg.empty:
            V.plot(V.lollipop(reg["incidentes"], height=280,
                              cores=V.cores_regime(reg.index, reg["pct_P2"])), key=f"{PAGE}_dia_regime")
            st.caption("Verde: ruído automatizado · amarelo: operação · vermelho: cauda crítica. "
                       "Previsão na aba **Demanda por tipo de trabalho**.")
        else:
            st.info(f"Nenhum incidente de {V.REF_DATE_STR} tem regime em `clusters_incidentes`.")
    with c2:
        T.section("Tipos de problema mais frequentes hoje", sub="cluster_nlp", ico="brain")
        tm = data_prep.com_tema(df_ref)
        if not tm.empty:
            cont = tm["_tema"].value_counts().head(8)
            V.plot(V.lollipop(cont, height=280, cores=V.cores_relativas(cont)), key=f"{PAGE}_dia_tema")
            st.caption("Temas extraídos das descrições. Tendência, horário e equipes na aba "
                       "**Tipos de problema (NLP)**.")
        else:
            st.info(f"Nenhum incidente de {V.REF_DATE_STR} tem tema em `cluster_nlp`.")

    st.divider()
    T.section("Produtos que concentram os incidentes do dia", ico="box")
    pp = df_ref["Produto"].value_counts().head(15) if not df_ref.empty else pd.Series(dtype=int)
    if not pp.empty:
        V.plot(V.pareto(pp.index, pp.values, height=380, niveis=True), key=f"{PAGE}_pareto")
        acum = pp.cumsum() / df_ref["Produto"].notna().sum() * 100
        n80 = int((acum < 80).sum()) + 1
        st.caption(f"{n80} produto(s) concentram cerca de 80% dos incidentes do dia. "
                   "Vermelho: maior volume · verde: menor.")
    else:
        st.info("Sem produtos na data de referência para o filtro atual.")

    st.divider()
    T.section("Filtrar o painel por status ou prioridade", ico="chart")
    d1, d2 = st.columns(2)
    with d1:
        T.section("Incidentes do dia por status", ico="pulse")
        sc = df_ref["Status"].value_counts()
        if not sc.empty:
            sel = V.selectable(V.donut(sc, colors=STATUS_COLORS, center="Status"),
                               key=f"{PAGE}_donut_status", field="label")
            if sel and st.session_state.get(f"{PAGE}_xfilter") != ("Status", sel[0]):
                st.session_state[f"{PAGE}_xfilter (clique no gráfico)"] = ("Status", sel[0])
                st.rerun()
        else:
            st.info(f"Sem incidentes em {V.REF_DATE_STR} para o filtro atual.")
    with d2:
        T.section("Incidentes do dia por prioridade", ico="chart")
        pc = (df_ref["_P"].value_counts()
              .reindex([p for p in V.PRIO_ORDER if p in set(df_ref["_P"])]).dropna())
        if not pc.empty:
            sel = V.selectable(V.donut(pc, colors=V.PRIO_COLORS, center="Prioridade"),
                               key=f"{PAGE}_donut_prio", field="label")
            if sel and st.session_state.get(f"{PAGE}_xfilter") != ("_P", sel[0]):
                st.session_state[f"{PAGE}_xfilter"] = ("_P", sel[0])
                st.rerun()
        else:
            st.info(f"Sem incidentes em {V.REF_DATE_STR} para o filtro atual.")

    cols_exp = [c for c in ["Número", "Prioridade", "Grupo designado", "Produto", "Status",
                            "KPI Violado?"] if c in df_ref.columns]
    V.csv_download(df_ref[cols_exp], "Exportar incidentes do dia (CSV)",
                   "noc_incidentes_dia.csv", key=f"{PAGE}_exp")


# ============================================================================
# DEMANDA POR REGIME — clusters_incidentes + previsão por cluster
# ============================================================================
def _aba_regime(df: pd.DataFrame, df_ref: pd.DataFrame):
    ref = V.REF_DATE
    reg30 = data_prep.com_regime(_janela(df, 30))
    perfil30 = data_prep.perfil_regimes(reg30)

    T.section("Incidentes previstos, por tipo de trabalho",
              sub="`previsao_d1_por_cluster` · `previsao_d7_por_cluster`", ico="layers")
    horizonte = st.radio("Horizonte", ["D+1", "D+7"], horizontal=True, key=f"{PAGE}_reg_h")
    prev = _prev_cluster(horizonte)
    met = _metricas_cluster()

    if prev.empty:
        st.info(f"Tabela `previsao_{horizonte.lower().replace('+', '')}_por_cluster` indisponível.")
    else:
        dia = prev[prev["data"].dt.date == ref.date()]
        rotulo = V.REF_DATE_STR
        if dia.empty:
            ultima = prev["data"].max()
            dia, rotulo = prev[prev["data"] == ultima], ultima.strftime("%d/%m/%Y")

        total_p = float(dia["previsto"].sum())
        total_r = float(dia["real"].sum()) if dia["real"].notna().any() else None
        cols = st.columns(len(dia) + 1)
        cols[0].metric(f"Total previsto · {rotulo}", V.br(total_p),
                       delta=(f"real {V.br(total_r)} ({V.br((total_r - total_p) / total_p * 100, 1, '%')})"
                              if total_r is not None and total_p else None),
                       delta_color="off")
        for i, (_, lin) in enumerate(dia.iterrows(), start=1):
            real_c = lin["real"]
            cols[i].metric(
                str(lin["cluster"]), V.br(lin["previsto"]),
                delta=(f"real {V.br(real_c)} · {V.br(lin['previsto'] / total_p * 100, 0, '%')} do total"
                       if pd.notna(real_c) and total_p else
                       (f"{V.br(lin['previsto'] / total_p * 100, 0, '%')} do total" if total_p else None)),
                delta_color="off")
        humano = dia[~dia["cluster"].str.contains("ru[íi]do", case=False, regex=True)]["previsto"].sum()
        if total_p:
            st.info(f"Dos {V.br(total_p)} incidentes previstos para {rotulo} ({horizonte}), "
                    f"**{V.br(humano)} ({V.br(humano / total_p * 100, 1, '%')}) exigem atuação "
                    "humana** — é esse número que dimensiona a escala, não o volume total.")

        opcoes = ["Todos"] + sorted(prev["cluster"].unique())
        escolha = st.radio("Tipo de trabalho", opcoes, horizontal=True, key=f"{PAGE}_reg_sel")
        if escolha == "Todos":
            serie = (prev.groupby("data")[["previsto", "real"]].sum(min_count=1).reset_index())
            mapes = [m for m in (_mape_regime(met, c, horizonte) for c in prev["cluster"].unique()) if m]
            mape_sel = float(np.median(mapes)) if mapes else None
        else:
            serie = prev[prev["cluster"] == escolha][["data", "previsto", "real"]]
            mape_sel = _mape_regime(met, escolha, horizonte)
        serie = serie[serie["data"] >= serie["data"].max() - pd.Timedelta(days=60)]
        banda = min(max((mape_sel or 12) / 100, 0.03), 0.6)
        fig = V.forecast_line(serie, "data", "real", "previsto", height=360, band_pct=banda)
        fig.add_shape(type="line", x0=ref, x1=ref, y0=0, y1=1, yref="paper",
                      line=dict(color=CINZA, dash="dot", width=1.5))
        V.plot(fig, key=f"{PAGE}_reg_forecast")
        m_serie = V.metricas_regressao(serie["real"], serie["previsto"])
        st.caption(
            f"Faixa sombreada = ±{V.br(banda * 100, 0, '%')} "
            + ("(MAPE do modelo em `metricas_previsao_por_cluster`)" if mape_sel else "(faixa padrão)")
            + f". Linha pontilhada: {V.REF_DATE_STR}."
            + (f" Nos últimos 60 dias: erro médio de {V.br(m_serie['mae'], 1)} incidentes/dia, "
               f"MAPE {V.br(m_serie['mape'], 1, '%')}." if m_serie else ""))

        futuro = prev[prev["data"] > ref]
        if not futuro.empty:
            with st.expander(f"Projeção após {V.REF_DATE_STR} ({horizonte})"):
                pv = futuro.pivot_table(index="data", columns="cluster", values="previsto",
                                        aggfunc="sum").round(0)
                pv.index = pv.index.strftime("%d/%m/%Y")
                st.dataframe(pv, use_container_width=True)

    st.divider()
    T.section("Incidentes que chegaram, por tipo de trabalho", sub="base `incidentes` com os filtros aplicados",
              ico="layers")
    if reg30.empty:
        st.info("Nenhum incidente da janela tem regime em `clusters_incidentes`.")
        return
    cores = V.cores_regime(perfil30.index, perfil30["pct_P2"])
    r1, r2 = st.columns(2)
    with r1:
        T.section("Incidentes por dia e tipo de trabalho (30 dias)", ico="chart")
        piv = (reg30.assign(_d=reg30["Aberto"].dt.normalize())
               .pivot_table(index="_d", columns="_regime", values="Número",
                            aggfunc="count", fill_value=0).sort_index())
        piv = piv[[c for c in perfil30.index if c in piv.columns]]
        V.plot(V.area_stacked(piv.index.strftime("%d/%m"), {c: piv[c] for c in piv.columns},
                              colors=cores, height=340, titulo_y="incidentes/dia"),
               key=f"{PAGE}_reg_area30")
        ult = piv.iloc[-7:].sum()
        if ult.sum():
            st.caption("Últimos 7 dias: " + " · ".join(
                f"{k} {V.br(v / ult.sum() * 100, 0, '%')}" for k, v in ult.items()))
    with r2:
        T.section(f"Incidentes por hora e tipo de trabalho ({V.REF_DATE_STR})", ico="clock")
        reg_dia = reg30[reg30["Aberto"].dt.date == ref.date()]
        if not reg_dia.empty:
            ph = (reg_dia.pivot_table(index=reg_dia["Aberto"].dt.hour, columns="_regime",
                                      values="Número", aggfunc="count", fill_value=0)
                  .reindex(range(24), fill_value=0))
            ph = ph[[c for c in perfil30.index if c in ph.columns]]
            V.plot(V.area_stacked([f"{h:02d}h" for h in ph.index], {c: ph[c] for c in ph.columns},
                                  colors=cores, height=340, titulo_y="incidentes/h"),
                   key=f"{PAGE}_reg_hora")
            nao_ruido = [c for c in ph.columns if not re.search("ru[íi]do", str(c), re.I)]
            if nao_ruido:
                pico = ph[nao_ruido].sum(axis=1)
                st.caption(f"Pico de trabalho que exige gente: **{int(pico.idxmax()):02d}h** "
                           f"({V.br(int(pico.max()))} incidentes fora do ruído).")
        else:
            st.info(f"Sem incidentes com regime em {V.REF_DATE_STR}.")

    r3, r4 = st.columns(2)
    with r3:
        T.section("Tipo de trabalho que cada equipe recebe (30 dias)", ico="users")
        top_eq = reg30["Grupo designado"].value_counts().head(10).index
        pe = (reg30[reg30["Grupo designado"].isin(top_eq)]
              .pivot_table(index="Grupo designado", columns="_regime", values="Número",
                           aggfunc="count", fill_value=0))
        pe = pe[[c for c in perfil30.index if c in pe.columns]]
        pe = pe.loc[pe.sum(axis=1).sort_values().index]
        V.plot(V.stacked_hbar(pe, colors=cores, height=380), key=f"{PAGE}_reg_eq")
        st.caption("Equipe com barra majoritariamente verde gasta o turno com ruído — candidata "
                   "a regra de supressão ou auto-remediação.")
    with r4:
        T.section("Resumo de cada tipo de trabalho (30 dias)", ico="grid")
        tab = perfil30.copy()
        tab["% do volume"] = tab["incidentes"] / tab["incidentes"].sum() * 100
        tab = tab.reset_index().rename(columns={
            "_regime": "Regime", "incidentes": "Incidentes", "pct_P2": "% alta prioridade",
            "pct_manual": "% aberto manualmente", "duracao_mediana_h": "Duração mediana (h)"})
        for h in ["D+1", "D+7"]:
            tab[f"MAPE {h}"] = tab["Regime"].apply(lambda c, h=h: _mape_regime(met, c, h))
        for c in ["% do volume", "% alta prioridade", "% aberto manualmente",
                  "Duração mediana (h)", "MAPE D+1", "MAPE D+7"]:
            tab[c] = pd.to_numeric(tab[c], errors="coerce").round(1)
        st.dataframe(tab[["Regime", "Incidentes", "% do volume", "% alta prioridade",
                          "% aberto manualmente", "Duração mediana (h)", "MAPE D+1", "MAPE D+7"]],
                     hide_index=True, use_container_width=True)
        st.caption("MAPE vem de `metricas_previsao_por_cluster` (vazio quando o nome do cluster "
                   "no modelo não casa com o `Cluster_Nome`).")


# ============================================================================
# TIPOS DE PROBLEMA — cluster_nlp
# ============================================================================
def _aba_nlp(df: pd.DataFrame, sla: pd.DataFrame):
    ref = V.REF_DATE
    tema30 = data_prep.com_tema(_janela(df, 30))
    if tema30.empty:
        st.info("Nenhum incidente da janela tem tema em `cluster_nlp`.")
        return
    tema30 = tema30.assign(_dia=tema30["Aberto"].dt.normalize())
    tema_dia = tema30[tema30["_dia"] == ref]
    hist = tema30[tema30["_dia"] < ref]
    dias_hist = max(hist["_dia"].nunique(), 1)

    no_dia = tema_dia["_tema"].value_counts()
    media = hist["_tema"].value_counts() / dias_hist
    comp = pd.DataFrame({"no_dia": no_dia, "media": media}).fillna(0)
    comp["desvio"] = comp["no_dia"] - comp["media"]
    comp["tend"] = np.where(comp["media"] > 0,
                            (comp["no_dia"] / comp["media"].where(comp["media"] > 0) - 1) * 100, np.nan)

    ult7 = tema30[tema30["_dia"] > ref - pd.Timedelta(days=7)]["_tema"].value_counts() / 7
    ant21 = tema30[(tema30["_dia"] <= ref - pd.Timedelta(days=7)) &
                   (tema30["_dia"] > ref - pd.Timedelta(days=28))]["_tema"].value_counts() / 21
    cres = pd.DataFrame({"u7": ult7, "a21": ant21}).fillna(0)
    cres["pct"] = np.where(cres["a21"] > 0,
                           (cres["u7"] / cres["a21"].where(cres["a21"] > 0) - 1) * 100, np.nan)

    # ---- Cards
    T.section(f"Tipos de problema do dia ({V.REF_DATE_STR})", sub="temas extraídos das descrições (`cluster_nlp`)",
              ico="brain")
    k = st.columns(4)
    k[0].metric("Temas ativos no dia", V.br(int((no_dia > 0).sum())),
                delta=f"{V.br(len(tema_dia))} incidentes classificados", delta_color="off")
    if not no_dia.empty:
        k[1].metric("Tema dominante", str(no_dia.index[0]),
                    delta=f"{V.br(no_dia.iloc[0] / no_dia.sum() * 100, 0, '%')} do dia", delta_color="off")
    alta = comp[(comp["no_dia"] >= 3) & comp["tend"].notna()].sort_values("tend", ascending=False)
    if not alta.empty and alta["tend"].iloc[0] > 0:
        k[2].metric("Maior alta vs normal", str(alta.index[0]),
                    delta=f"+{V.br(alta['tend'].iloc[0], 0, '%')} vs média diária", delta_color="inverse")
    else:
        k[2].metric("Maior alta vs normal", "—", delta="nenhum tema acima do normal", delta_color="off")
    sat_dia = int(tema_dia["_tema"].isin(data_prep.TEMAS_SATURACAO).sum())
    k[3].metric("Saturação de recurso no dia", V.br(sat_dia),
                delta=(f"{V.br(sat_dia / len(tema_dia) * 100, 0, '%')} do volume" if len(tema_dia) else None),
                delta_color="off")

    # ---- Linha 1
    a1, a2 = st.columns(2)
    with a1:
        T.section("Tipos de problema acima ou abaixo do normal hoje", ico="alert")
        e = comp.reindex(comp["desvio"].abs().sort_values(ascending=False).index).head(10)
        if not e.empty:
            V.plot(V.divergent_bar(e.index, e["no_dia"], e["media"], height=360,
                                   nome_base="média/dia (29 dias)", tolerancia=0.25),
                   key=f"{PAGE}_nlp_desvio")
            st.caption("Vermelho: tema mais de 25% acima da própria média diária. Amarelo: acima, "
                       "dentro da tolerância. Verde: no normal ou abaixo.")
    with a2:
        T.section("% de cada tipo de problema que é ruído, operação ou crítico", ico="users")
        pv, cores_tr = data_prep.tema_x_regime(tema30)
        if not pv.empty:
            V.plot(V.stacked_hbar(pv, colors=cores_tr, height=360, sufixo="%", rotulos=True),
                   key=f"{PAGE}_nlp_regime")
            st.caption("Cada tema dividido pelo tipo de trabalho. Tema quase todo verde é ruído "
                       "de monitoramento; vermelho é o que vira problema de verdade.")
        else:
            st.info("Sem regime nem status para dividir os temas.")

    # ---- Linha 2
    b1, b2 = st.columns([1.3, 1])
    perfil = data_prep.perfil_temas_de(tema30)
    with b1:
        T.section("Tipos de problema para atacar primeiro: volume × risco (30 dias)", ico="target")
        if not perfil.empty:
            bdf = perfil.reset_index().rename(columns={"_tema": "tema"})
            rotulo_y = "% P1/P2"
            bdf["y"] = bdf["tema"].map(tema30.groupby("_tema")["_P"]
                                       .apply(lambda s: s.isin(["P1", "P2"]).mean() * 100))
            if not sla.empty:
                prob = sla.drop_duplicates(subset=["_num"]).set_index("_num")["_pct"]
                rk = tema30.assign(_prob=tema30["_k"].map(prob)).dropna(subset=["_prob"])
                cob = rk.groupby("_tema")["_prob"].agg(["mean", "size"])
                if (cob["size"] >= 5).sum() >= max(2, len(bdf) // 2):
                    bdf["y"] = bdf["tema"].map(cob["mean"])
                    rotulo_y = "risco médio previsto de violação (%)"
            bdf = bdf.dropna(subset=["y"])
            bdf["tamanho"] = bdf["horas_estimadas"].clip(lower=1)
            topo_y = float(bdf["y"].max() or 0)
            cores_b = [V.cor_nivel(v / topo_y if topo_y else 0, 1 / 3, 2 / 3) for v in bdf["y"]]
            V.plot(V.bubble_matrix(bdf, x="incidentes", y="y", size="tamanho", text="tema",
                                   height=400, rotulo_x="incidentes (30 dias, escala log)",
                                   rotulo_y=rotulo_y, cores=cores_b), key=f"{PAGE}_nlp_bolha")
            st.caption("Bolha = horas estimadas (volume × duração mediana). Quadrante superior "
                       "direito: muito volume e muito risco — primeiro alvo de problema-raiz. "
                       "Superior esquerdo: pouco volume, alto risco — não deixar sumir na fila.")
    with b2:
        T.section("Disco, CPU e memória: quanto cresceu na última semana", ico="trend")
        sat = cres[cres.index.isin(data_prep.TEMAS_SATURACAO)]["pct"].dropna()
        if not sat.empty:
            V.plot(V.simple_hbar(sat.round(0), height=400, sufixo="%", casas=0,
                                 cor_fn=lambda v: V.cor_nivel(v, 10, 30)), key=f"{PAGE}_nlp_sat")
            st.caption("Média diária dos últimos 7 dias contra os 21 anteriores. Swap, disco e CPU "
                       "não estouram de repente: crescem. Vermelho (>30%) pede ampliação de "
                       "capacidade antes do incidente, não depois.")
        else:
            st.info("Sem temas de saturação (swap, disco, CPU) com histórico na janela.")

    # ---- Linha 3
    T.section("Incidentes por dia de cada tipo de problema (30 dias)", ico="trend")
    pdia = (tema30.pivot_table(index="_dia", columns="_tema", values="Número",
                               aggfunc="count", fill_value=0)
            .reindex(pd.date_range(ref - pd.Timedelta(days=29), ref, freq="D"), fill_value=0))
    candidatos = cres[(cres["u7"] >= 1) & cres["pct"].notna()].sort_values("pct", ascending=False)
    destaques = list(candidatos.head(3).index) or list(pdia.sum().sort_values(ascending=False).head(3).index)
    V.plot(V.line_multi(pdia.index.strftime("%d/%m"), {c: pdia[c] for c in pdia.columns},
                        destaques=destaques, height=380, titulo_y="incidentes/dia"),
           key=f"{PAGE}_nlp_linhas")
    st.caption("Em destaque os 3 temas que mais cresceram na última semana: "
               + " · ".join(f"**{t}** ({'+' if cres.loc[t, 'pct'] >= 0 else ''}"
                            f"{V.br(cres.loc[t, 'pct'], 0, '%')})" for t in destaques
                            if t in cres.index and pd.notna(cres.loc[t, "pct"]))
               + ". Os demais ficam em cinza como contexto.")

    # ---- Linha 4
    c1, c2 = st.columns(2)
    with c1:
        T.section("Em que horário cada tipo de problema acontece", ico="clock")
        ph = pd.crosstab(tema30["_tema"], tema30["Aberto"].dt.hour, normalize="index") * 100
        ph = ph.reindex(columns=range(24), fill_value=0).round(1)
        ph.columns = [f"{h:02d}h" for h in ph.columns]
        V.plot(V.heatmap(ph, scale=CHART_SCALE_LOAD, height=380, value_fmt=""),
               key=f"{PAGE}_nlp_hora")
        st.caption("Cada linha soma 100%: mostra a janela típica de cada tema. Concentração "
                   "noturna em disco/IO costuma ser rotina de backup — ajuste de janela, não incidente.")
    with c2:
        T.section("Equipes que atendem cada tipo de problema", ico="users")
        top_eq = tema30["Grupo designado"].value_counts().head(8).index
        pe = (pd.crosstab(tema30["_tema"], tema30["Grupo designado"], normalize="index") * 100)
        pe = pe.reindex(columns=[c for c in top_eq if c in pe.columns]).round(0)
        V.plot(V.heatmap(pe, scale=CHART_SCALE_LOAD, height=380, value_fmt="%{z:.0f}%"),
               key=f"{PAGE}_nlp_equipe")
        st.caption("% de cada tema que cai em cada equipe. Tema espalhado por muitas equipes = "
                   "roteamento sem dono, retrabalho de triagem.")

    with st.expander("Perfil dos temas — últimos 30 dias"):
        if not perfil.empty:
            vista = perfil.reset_index().rename(columns={
                "_tema": "Tema", "incidentes": "Incidentes", "pct_P2": "% alta prioridade",
                "pct_com_pai": "% com incidente pai", "duracao_mediana_h": "Duração mediana (h)",
                "entram_kpi": "Entram no KPI", "horas_estimadas": "Horas estimadas",
                "saturacao": "Saturação de recurso"})
            vista["No dia"] = vista["Tema"].map(no_dia).fillna(0).astype(int)
            vista["Tendência 7d"] = vista["Tema"].map(cres["pct"]).apply(
                lambda v: "—" if pd.isna(v) else ("▲ " if v > 0 else "▼ ") + V.br(abs(v), 0, "%"))
            for c in ["% alta prioridade", "% com incidente pai", "Duração mediana (h)"]:
                vista[c] = vista[c].round(1)
            st.dataframe(vista, hide_index=True, use_container_width=True)


# ============================================================================
# RITMO E SAZONALIDADE
# ============================================================================
def _aba_ritmo(df: pd.DataFrame, prev_dia):
    ref = V.REF_DATE
    janela = _janela(df, 28)
    r1c, r2c = st.columns(2)
    with r1c:
        T.section("Incidentes por dia (30 dias) e a previsão de hoje", ico="trend")
        base30 = _janela(df, 30)
        if not base30.empty:
            s = base30.groupby(base30["Aberto"].dt.date).size()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[d.strftime("%d/%m") for d in s.index], y=list(s.values),
                                     mode="lines+markers", name="Realizado",
                                     line=dict(color=NAVY_LIGHT, width=2.5),
                                     hovertemplate="%{x}<br>%{y:,} incidentes<extra></extra>"))
            if prev_dia:
                fig.add_trace(go.Scatter(x=[ref.strftime("%d/%m")], y=[prev_dia],
                                         mode="markers", name="Previsto (D+1)",
                                         marker=dict(color=RED, size=14, symbol="diamond"),
                                         hovertemplate="previsto: %{y:,}<extra></extra>"))
            fig.update_layout(xaxis_title=None, yaxis_title="Incidentes/dia")
            V.plot(V.style_fig(fig, height=320, legend=True, legend_top=True),
                   key=f"{PAGE}_trend30")
        else:
            st.info("Sem histórico de 30 dias para o filtro atual.")
    with r2c:
        T.section("Dias da semana com mais incidentes (28 dias)", ico="calendar")
        if not janela.empty:
            dow = (janela["Aberto"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA)))
                   .value_counts().reindex(DIAS_SEMANA).fillna(0))
            V.plot(V.bar_niveis(dow.index, dow.values, list(V.cores_relativas(dow).values()),
                                height=320, casas=0, titulo_y="incidentes"), key=f"{PAGE}_dow")
            st.caption("Vermelho: dias de maior volume · verde: menor.")
        else:
            st.info("Sem dados na janela.")

    st.divider()
    T.section("Horários de pico em cada dia da semana (28 dias)", ico="clock")
    if not janela.empty:
        j = janela.copy()
        j["_dow"] = j["Aberto"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA)))
        piv = (j.pivot_table(index="_dow", columns=j["Aberto"].dt.hour,
                             values="Número", aggfunc="count", fill_value=0)
               .reindex(DIAS_SEMANA).fillna(0))
        piv.columns = [f"{h:02d}h" for h in piv.columns]
        V.plot(V.heatmap(piv, scale=CHART_SCALE_LOAD, height=360), key=f"{PAGE}_hm_dow")
        pico = j.groupby([j["_dow"], j["Aberto"].dt.hour]).size().idxmax()
        st.caption(f"Célula mais carregada da janela: **{pico[0]}, {pico[1]:02d}h**. "
                   "Use para dimensionar a escala de plantão.")
    else:
        st.info("Sem incidentes nos últimos 28 dias para o filtro atual.")

    st.divider()
    T.section("Incidentes por mês: fechados sozinhos vs com pessoa", ico="clock")
    if not df.empty:
        m = df.copy()
        m["_mes"] = m["Aberto"].dt.to_period("M").astype(str)
        comp = (m.assign(_tipo=np.where(m["Status"] == "Sem Intervenção",
                                        "Auto-resolvido", "Com intervenção"))
                .pivot_table(index="_mes", columns="_tipo", values="Número",
                             aggfunc="count", fill_value=0).tail(18))
        V.plot(V.area_stacked(comp.index, {c: comp[c] for c in comp.columns},
                              colors={"Auto-resolvido": CINZA, "Com intervenção": RED},
                              height=340, titulo_y="Incidentes/mês"), key=f"{PAGE}_auto_hist")
        st.caption("Separa o crescimento de volume causado por automação de monitoramento "
                   "do que de fato chegou às equipes. Salto na faixa cinza = mudança de "
                   "observabilidade, não degradação de infraestrutura.")
    else:
        st.info("Sem dados para a série histórica.")


# ============================================================================
# RISCO E OLA
# ============================================================================
def _aba_risco(df: pd.DataFrame, sla: pd.DataFrame, resolvidos: pd.DataFrame):
    ref = V.REF_DATE
    g1, g2 = st.columns([1, 1.25])
    with g1:
        T.section("% de incidentes dentro do OLA (meta 95%)", ico="shield")
        eleg = df[df["Entrou para KPI?"] == "SIM"] if "Entrou para KPI?" in df.columns else df.iloc[0:0]
        total_eleg = len(eleg)
        cumprido = int((eleg["KPI Violado?"] != "SIM").sum()) if total_eleg else 0
        pct = (cumprido / total_eleg * 100) if total_eleg else 0.0
        V.plot(V.gauge(pct, META_KPI), key=f"{PAGE}_gauge")
        st.caption(f"Meta: {META_KPI:.0f}% · Calculado só sobre incidentes com "
                   f"`Entrou para KPI? = SIM` · Elegíveis: {V.br(total_eleg)} · "
                   f"Cumpridos: {V.br(cumprido)}")
    with g2:
        T.section("10 equipes com maior risco de violar o OLA", ico="alert")
        V.render_ranking(
            V.rank_dim(sla, "_grupo", top=10), key=f"{PAGE}_rk_risco", risco=True,
            value_suffix="%", height=360,
            motivo_vazio=("Sem grupo designado nas linhas de `previsao_sla` "
                          "(nem na própria tabela, nem via join com `incidentes`)."))

    st.divider()
    m1, m2 = st.columns(2)
    with m1:
        T.section("Incidentes por prioridade e nível de risco de violar o OLA", ico="alert")
        if not sla.empty and sla["_prio"].notna().any():
            piv = (sla.dropna(subset=["_prio"])
                   .pivot_table(index="_prio", columns="_faixa", values="_pct",
                                aggfunc="count", fill_value=0))
            piv = piv.reindex(index=[p for p in V.PRIO_ORDER if p in piv.index],
                              columns=[f for f in ["Baixo", "Médio", "Alto", "Crítico"]
                                       if f in piv.columns]).fillna(0)
            V.plot(V.heatmap(piv, scale=CHART_SCALE_RISK, height=340), key=f"{PAGE}_matriz")
            st.caption("Quantidade de incidentes em cada cruzamento. O canto superior "
                       "direito (P1/P2 em risco crítico) é a fila de atuação imediata.")
        else:
            st.info("Sem prioridade nas linhas de `previsao_sla` para montar a matriz.")
    with m2:
        T.section("Tempo médio de resolução por prioridade vs meta (7 dias)", ico="clock")
        if not resolvidos.empty:
            jan = resolvidos[(resolvidos["_res"] >= ref - pd.Timedelta(days=6)) &
                             (resolvidos["_res"] < ref + pd.Timedelta(days=1))]
            if not jan.empty:
                mt = jan.groupby("_P")["_dur_h"].mean()
                mt = mt.reindex([p for p in V.PRIO_ORDER if p in mt.index]).dropna()
                V.plot(V.bar_com_meta(mt, META_MTTR_H, height=340, sufixo=" h"),
                       key=f"{PAGE}_mttr_prio")
                st.caption(f"Média dos últimos 7 dias, por prioridade. Barra vermelha = "
                           f"acima da meta de {META_MTTR_H:.0f} h.")
            else:
                st.info("Sem resoluções nos últimos 7 dias para o filtro atual.")
        else:
            st.info("Sem incidentes resolvidos para calcular o MTTR.")

    st.divider()
    T.section("Incidentes para tratar primeiro: maior chance de violar o OLA", ico="shield")
    if not sla.empty:
        tbl = (sla.rename(columns={
            "_num": "Numero_Incidente", "_prio": "Prioridade", "_grupo": "Grupo Designado",
            "_produto": "Produto", "_pct": "Probabilidade_Violacao_%", "_faixa": "Risco"})
            [["Numero_Incidente", "Prioridade", "Grupo Designado", "Produto",
              "Probabilidade_Violacao_%", "Risco"]]
            .sort_values("Probabilidade_Violacao_%", ascending=False))
        V.critical_table(tbl, "Probabilidade_Violacao_%", key=f"{PAGE}_fila",
                         search_cols=["Numero_Incidente", "Grupo Designado",
                                      "Produto", "Prioridade"])
        T.legend(T.LEGENDA_RISCO)
    else:
        st.info("Modelo `previsao_sla` indisponível.")


# ============================================================================
# CONFIABILIDADE E REINCIDÊNCIA — leitura SRE
# ============================================================================
def _aba_confiabilidade(df: pd.DataFrame, resolvidos: pd.DataFrame):
    ref = V.REF_DATE
    base30 = _janela(df, 30)
    jan = (resolvidos[(resolvidos["_res"] >= ref - pd.Timedelta(days=29)) &
                      (resolvidos["_res"] < ref + pd.Timedelta(days=1))]
           if not resolvidos.empty else resolvidos)

    T.section("O OLA está sendo cumprido?", sub="orçamento de erro e cumprimento de prazo",
              ico="shield")
    s1, s2 = st.columns(2)
    with s1:
        T.section(f"Violação de OLA por dia vs limite aceitável da meta de {META_KPI:.0f}% (30 dias)", ico="gauge")
        if {"Entrou para KPI?", "KPI Violado?"} <= set(base30.columns):
            el = base30[base30["Entrou para KPI?"] == "SIM"]
            if not el.empty:
                orc = 1 - META_KPI / 100
                di = el.assign(_v=(el["KPI Violado?"] == "SIM").astype(int),
                               _d=el["Aberto"].dt.normalize())
                diario = (di.groupby("_d").agg(n=("_v", "size"), v=("_v", "sum"))
                          .reindex(pd.date_range(ref - pd.Timedelta(days=29), ref, freq="D"),
                                   fill_value=0))
                diario["burn"] = np.where(diario["n"] > 0,
                                          (diario["v"] / diario["n"].where(diario["n"] > 0)) / orc, 0)
                cores = [RISK_GREEN if b < 1 else RISK_YELLOW if b < 2 else RISK_RED
                         for b in diario["burn"]]
                V.plot(V.bar_niveis(diario.index.strftime("%d/%m"), diario["burn"], cores,
                                    height=340, sufixo="×", casas=1, linha=1.0,
                                    rotulo_linha="ritmo sustentável (1×)", rotulos=False,
                                    titulo_y="burn rate"), key=f"{PAGE}_burn")
                mes = di[di["_d"].dt.month == ref.month]
                consumo = (mes["_v"].sum() / (orc * len(mes)) * 100) if len(mes) else None
                dias_ruins = int((diario["burn"] >= 2).sum())
                st.caption(
                    f"Burn rate = taxa de violação do dia ÷ orçamento de erro "
                    f"({100 - META_KPI:.0f}% dos elegíveis). Acima de 1× o orçamento acaba antes do "
                    f"fim do período. {V.br(dias_ruins)} dia(s) acima de 2× na janela."
                    + (f" **Mês até {V.REF_DATE_STR}: {V.br(consumo, 0, '%')} do orçamento consumido.**"
                       if consumo is not None else ""))
            else:
                st.info("Sem incidentes elegíveis a KPI na janela.")
        else:
            st.info("Base sem `Entrou para KPI?` / `KPI Violado?`.")
    with s2:
        T.section("% resolvido dentro do prazo, por prioridade (30 dias)", ico="clock")
        # Substitui o boxplot de tempo de resolução: a mesma informação (quem
        # estoura o limite da prioridade) em leitura direta de semáforo.
        if not jan.empty:
            lim = jan["_P"].map(SLA_HORAS_POR_PRIORIDADE)
            j = jan[lim.notna()].assign(_raz=jan["_dur_h"] / lim)
            if not j.empty:
                j["_faixa"] = np.select([j["_raz"] <= 1, j["_raz"] <= 2],
                                        ["Dentro do prazo", "Até 2× o prazo"], "Acima de 2× o prazo")
                pz = pd.crosstab(j["_P"], j["_faixa"], normalize="index") * 100
                ordem = ["Dentro do prazo", "Até 2× o prazo", "Acima de 2× o prazo"]
                pz = pz.reindex(columns=[c for c in ordem if c in pz.columns])
                pz = pz.reindex([p for p in reversed(V.PRIO_ORDER) if p in pz.index]).round(1)
                V.plot(V.stacked_hbar(pz, colors={ordem[0]: RISK_GREEN, ordem[1]: RISK_YELLOW,
                                                  ordem[2]: RISK_RED},
                                      height=340, sufixo="%", rotulos=True), key=f"{PAGE}_prazo_prio")
                dentro = pz.get("Dentro do prazo", pd.Series(dtype=float))
                st.caption("Incidentes encerrados nos últimos 30 dias, pelo limite de "
                           "`SLA_HORAS_POR_PRIORIDADE`: " + " · ".join(
                               f"{p}: {V.br(v, 0, '%')} no prazo ({V.br(SLA_HORAS_POR_PRIORIDADE[p], 0, ' h')})"
                               for p, v in dentro.iloc[::-1].items()))
            else:
                st.info("Sem prioridades com prazo configurado na janela.")
        else:
            st.info("Sem resoluções nos últimos 30 dias para o filtro atual.")

    st.divider()
    T.section("Problemas que voltam", sub="o mesmo item de configuração falhando de novo", ico="recycle")
    ic30 = _ic_base(base30)
    if ic30.empty:
        st.info("Sem item de configuração identificado na janela.")
    else:
        # ---- ICs que mais voltam (mantido) + colunas SRE
        ep = ic30[ic30["_gap_h"].isna() | (ic30["_gap_h"] > 0.5)].copy()
        ep["_gap_ep"] = ep.groupby("_ic")["Aberto"].diff().dt.total_seconds() / 3600
        mtbf = ep.groupby("_ic").agg(episodios=("Aberto", "size"), mtbf_h=("_gap_ep", "median"))

        agg = (ic30.groupby("_ic")
               .agg(Incidentes=("Número", "count"),
                    Dias_distintos=("Aberto", lambda s: s.dt.date.nunique()),
                    Recaidas_24h=("_recaida24", "sum"),
                    Produto=("Produto", lambda s: s.mode().iloc[0] if len(s.mode()) else "—"),
                    Equipe=("Grupo designado", lambda s: s.mode().iloc[0] if len(s.mode()) else "—"))
               .sort_values("Incidentes", ascending=False).head(10))
        agg["MTBF mediano (h)"] = mtbf["mtbf_h"].reindex(agg.index).round(1)
        T.section("Itens de configuração com mais incidentes (30 dias)", ico="recycle")
        cc1, cc2 = st.columns([1, 1])
        with cc1:
            V.plot(V.simple_hbar(agg["Incidentes"], height=360,
                                 cor_fn=_cor_relativa(agg["Incidentes"].max())), key=f"{PAGE}_ic")
        with cc2:
            st.dataframe(agg.reset_index().rename(columns={
                "_ic": "Item de configuração", "Dias_distintos": "Dias distintos",
                "Recaidas_24h": "Recaídas ≤24h"}), hide_index=True, use_container_width=True)
        topo = agg.index[0]
        st.caption(f"**{topo}** abriu {V.br(int(agg['Incidentes'].iloc[0]))} incidentes em "
                   f"{V.br(int(agg['Dias_distintos'].iloc[0]))} dias distintos nos últimos "
                   f"30 dias — candidato a problema-raiz, não a chamado recorrente.")

        # ---- MTBF | Recaída por equipe
        e1, e2 = st.columns(2)
        with e1:
            T.section("Itens que falham com mais frequência: horas entre falhas", ico="clock")
            mt = mtbf[mtbf["episodios"] >= 3]["mtbf_h"].dropna().sort_values().head(10)
            if not mt.empty:
                V.plot(V.simple_hbar(mt.round(1), height=360, sufixo=" h", casas=1, inverter=True,
                                     cor_fn=lambda v: RISK_RED if v < 24 else
                                     (RISK_YELLOW if v < 72 else RISK_GREEN)), key=f"{PAGE}_mtbf")
                st.caption("Mediana de horas entre episódios de falha (aberturas a menos de 30 min "
                           "contam como o mesmo episódio). Vermelho: falha mais de uma vez por dia · "
                           "amarelo: a cada 1–3 dias · verde: acima de 3 dias. ICs com 3+ episódios.")
            else:
                st.info("Nenhum IC com 3 ou mais episódios de falha na janela.")
        with e2:
            T.section("% de incidentes que voltaram em até 24 h após resolvidos, por equipe", ico="users")
            trat = ic30[(ic30["Status"] != "Sem Intervenção") & _res(ic30).notna()]
            if not trat.empty:
                rec = trat.groupby("Grupo designado")["_recaida24"].agg(["mean", "size"])
                rec = (rec[rec["size"] >= 10]["mean"] * 100).sort_values(ascending=False).head(10)
                if not rec.empty:
                    V.plot(V.simple_hbar(rec.round(1), height=360, sufixo="%", casas=1,
                                         cor_fn=lambda v: V.cor_nivel(v, 10, 25)), key=f"{PAGE}_recaida")
                    st.caption("% dos incidentes tratados pela equipe (com intervenção) em que o mesmo IC "
                               "voltou a abrir incidente em até 24 h após a resolução. Vermelho >25% · "
                               "amarelo 10–25% · verde <10%. Equipes com 10+ incidentes.")
                else:
                    st.info("Nenhuma equipe com volume suficiente (10+) para medir recaída.")
            else:
                st.info("Sem incidentes tratados com IC na janela.")

        # ---- Padrão IC × dia | Taxa semanal
        p1, p2 = st.columns(2)
        with p1:
            T.section("Em quais dias cada item falhou (14 dias)", ico="calendar")
            ic14 = ic30[ic30["Aberto"] >= ref - pd.Timedelta(days=13)]
            top_ic = ic14["_ic"].value_counts().head(8).index
            if len(top_ic):
                hm = pd.crosstab(ic14[ic14["_ic"].isin(top_ic)]["_ic"],
                                 ic14[ic14["_ic"].isin(top_ic)]["Aberto"].dt.normalize())
                hm = hm.reindex(index=top_ic,
                                columns=pd.date_range(ref - pd.Timedelta(days=13), ref, freq="D"),
                                fill_value=0)
                hm.columns = hm.columns.strftime("%d/%m")
                V.plot(V.heatmap(hm, scale=CHART_SCALE_LOAD, height=360), key=f"{PAGE}_ic_dia")
                st.caption("Linha cheia todos os dias = falha crônica (problema-raiz). Bloco isolado "
                           "= surto pontual (mudança ou evento). O tratamento é diferente.")
            else:
                st.info("Sem ICs recorrentes nos últimos 14 dias.")
        with p2:
            T.section("% de incidentes repetidos no mesmo item, por semana", ico="trend")
            ic91 = _ic_base(_janela(df, 91))
            if not ic91.empty:
                w = ic91[ic91["Aberto"] >= ref - pd.Timedelta(days=83)].copy()
                w["_rep"] = (w["_gap_h"] <= 168).astype(int)
                w["_sem"] = (w["Aberto"] - pd.to_timedelta(w["Aberto"].dt.dayofweek, unit="D")).dt.normalize()
                todos = w.groupby("_sem")["_rep"].mean() * 100
                humano = w[w["Status"] != "Sem Intervenção"].groupby("_sem")["_rep"].mean() * 100
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=todos.index.strftime("%d/%m"), y=todos.values,
                                         mode="lines+markers", name="Todos",
                                         line=dict(color=NAVY_LIGHT, width=2.5),
                                         hovertemplate="semana de %{x}<br>%{y:.1f}%<extra></extra>"))
                fig.add_trace(go.Scatter(x=humano.reindex(todos.index).index.strftime("%d/%m"),
                                         y=humano.reindex(todos.index).values,
                                         mode="lines+markers", name="Com intervenção humana",
                                         line=dict(color=RED, width=2.5),
                                         hovertemplate="semana de %{x}<br>%{y:.1f}%<extra></extra>"))
                fig.update_layout(xaxis_title="semana (início)", yaxis_title="% reincidente em 7 dias")
                fig.update_yaxes(ticksuffix="%")
                V.plot(V.style_fig(fig, height=360, legend=True, legend_top=True), key=f"{PAGE}_rep_sem")
                st.caption("% dos incidentes cujo IC já tinha falhado nos 7 dias anteriores. Linha "
                           "vermelha subindo = o time está apagando o mesmo incêndio. A última semana "
                           f"vai até {V.REF_DATE_STR} (parcial).")
            else:
                st.info("Sem ICs para calcular a série semanal.")

        # ---- Tempestades | Temas que mais reincidem
        t1, t2 = st.columns(2)
        with t1:
            T.section("Incidentes que geraram mais chamados duplicados", ico="alert")
            pai = V._clean_dim(base30, "Incidente Pai", "incidente_pai")
            if pai.notna().any():
                pai = pai[pai.notna() & (pai != base30["Número"].astype(str))]
                cont = pai.value_counts().head(10)
                V.plot(V.simple_hbar(cont, height=360, cor_fn=_cor_relativa(cont.max())),
                       key=f"{PAGE}_tempestade")
                st.caption(f"O maior pai da janela arrastou **{V.br(int(cont.iloc[0]))}** filhos. "
                           "Resolver a causa do pai fecha o lote inteiro — é onde o NOC ganha escala.")
            else:
                st.info("Sem `Incidente Pai` preenchido na janela.")
        with t2:
            T.section("Tipos de problema que mais se repetem no mesmo item", ico="brain")
            tic = data_prep.com_tema(ic30)
            if not tic.empty:
                tic = tic.sort_values(["_ic", "_tema", "Aberto"])
                tic["_g"] = tic.groupby(["_ic", "_tema"])["Aberto"].diff().dt.total_seconds() / 3600
                tr = tic.assign(_rep=(tic["_g"] <= 168)).groupby("_tema")["_rep"].agg(["mean", "size"])
                tr = (tr[tr["size"] >= 10]["mean"] * 100).sort_values(ascending=False).head(8)
                if not tr.empty:
                    V.plot(V.simple_hbar(tr.round(1), height=360, sufixo="%", casas=1,
                                         cor_fn=lambda v: V.cor_nivel(v, 30, 60)), key=f"{PAGE}_tema_rep")
                    st.caption("% dos incidentes de cada tema em que o mesmo IC já tinha o mesmo tema "
                               "nos 7 dias anteriores. Vermelho >60% · amarelo 30–60% · verde <30%.")
                else:
                    st.info("Temas sem volume suficiente (10+) com IC na janela.")
            else:
                st.info("Sem `cluster_nlp` para os incidentes com IC.")

    st.divider()
    _backlog_problema_raiz(base30, ic30)

    st.divider()
    T.section("Como os chamados foram fechados e quanto tempo tomaram", ico="doc")
    q1, q2 = st.columns(2)
    with q1:
        T.section("Chamados por código de fechamento (30 dias)", ico="doc")
        if not base30.empty and "Código de fechamento" in base30.columns:
            cf = base30["Código de fechamento"].value_counts().head(10)
            V.plot(V.simple_hbar(cf, height=360, cor_fn=_cor_relativa(cf.max() if len(cf) else 0)),
                   key=f"{PAGE}_cf")
            if "tem_resolucao" in base30.columns:
                doc = pd.to_numeric(base30["tem_resolucao"], errors="coerce").mean()
                st.caption(f"{V.br((doc or 0) * 100, 1, '%')} dos chamados dos últimos 30 dias "
                           f"têm solução documentada. Fechamento sem documentação alimenta "
                           f"reincidência.")
        else:
            st.info("Sem código de fechamento na janela.")
    with q2:
        T.section("Categorias que mais consomem horas do NOC (30 dias)", ico="clock")
        if not jan.empty and "Categoria" in jan.columns:
            tempo = (jan.groupby("Categoria")["_dur_h"].agg(horas="sum", incidentes="count")
                     .sort_values("horas", ascending=False).head(10))
            V.plot(V.simple_hbar(tempo["horas"], height=360, sufixo=" h", casas=0,
                                 cor_fn=_cor_relativa(tempo["horas"].max())), key=f"{PAGE}_cat_tempo")
            st.caption("Soma das horas de resolução por categoria nos últimos 30 dias — "
                       "volume alto com resolução curta pesa menos que volume baixo e demorado.")
        else:
            st.info("Sem categoria nas resoluções da janela.")


# ============================================================================
def _backlog_problema_raiz(base30: pd.DataFrame, ic30: pd.DataFrame):
    """Painel de ação por tipo de problema, lido como backlog de Problem Management.

    Veio do Painel Gerencial. Aqui ganhou os sinais SRE da aba (reincidência no
    mesmo IC, violação de KPI, tendência da semana) e uma prioridade de ação.
    """
    ref = V.REF_DATE
    T.section("O que resolver na causa raiz: ação sugerida por tipo de problema",
              sub="últimos 30 dias · `cluster_nlp` + sinais de reincidência e OLA", ico="target")
    tema_b = data_prep.com_tema(base30)
    if tema_b.empty:
        st.info("Sem temas de `cluster_nlp` na janela para montar o backlog.")
        return

    perfil = data_prep.perfil_temas_de(tema_b)
    dia_n = tema_b["Aberto"].dt.normalize()
    u7 = tema_b[dia_n > ref - pd.Timedelta(days=7)]["_tema"].value_counts() / 7
    a21 = tema_b[(dia_n <= ref - pd.Timedelta(days=7)) &
                 (dia_n > ref - pd.Timedelta(days=28))]["_tema"].value_counts() / 21
    tend = pd.DataFrame({"u": u7, "a": a21}).fillna(0)
    tend = pd.Series(np.where(tend["a"] > 0, (tend["u"] / tend["a"].where(tend["a"] > 0) - 1) * 100,
                              np.nan), index=tend.index)
    p12 = tema_b.groupby("_tema")["_P"].apply(lambda x: x.isin(["P1", "P2"]).mean() * 100)

    rep = pd.Series(dtype=float)
    if ic30 is not None and not ic30.empty:
        tic = data_prep.com_tema(ic30)
        if not tic.empty:
            tic = tic.sort_values(["_ic", "_tema", "Aberto"])
            tic["_g"] = tic.groupby(["_ic", "_tema"])["Aberto"].diff().dt.total_seconds() / 3600
            r = tic.assign(_rep=(tic["_g"] <= 168)).groupby("_tema")["_rep"].agg(["mean", "size"])
            rep = r[r["size"] >= 10]["mean"] * 100

    viol = pd.Series(dtype=float)
    if {"Entrou para KPI?", "KPI Violado?"} <= set(tema_b.columns):
        el = tema_b[tema_b["Entrou para KPI?"] == "SIM"]
        if not el.empty:
            v = el.assign(_v=(el["KPI Violado?"] == "SIM")).groupby("_tema")["_v"].agg(["mean", "size"])
            viol = v[v["size"] >= 10]["mean"] * 100

    b = perfil.copy()
    b["p12"] = p12
    b["tend"] = tend
    b["rep"] = rep
    b["viol"] = viol
    mediana = b["incidentes"].median()

    def _acao(l):
        score, acoes = 0, []
        if pd.notna(l["viol"]) and l["viol"] > 2 * (100 - META_KPI):
            score += 3; acoes.append("OLA quebrando: revisar fluxo e escalonamento")
        if pd.notna(l["rep"]) and l["rep"] > 60:
            score += 3; acoes.append("Causa raiz: o mesmo IC volta a falhar")
        if l["pct_com_pai"] > 30:
            score += 2; acoes.append("Agrupar repetições em Problem Record")
        if l["saturacao"]:
            score += 2; acoes.append("Capacity planning preventivo")
        if l["p12"] > 20:
            score += 2; acoes.append("Escalonamento antecipado")
        if pd.notna(l["tend"]) and l["tend"] > 50:
            score += 2; acoes.append("Em alta: investigar mudança recente")
        if l["incidentes"] > mediana and l["p12"] < 5:
            score += 1; acoes.append("Suprimir ou agregar alertas")
        prio = "Alta" if score >= 5 else ("Média" if score >= 3 else "Baixa")
        return pd.Series({"score": score, "Prioridade": prio,
                          "Ação sugerida": " · ".join(acoes) if acoes else "Acompanhar"})

    b = b.join(b.apply(_acao, axis=1))
    b = b.sort_values(["score", "horas_estimadas"], ascending=False)
    vista = b.reset_index().rename(columns={
        "_tema": "Tipo de problema", "incidentes": "Incidentes", "p12": "% P1/P2",
        "pct_com_pai": "% repetição (pai)", "rep": "% volta no mesmo IC (7d)",
        "viol": "% violação KPI", "tend": "Tendência 7d %", "horas_estimadas": "Horas est."})
    cols = ["Prioridade", "Tipo de problema", "Ação sugerida", "Incidentes", "Horas est.", "% P1/P2",
            "% violação KPI", "% volta no mesmo IC (7d)", "% repetição (pai)", "Tendência 7d %"]
    vista = vista[cols]
    for c in cols[3:]:
        vista[c] = pd.to_numeric(vista[c], errors="coerce").round(1)
    cor_prio = {"Alta": RISK_RED, "Média": RISK_YELLOW, "Baixa": RISK_GREEN}
    _apply = getattr(vista.style, "map", None) or vista.style.applymap
    st.dataframe(_apply(lambda v: (f"background-color:{cor_prio[v]};color:#fff;font-weight:600"
                                   if v in cor_prio else ""), subset=["Prioridade"])
                 .format(precision=1, na_rep="—"),
                 hide_index=True, use_container_width=True)
    n_alta = int((b["Prioridade"] == "Alta").sum())
    st.caption(f"**{V.br(n_alta)} tipo(s) de problema com prioridade alta.** Pontuação: violação de "
               "KPI acima de 2× o orçamento de erro e reincidência no mesmo IC pesam 3; repetição via incidente pai, saturação, "
               "alta criticidade e tendência de alta pesam 2; ruído volumoso pesa 1. "
               "Alta ≥5 · Média 3–4 · Baixa <3.")
    V.csv_download(vista, "Baixar backlog de problema-raiz (CSV)",
                   "noc_backlog_problema_raiz.csv", key=f"{PAGE}_dl_backlog")


# ============================================================================
# CONFIANÇA DOS MODELOS
# ============================================================================
def _aba_modelos():
    s_d1 = _serie_volume("previsao_d1")
    s_d7 = _serie_volume("previsao_d7")
    tt = V.turno_table(load_prediction_table("previsao_turno"))
    met = _metricas_cluster()
    m_d1 = V.metricas_regressao(s_d1["real"], s_d1["previsto"]) if not s_d1.empty else {}
    m_d7 = V.metricas_regressao(s_d7["real"], s_d7["previsto"]) if not s_d7.empty else {}
    m_tt = V.metricas_regressao(tt["_real"], tt["_previsto"]) if not tt.empty else {}

    # ---- risco
    bruto_sla = load_prediction_table("previsao_sla")
    pcol = V.pick_col(bruto_sla, "Probabilidade_Violacao_%", "Probabilidade_Violacao",
                      contains=True) if bruto_sla is not None else None
    vcol = V.pick_col(bruto_sla, "KPI_Violado_Real", "kpi_violado",
                      contains=True) if bruto_sla is not None else None
    av = (pd.DataFrame({"pct": V.as_pct(bruto_sla[pcol]),
                        "real": pd.to_numeric(bruto_sla[vcol], errors="coerce")}).dropna()
          if (pcol and vcol) else pd.DataFrame())
    auc = V.auc_score(av["pct"], av["real"]) if not av.empty else np.nan

    # ---- duração
    prev_dur = load_prediction_table("previsao_duracao")
    rc = V.pick_col(prev_dur, "Duracao_Real", "duracao_real", contains=True) if prev_dur is not None else None
    pc = V.pick_col(prev_dur, "Duracao_Prevista", "duracao_prevista", contains=True) if prev_dur is not None else None
    dur = pd.DataFrame()
    if rc and pc:
        fator = V.dur_to_hours(1.0, PREV_DURACAO_UNIT)
        dur = pd.DataFrame({"real": pd.to_numeric(prev_dur[rc], errors="coerce") * fator,
                            "prev": pd.to_numeric(prev_dur[pc], errors="coerce") * fator}).dropna()
        dur = dur[(dur["real"] >= 0) & (dur["prev"] >= 0)]
        if not dur.empty:
            dur["fr"] = pd.cut(dur["real"], _BINS_DUR, labels=False, right=False)
            dur["fp"] = pd.cut(dur["prev"], _BINS_DUR, labels=False, right=False)
            dur["dist"] = (dur["fp"] - dur["fr"]).abs()
    pct_ate1 = float((dur["dist"] <= 1).mean() * 100) if not dur.empty else np.nan

    # ---- Semáforo
    T.section("Dá para confiar em cada previsão?", ico="shield")

    def _item(titulo, valor, metrica, cor, nota=""):
        veredito = {RISK_GREEN: "Confiável para decidir", RISK_YELLOW: "Usar com cautela",
                    RISK_RED: "Não usar sozinho"}.get(cor, "Sem dados")
        return dict(titulo=titulo, valor=valor, metrica=metrica, cor=cor, veredito=veredito, nota=nota)

    mape_reg = float(met["MAPE"].median()) if not met.empty and met["MAPE"].notna().any() else np.nan
    cor_auc = CINZA if pd.isna(auc) else (RISK_GREEN if auc >= 0.8 else RISK_YELLOW if auc >= 0.7 else RISK_RED)
    cor_dur = CINZA if pd.isna(pct_ate1) else (RISK_GREEN if pct_ate1 >= 80 else
                                              RISK_YELLOW if pct_ate1 >= 60 else RISK_RED)
    V.cartoes_semaforo([
        _item("Volume D+1", V.br(m_d1.get("mape"), 1, "%"), "MAPE", _cor_mape(m_d1.get("mape")),
              f"{V.br(m_d1.get('n'))} dias avaliados" if m_d1 else ""),
        _item("Volume D+7", V.br(m_d7.get("mape"), 1, "%"), "MAPE", _cor_mape(m_d7.get("mape")),
              f"{V.br(m_d7.get('n'))} dias avaliados" if m_d7 else ""),
        _item("Volume por turno", V.br(m_tt.get("mape"), 1, "%"), "MAPE", _cor_mape(m_tt.get("mape")),
              f"{V.br(m_tt.get('n'))} turnos avaliados" if m_tt else ""),
        _item("Demanda por tipo de trabalho", V.br(mape_reg, 1, "%"), "MAPE mediano", _cor_mape(mape_reg),
              f"{V.br(met['cluster'].nunique())} regimes" if not met.empty else ""),
        _item("Risco de OLA", V.br(auc, 2), "AUC", cor_auc,
              f"{V.br(len(av))} incidentes com desfecho" if not av.empty else ""),
        _item("Duração", V.br(pct_ate1, 0, "%"), "até 1 faixa de erro", cor_dur,
              f"{V.br(len(dur))} incidentes" if not dur.empty else ""),
    ])
    st.caption("Critérios: MAPE <10% verde · 10–20% amarelo · >20% vermelho. AUC ≥0,80 verde · "
               "0,70–0,80 amarelo. Duração: ≥80% das previsões a no máximo 1 faixa da real verde · "
               "60–80% amarelo.")

    # ---- Volume
    st.divider()
    T.section("Previsão de volume: quanto o modelo erra", sub="`previsao_d1` · `previsao_d7` · `previsao_turno`",
              ico="trend")
    linhas = []
    for nome, m in [("D+1", m_d1), ("D+7", m_d7), ("Por turno", m_tt)]:
        if m:
            linhas.append({"Modelo": nome, "Pontos avaliados": m["n"],
                           "MAE (incidentes)": round(m["mae"], 1),
                           "MAPE (%)": round(m["mape"], 1) if pd.notna(m["mape"]) else None,
                           "R²": round(m["r2"], 2) if pd.notna(m["r2"]) else None,
                           "Viés médio": round(m["vies"], 1),
                           "% dentro de ±10%": round(m["dentro10"], 0) if pd.notna(m["dentro10"]) else None})
    if linhas:
        tab = pd.DataFrame(linhas)
        _apply = getattr(tab.style, "map", None) or tab.style.applymap
        st.dataframe(_apply(lambda v: (f"background-color:{_cor_mape(v)};color:#fff;font-weight:600"
                                       if pd.notna(v) else ""), subset=["MAPE (%)"])
                     .format(precision=1, na_rep="—"),
                     hide_index=True, use_container_width=True)
        st.caption("Viés positivo = o modelo prevê mais do que acontece (escala sobra); "
                   "negativo = prevê menos (escala falta).")

    v1, v2 = st.columns(2)
    for col, nome, serie, m, key in [(v1, "D+1", s_d1, m_d1, "d1"), (v2, "D+7", s_d7, m_d7, "d7")]:
        with col:
            T.section(f"Incidentes previstos vs reais — {nome} (60 dias)", ico="trend")
            if not serie.empty:
                s60 = serie[serie["data"] >= serie["data"].max() - pd.Timedelta(days=60)]
                banda = min(max((m.get("mape") or 12) / 100, 0.03), 0.6)
                V.plot(V.forecast_line(s60, "data", "real", "previsto", height=340, band_pct=banda),
                       key=f"{PAGE}_vol_{key}")
                st.caption(f"Faixa = ±MAPE ({V.br(banda * 100, 0, '%')}). Real fora da faixa = dia "
                           "atípico que merece explicação.")
            else:
                st.info(f"Tabela `previsao_{key}` indisponível.")

    w1, w2 = st.columns(2)
    with w1:
        T.section("Erro da previsão em cada turno (%)", ico="clock")
        if not tt.empty:
            mt = {t.split(" (")[0]: V.metricas_regressao(g["_real"], g["_previsto"]).get("mape")
                  for t, g in tt.groupby("_turno")}
            mt = pd.Series(mt).reindex([t.split(" (")[0] for t in V.TURNOS4]).dropna()
            if not mt.empty:
                V.plot(V.bar_niveis(mt.index, mt.values, [_cor_mape(v) for v in mt.values],
                                    height=320, sufixo="%", linha=10, rotulo_linha="10%",
                                    titulo_y="MAPE"), key=f"{PAGE}_mape_turno")
                st.caption("Turno vermelho: planejar escala com folga — a previsão ali é menos precisa.")
        else:
            st.info("Tabela `previsao_turno` indisponível.")
    with w2:
        T.section("Erro da previsão D+1 por dia da semana (%)", ico="calendar")
        if m_d1:
            s = s_d1.dropna(subset=["real"])
            s = s[s["real"] > 0]
            s = s.assign(_err=(s["previsto"] - s["real"]).abs() / s["real"] * 100,
                         _dow=s["data"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA))))
            md = s.groupby("_dow")["_err"].mean().reindex(DIAS_SEMANA).dropna()
            V.plot(V.bar_niveis([d[:3] for d in md.index], md.values, [_cor_mape(v) for v in md.values],
                                height=320, sufixo="%", linha=10, rotulo_linha="10%",
                                titulo_y="MAPE"), key=f"{PAGE}_mape_dow")
            st.caption("Segunda-feira e véspera de feriado costumam concentrar o erro "
                       "(represamento do fim de semana).")
        else:
            st.info("Sem pares previsto × real em `previsao_d1`.")

    # ---- Regime
    st.divider()
    T.section("Erro da previsão por tipo de trabalho", sub="`metricas_previsao_por_cluster`",
              ico="layers")
    if not met.empty:
        k1, k2 = st.columns(2)
        with k1:
            T.section("Erro médio (%) por tipo de trabalho e horizonte", ico="grid")
            hm = met.pivot_table(index="cluster", columns="horizonte", values="MAPE", aggfunc="mean").round(1)
            V.plot(V.heatmap(hm, scale=CHART_SCALE_RISK, height=320, value_fmt="%{z:.1f}%"),
                   key=f"{PAGE}_mape_reg")
            st.caption("Verde = erro percentual baixo. Comparável entre regimes de volumes "
                       "diferentes, ao contrário do MAE.")
        with k2:
            T.section("Modelo usado em cada previsão e suas métricas", ico="doc")
            vista = met.rename(columns={"cluster": "Regime", "horizonte": "Horizonte",
                                        "escolhido": "Modelo escolhido", "MAPE": "MAPE (%)"})
            _apply = getattr(vista.style, "map", None) or vista.style.applymap
            st.dataframe(_apply(lambda v: (f"background-color:{_cor_mape(v)};color:#fff;font-weight:600"
                                           if pd.notna(v) else ""), subset=["MAPE (%)"])
                         .format({"MAE": "{:.1f}", "RMSE": "{:.1f}", "R2": "{:.2f}", "MAPE (%)": "{:.1f}"},
                                 na_rep="—"),
                         hide_index=True, use_container_width=True)
            st.caption("Cada regime usa o estimador que venceu na validação. Onde um estimador "
                       "simples ganhou do ML, ele foi mantido.")
    else:
        st.info("Tabela `metricas_previsao_por_cluster` indisponível.")

    # ---- Risco
    st.divider()
    T.section("O modelo de risco de OLA acerta?", sub="`previsao_sla` × `KPI_Violado_Real`", ico="shield")
    if not av.empty:
        flag = av["pct"] >= 75
        base = float(av["real"].mean() * 100)
        precisao = float(av.loc[flag, "real"].mean() * 100) if flag.any() else np.nan
        recall = (float(flag[av["real"] >= 1].mean() * 100) if (av["real"] >= 1).any() else np.nan)
        brier = float(((av["pct"] / 100 - av["real"]) ** 2).mean())
        kc = st.columns(4)
        kc[0].metric("AUC", V.br(auc, 2), delta="0,5 = aleatório · 1 = perfeito", delta_color="off")
        kc[1].metric("Precisão no corte 75%", V.br(precisao, 1, "%"),
                     delta=f"taxa base {V.br(base, 1, '%')}", delta_color="off")
        kc[2].metric("Recall no corte 75%", V.br(recall, 1, "%"),
                     delta="violações que o alerta pega", delta_color="off")
        kc[3].metric("Brier score", V.br(brier, 3), delta="menor é melhor", delta_color="off")
        st.caption(f"Precisão: dos incidentes marcados acima de 75%, quantos violaram de fato "
                   f"(compare com a taxa base de {V.br(base, 1, '%')}). Recall: das violações reais, "
                   "quantas estavam acima de 75%.")

        m1, m2 = st.columns(2)
        with m1:
            T.section("Risco previsto vs % que realmente violou o OLA", ico="gauge")
            cortes = [0, 10, 25, 50, 75, 90, 100]
            rotulos = ["0-10%", "10-25%", "25-50%", "50-75%", "75-90%", "90-100%"]
            av["_faixa"] = pd.cut(av["pct"], bins=cortes, labels=rotulos, include_lowest=True)
            cal = (av.groupby("_faixa", observed=True)["real"].agg(taxa="mean", n="size").dropna())
            cal["taxa"] = cal["taxa"] * 100
            if not cal.empty:
                V.plot(V.calibration_chart(cal.index, cal["taxa"], cal["n"], height=340),
                       key=f"{PAGE}_calib")
                st.caption("Se as barras crescem da esquerda para a direita, a ordem do risco é "
                           "confiável: dá para trabalhar a fila de cima para baixo.")
        with m2:
            T.section("Quantos incidentes revisar para pegar a maioria das violações", ico="trend")
            ordenado = av.sort_values("pct", ascending=False).reset_index(drop=True)
            total_viol = ordenado["real"].sum()
            if total_viol > 0:
                capt = ordenado["real"].cumsum() / total_viol * 100
                fila = (ordenado.index + 1) / len(ordenado) * 100
                passo = max(1, len(ordenado) // 200)
                V.plot(V.gain_curve(fila[::passo], capt[::passo], height=340), key=f"{PAGE}_ganho")
                alvo = ordenado[capt >= 80]
                if not alvo.empty:
                    pct_fila = (alvo.index[0] + 1) / len(ordenado) * 100
                    st.caption(f"Revisando os **{V.br(pct_fila, 1, '%')} de maior risco**, a operação "
                               "alcança 80% de todas as violações.")
            else:
                st.info("Sem violações registradas no conjunto avaliado.")
    else:
        st.info("`previsao_sla` sem a coluna de violação real — avaliação indisponível.")

    # ---- Duração
    st.divider()
    T.section("O modelo de duração acerta?", sub="`previsao_duracao`", ico="clock")
    if not dur.empty:
        erro_abs = (dur["prev"] - dur["real"]).abs()
        kd = st.columns(4)
        kd[0].metric("Na faixa certa", V.br((dur["dist"] == 0).mean() * 100, 1, "%"))
        kd[1].metric("Até 1 faixa de distância", V.br(pct_ate1, 1, "%"))
        kd[2].metric("Subestimados", V.br((dur["fp"] < dur["fr"]).mean() * 100, 1, "%"),
                     delta="previsão abaixo da faixa real", delta_color="off")
        kd[3].metric("Erro absoluto mediano", V.fmt_hours(float(erro_abs.median())))
        st.caption("Faixas: " + " · ".join(_ROT_DUR) + ". Subestimar é o erro caro: o incidente "
                   "parece rápido e estoura o OLA.")

        x1, x2 = st.columns(2)
        with x1:
            T.section("% de acerto da duração, por faixa de tempo real", ico="target")
            dur["_ac"] = np.select([dur["dist"] == 0, dur["dist"] == 1],
                                   ["Faixa certa", "Errou 1 faixa"], "Errou 2+ faixas")
            n_f = dur.groupby("fr").size()
            pz = pd.crosstab(dur["fr"], dur["_ac"], normalize="index") * 100
            pz = pz.reindex(columns=[c for c in ["Faixa certa", "Errou 1 faixa", "Errou 2+ faixas"]
                                     if c in pz.columns])
            pz = pz.sort_index(ascending=False).round(1)
            pz.index = [f"{_ROT_DUR[int(i)]} (n={V.br(int(n_f.get(i, 0)))})" for i in pz.index]
            V.plot(V.stacked_hbar(pz, colors={"Faixa certa": RISK_GREEN, "Errou 1 faixa": RISK_YELLOW,
                                              "Errou 2+ faixas": RISK_RED},
                                  height=360, sufixo="%", rotulos=True), key=f"{PAGE}_dur_faixa")
            st.caption("Cada linha é uma faixa de duração REAL. Mostra em que tipo de incidente "
                       "o modelo acerta e em qual não dá para confiar.")
        with x2:
            T.section("Duração prevista vs real, por faixa de tempo", ico="chart")
            md = dur.groupby("fr").agg(real=("real", "median"), prev=("prev", "median"))
            md.index = [_ROT_DUR[int(i)] for i in md.index]
            fig = V.grouped_bar(md.index, {"Real (mediana)": md["real"].clip(lower=0.01),
                                           "Previsto (mediana)": md["prev"].clip(lower=0.01)},
                                height=360, colors={"Real (mediana)": NAVY_LIGHT,
                                                    "Previsto (mediana)": RED})
            fig.update_yaxes(type="log", title="horas (escala log)")
            V.plot(fig, key=f"{PAGE}_dur_mediana")
            st.caption("Vermelha acima da azul = superestima; abaixo = subestima. O padrão típico é "
                       "o modelo puxar tudo para o meio: superestima o rápido e subestima o longo.")
    else:
        st.info("Tabela `previsao_duracao` indisponível.")
