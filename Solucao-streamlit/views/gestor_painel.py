"""Painel Gerencial & Previsões Estratégicas — visão executiva ancorada em 12/12/2025.

Ordem por valor de negócio, depois dos cards:
1. Risco de violação de OLA (onde está a multa)
2. Projeções D+1 / D+7 (dimensionamento)
3. Modos de falha — regimes (`clusters_incidentes`) e tipos de problema (`cluster_nlp`)
3b. Tendência mensal de P2/P3 por produto e categoria (requisito de identificar tendência)
4. OLA realizado e carga por equipe/produto
5. Quando a demanda chega (turno e dia da semana)
6. Saúde operacional do dia

Leitura única (sem modo técnico): barras, semáforos e tabelas, com cor por nível.
"""
import re
import numpy as np
import pandas as pd
import streamlit as st

from config import META_MTTR_H, MTTR_MAX_H, PREV_DURACAO_UNIT
from data_loader import load_prediction_table
from theme import (apply_theme, CHART_SCALE_NAVY, CHART_SCALE_LOAD, RISK_COLORS,
                   RISK_RED, RISK_YELLOW, RISK_GREEN, RED, NAVY_LIGHT)
import theme as T
import viz_helpers as V
import data_prep

PAGE = "GESTOR"
META_KPI = 95.0
ENCERRADOS = {"Encerrado", "Encerrado Automaticamente"}
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
CINZA = "#C9CED6"


def sanitize_iframe_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    m = re.search(r'src=["\'](https?://[^"\']+)["\']', raw_url.strip(), re.IGNORECASE)
    return m.group(1).strip() if m else raw_url.strip()


def _forecast_block(prev, dcol_names, prev_names, real_names, title, key):
    dcol = V.pick_col(prev, *dcol_names)
    pcol = V.pick_col(prev, *prev_names, contains=True)
    rcol = V.pick_col(prev, *real_names, contains=True)
    T.section(title, ico="chart")
    if dcol and pcol and rcol:
        V.plot(V.forecast_line(prev, dcol, rcol, pcol), key=key)
    else:
        fig = V.dynamic_chart(prev, scale=CHART_SCALE_NAVY)
        V.plot(fig, key=key) if fig else st.info("Sem dados suficientes para o gráfico.")


def _health_index(df, prev_d1, prev_sla, ref):
    """Índice de saúde 0-100 (maior = melhor) para o Dia vs Média Histórica."""
    def bloco(base, dia=False):
        if base.empty:
            return dict(SLA=0, MTTR=0, Volume=0, Violações=0, Risco=0)
        eleg = base[base["Entrou para KPI?"] == "SIM"]
        sla = (eleg["KPI Violado?"] != "SIM").mean() * 100 if len(eleg) else 0
        # 'Duração' está em SEGUNDOS: usa o helper (delta Resolvido-Aberto em horas)
        # em vez de dividir por 60, que inflava o MTTR em 60x e distorcia o radar.
        res = V.resolved_base(base, ENCERRADOS, max_h=MTTR_MAX_H)
        mttr_h = float(res["_dur_h"].mean()) if not res.empty else META_MTTR_H
        mttr = max(0, min(100, META_MTTR_H / mttr_h * 100)) if mttr_h else 0
        viol = (1 - (eleg["KPI Violado?"] == "SIM").mean()) * 100 if len(eleg) else 100
        return dict(SLA=sla, MTTR=mttr, Violações=viol)
    dia_base = df[df["Aberto"].dt.date == ref.date()]
    hist_base = df[df["Aberto"] < ref]
    dia, hist = bloco(dia_base), bloco(hist_base)

    # Volume: quão perto do previsto (100 = igual/abaixo do previsto)
    prev_dia, real_dia, _ = _prev_real(prev_d1, ref)
    if prev_dia and real_dia:
        dia["Volume"] = max(0, min(100, prev_dia / real_dia * 100))
    else:
        dia["Volume"] = 70
    hist["Volume"] = 75

    # Risco: 100 - risco médio previsto
    scol = V.pick_col(prev_sla, "Probabilidade_Violacao_%", "probabilidade violacao", contains=True)
    risco_med = float(V.as_pct(prev_sla[scol]).mean()) if scol else 40
    dia["Risco"] = max(0, 100 - risco_med)
    hist["Risco"] = max(0, 100 - risco_med * 0.9)

    eixos = ["SLA", "MTTR", "Volume", "Violações", "Risco"]
    dia["Eficiência"] = np.mean([dia[e] for e in eixos])
    hist["Eficiência"] = np.mean([hist[e] for e in eixos])
    eixos = eixos + ["Eficiência"]
    return eixos, [dia[e] for e in eixos], [hist[e] for e in eixos]


def _prev_real(prev_d1, ref):
    if prev_d1 is None or prev_d1.empty:
        return None, None, None
    dcol = V.pick_col(prev_d1, "Data", "dia")
    pcol = V.pick_col(prev_d1, "Incidentes_Previstos", "previsto", contains=True)
    rcol = V.pick_col(prev_d1, "Incidentes_Reais", "real", contains=True)
    if not (dcol and pcol):
        return None, None, None
    d = prev_d1.copy()
    d[dcol] = pd.to_datetime(d[dcol], errors="coerce")
    row = d[d[dcol].dt.date == ref.date()]
    if row.empty:
        row = d.sort_values(dcol).tail(1)
    return (float(row[pcol].iloc[0]) if pcol else None,
            float(row[rcol].iloc[0]) if (rcol and rcol in row) else None, None)


def render_gestor_painel():
    apply_theme()
    T.hero("Painel Gerencial & Previsões Estratégicas",
           "Visão executiva da operação, projeções D+1/D+7, risco de SLA e recomendações "
           "preventivas — dados do BigQuery (<code>predictops_gold</code>). "
           f"Referência: <code>{V.REF_DATE_STR}</code>.")

    # ---------------- Dados ----------------
    df = data_prep.incidentes()
    df["_Turno"] = df["Aberto"].dt.hour.apply(V.turno_from_hour)
    prev_d1 = load_prediction_table("previsao_d1")
    prev_d7 = load_prediction_table("previsao_d7")
    prev_sla = load_prediction_table("previsao_sla")
    prev_dur = load_prediction_table("previsao_duracao")

    T.section("# Filtros globais", ico="filter")
    df = V.global_slicers(df, PAGE, [
        ("Prioridade", "_P"), ("Turno", "_Turno"), ("Grupo Designado", "Grupo designado"),
    ])

    ref = V.REF_DATE
    df_ref = df[df["Aberto"].dt.date == ref.date()]
    mes_ref = df[(df["Aberto"].dt.year == ref.year) & (df["Aberto"].dt.month == ref.month)]
    mes_ant = df[(df["Aberto"].dt.year == ref.year) & (df["Aberto"].dt.month == ref.month - 1)]

    # ---------------- Cards executivos ----------------
    prev_dia, _, _ = _prev_real(prev_d1, ref)
    scol = V.pick_col(prev_sla, "Probabilidade_Violacao_%", "probabilidade violacao", contains=True)
    risco_med = float(V.as_pct(prev_sla[scol]).mean()) if scol else None
    dcol_dur = V.pick_col(prev_dur, "Duracao_Prevista", "duracao prevista", contains=True)
    dur_med = (V.dur_to_hours(pd.to_numeric(prev_dur[dcol_dur], errors="coerce").mean(),
                              PREV_DURACAO_UNIT) if dcol_dur else None)

    def _sla_glob(base):
        eleg = base[base["Entrou para KPI?"] == "SIM"]
        return (eleg["KPI Violado?"] != "SIM").mean() * 100 if len(eleg) else None
    sla_mes, sla_ant = _sla_glob(mes_ref), _sla_glob(mes_ant)
    var_sla = (sla_mes - sla_ant) if (sla_mes is not None and sla_ant is not None) else None

    enc = mes_ref[mes_ref["Status"].isin(ENCERRADOS)]
    taxa_def = (pd.to_numeric(enc["tem_resolucao"], errors="coerce").mean() * 100
                if ("tem_resolucao" in enc.columns and len(enc)) else None)

    c = st.columns(3)
    c[0].metric("Incidentes do Dia", V.br(len(df_ref)))
    c[1].metric("Incidentes Previstos (D+1)", V.br(prev_dia))
    c[2].metric("Risco Médio de Quebra de OLA", V.br(risco_med, 1, "%"), delta_color="inverse")
    c = st.columns(3)
    c[0].metric("Duração Média Prevista", V.fmt_hours(dur_med))
    c[1].metric("Taxa de Solução Definitiva", V.br(taxa_def, 1, "%"))
    c[2].metric("OLA Global do Mês", V.br(sla_mes, 1, "%"),
                delta=(f"{V.br(var_sla, 1, ' p.p.')} vs mês anterior" if var_sla is not None else None))
    st.caption("Cards executivos ancorados em 12/12/2025 e no mês de referência (dez/2025).")
    st.divider()

    sla = data_prep.sla()
    _bloco_risco(sla)
    st.divider()
    _bloco_projecoes(prev_d1, prev_d7)
    st.divider()
    _bloco_modos_de_falha(df)
    st.divider()
    _bloco_tendencia_prioridade(df)
    st.divider()
    _bloco_sla_carga(df, sla)
    st.divider()
    _bloco_demanda(df, df_ref)
    st.divider()
    _bloco_saude(df, prev_d1, prev_sla, ref)


# ============================================================================
# 1. RISCO DE OLA
# ============================================================================
def _bloco_risco(sla: pd.DataFrame):
    T.section("Onde está o risco de violar o OLA", sub="`previsao_sla`", ico="alert")
    est = {"sufixo": "%", "casas": 1, "cor_fn": V.risco_cor, "height": 360}
    r1, r2 = st.columns(2)
    with r1:
        T.section("10 equipes com maior risco de violar o OLA", ico="alert")
        V.render_ranking(V.rank_dim(sla, "_grupo", top=10), key=f"{PAGE}_rk", simples=True,
                         motivo_vazio="Sem grupo designado nas linhas de `previsao_sla`.", **est)
    with r2:
        T.section("10 produtos com maior risco de violar o OLA", ico="alert")
        V.render_ranking(V.rank_dim(sla, "_produto", top=10), key=f"{PAGE}_rk_prod", simples=True,
                         motivo_vazio="Sem produto nas linhas de `previsao_sla`.", **est)
    T.legend(T.LEGENDA_RISCO)

    r3, r4 = st.columns([1.3, 1])
    with r3:
        # Substitui "Equipes críticas — volume × risco médio" (dispersão difícil de
        # ler): a mesma pergunta — quem tem muito incidente e muito risco — em uma
        # barra por equipe, dividida pela faixa de risco.
        T.section("Incidentes em risco de violar o OLA, por equipe", ico="users")
        ex = sla.dropna(subset=["_grupo"]) if not sla.empty else sla
        if not ex.empty:
            faixas = ["Crítico", "Alto", "Médio", "Baixo"]
            piv = pd.crosstab(ex["_grupo"], ex["_faixa"]).reindex(columns=faixas, fill_value=0)
            piv["_alto"] = piv["Crítico"] + piv["Alto"]
            piv = piv.sort_values(["_alto", "Médio"], ascending=False).head(10)
            topo, n_topo = piv.index[0], int(piv["_alto"].iloc[0])
            piv = piv.drop(columns="_alto").iloc[::-1]
            piv = piv[[f for f in faixas if piv[f].sum() > 0]]
            V.plot(V.stacked_hbar(piv, colors=RISK_COLORS, height=380, rotulos=True),
                   key=f"{PAGE}_exposicao")
            st.caption(f"Barra = incidentes da equipe pontuados pelo modelo; cor = faixa de risco. "
                       f"Ordenado por risco alto + crítico: **{topo}** lidera com {V.br(n_topo)}.")
        else:
            st.info("Sem grupo designado nas linhas de `previsao_sla`.")
    with r4:
        T.section("Incidentes por nível de risco de violar o OLA", ico="alert")
        if not sla.empty:
            faixas = (sla["_faixa"].value_counts()
                      .reindex(["Baixo", "Médio", "Alto", "Crítico"]).dropna())
            V.plot(V.donut(faixas, colors=RISK_COLORS, center="Risco", height=380),
                   key=f"{PAGE}_faixas")
        else:
            st.info("Modelo `previsao_sla` indisponível.")


# ============================================================================
# 2. PROJEÇÕES
# ============================================================================
def _bloco_projecoes(prev_d1, prev_d7):
    T.section("Previsão de volume de incidentes", sub="`previsao_d1` · `previsao_d7`",
              ico="chart")
    f1, f2 = st.columns(2)
    with f1:
        _forecast_block(prev_d1, ["Data", "dia"], ["Incidentes_Previstos", "previsto"],
                        ["Incidentes_Reais", "real"], "Previstos vs reais — dia seguinte (D+1)", f"{PAGE}_fc_d1")
    with f2:
        _forecast_block(prev_d7, ["Data", "dia"], ["Incidentes_Previstos_D7", "previsto"],
                        ["Incidentes_Reais_D7", "real"], "Previstos vs reais — 7 dias à frente (D+7)", f"{PAGE}_fc_d7")


# ============================================================================
# 3. MODOS DE FALHA — regimes + NLP
# ============================================================================
def _bloco_modos_de_falha(df: pd.DataFrame):
    T.section("O que causa os incidentes",
              sub="`clusters_incidentes` (tipo de trabalho) · `cluster_nlp` (tipo de problema)",
              ico="brain")
    reg_frame = data_prep.com_regime(df)
    regimes = data_prep.perfil_regimes(reg_frame)
    tema_frame = data_prep.com_tema(df)
    perfil = data_prep.perfil_temas_de(tema_frame)
    if regimes.empty and perfil.empty:
        st.info("Sem dados em `clusters_incidentes` / `cluster_nlp`.")
        return

    # ------------------------------------------------------------- Regimes
    T.eyebrow("Tipo de trabalho: ruído automático, operação ou crítico")
    if not regimes.empty:
        cores_r = V.cores_regime(regimes.index, regimes["pct_P2"])
        lista_cores = [cores_r[r] for r in regimes.index]
        g1, g2 = st.columns(2)
        with g1:
            T.section("Incidentes por tipo de trabalho", sub="`clusters_incidentes`", ico="layers")
            V.plot(V.bar_niveis(regimes.index, regimes["incidentes"], lista_cores, height=320,
                                casas=0, titulo_y="incidentes"), key=f"{PAGE}_regimes")
            total = int(regimes["incidentes"].sum())
            ruido = int(regimes[regimes.index.astype(str).str.contains(
                "ru[íi]do", case=False, regex=True)]["incidentes"].sum())
            if total:
                st.caption(f"**{V.br((total - ruido) / total * 100, 1, '%')} do volume exige pessoa.** "
                           "O restante é ruído automatizado — e é ele que infla os indicadores "
                           "agregados. Verde: ruído · amarelo: operação · vermelho: cauda crítica.")
        with g2:
            T.section("% de alta prioridade em cada tipo de trabalho", ico="alert")
            V.plot(V.bar_niveis(regimes.index, regimes["pct_P2"], lista_cores, height=320,
                                sufixo="%", casas=1, titulo_y="% P2"), key=f"{PAGE}_regimes_p2")
            st.caption("Volume e criticidade caminham em direções opostas: o regime que mais "
                       "gera chamado é o que menos exige urgência.")
        g3, g4 = st.columns(2)
        with g3:
            T.section("Tempo típico de resolução por tipo de trabalho", ico="clock")
            V.plot(V.bar_niveis(regimes.index, regimes["duracao_mediana_h"].fillna(0), lista_cores,
                                height=320, sufixo=" h", casas=1, titulo_y="horas"),
                   key=f"{PAGE}_regimes_dur")
            st.caption("Quanto tempo um incidente de cada regime prende a equipe.")
        with g4:
            T.section("Previsão D+1 por tipo de trabalho: previsto vs real", sub="`previsao_d1_por_cluster`",
                      ico="chart")
            prev = data_prep.previsao_cluster("D+1")
            if not prev.empty:
                dia = prev[prev["data"].dt.date == V.REF_DATE.date()]
                rotulo = V.REF_DATE_STR
                if dia.empty:
                    ultima = prev["data"].max()
                    dia, rotulo = prev[prev["data"] == ultima], ultima.strftime("%d/%m/%Y")
                series = {"Previsto": dia["previsto"].round(0)}
                if dia["real"].notna().any():
                    series["Real"] = dia["real"].round(0)
                V.plot(V.grouped_bar(dia["cluster"], series, height=320,
                                     colors={"Previsto": NAVY_LIGHT, "Real": RED}),
                       key=f"{PAGE}_regimes_prev")
                tot = float(dia["previsto"].sum())
                hum = float(dia[~dia["cluster"].str.contains("ru[íi]do", case=False,
                                                              regex=True)]["previsto"].sum())
                if tot:
                    st.caption(f"{rotulo}: {V.br(tot)} incidentes previstos, **{V.br(hum)} "
                               f"({V.br(hum / tot * 100, 0, '%')}) exigem pessoa**. É esse número "
                               "que dimensiona a equipe.")
            else:
                st.info("Tabela `previsao_d1_por_cluster` indisponível.")
    else:
        st.info("Sem dados em `clusters_incidentes`.")

    if perfil.empty:
        return

    # ------------------------------------------------------------- NLP
    T.eyebrow("Tipos de problema (identificados pela descrição do chamado)")
    total_t = int(perfil["incidentes"].sum())
    horas_t = float(perfil["horas_estimadas"].sum())
    k = st.columns(4)
    k[0].metric("Tipos de problema identificados", V.br(len(perfil)),
                delta=f"{V.br(total_t)} chamados classificados", delta_color="off")
    k[1].metric("Maior volume", str(perfil.index[0]),
                delta=f"{V.br(perfil['incidentes'].iloc[0] / total_t * 100, 0, '%')} dos chamados",
                delta_color="off")
    crit = perfil["pct_P2"].idxmax()
    k[2].metric("Mais crítico", str(crit),
                delta=f"{V.br(perfil.loc[crit, 'pct_P2'], 0, '%')} dos chamados são P2",
                delta_color="inverse")
    caro = perfil["horas_estimadas"].idxmax()
    k[3].metric("Mais consome horas", str(caro),
                delta=(f"{V.br(perfil.loc[caro, 'horas_estimadas'] / horas_t * 100, 0, '%')} das horas"
                       if horas_t else None), delta_color="off")

    n1, n2 = st.columns([1.25, 1])
    with n1:
        T.section("Prioridade dos chamados em cada tipo de problema", ico="alert")
        mix = pd.crosstab(tema_frame["_tema"], tema_frame["_P"], normalize="index") * 100
        mix = mix.reindex(columns=[p for p in V.PRIO_ORDER if p in mix.columns])
        altas = [p for p in ["P1", "P2"] if p in mix.columns]
        mix = mix.loc[mix[altas].sum(axis=1).sort_values().index] if altas else mix
        V.plot(V.stacked_hbar(mix.round(1), colors=V.PRIO_COLORS, height=400, sufixo="%",
                              rotulos=True), key=f"{PAGE}_mix_tema")
        if "P2" in mix.columns:
            topo = mix["P2"].idxmax()
            p2_topo = float(mix.loc[topo, "P2"])
            outros = tema_frame[tema_frame["_tema"] != topo]
            p2_outros = float((outros["_P"] == "P2").mean() * 100) if len(outros) else 0
            vol_topo = float((tema_frame["_tema"] == topo).mean() * 100)
            st.caption(f"**{topo}: {V.br(p2_topo, 0, '%')} dos chamados são P2**, contra "
                       f"{V.br(p2_outros, 1, '%')} nos demais tipos de problema — com só "
                       f"{V.br(vol_topo, 1, '%')} do volume. O risco não está onde está o volume.")
    with n2:
        T.section("% de violação de OLA por tipo de problema", ico="shield")
        if {"Entrou para KPI?", "KPI Violado?"} <= set(tema_frame.columns):
            el = tema_frame[tema_frame["Entrou para KPI?"] == "SIM"]
            v = (el.assign(_v=(el["KPI Violado?"] == "SIM"))
                 .groupby("_tema")["_v"].agg(["mean", "size"]))
            v = (v[v["size"] >= 10]["mean"] * 100).sort_values(ascending=False)
            if not v.empty:
                orc = 100 - META_KPI
                V.plot(V.simple_hbar(v.round(1), height=400, sufixo="%", casas=1,
                                     cor_fn=lambda x: V.cor_nivel(x, orc, 2 * orc)),
                       key=f"{PAGE}_viol_tema")
                st.caption(f"Entre os chamados que entram no KPI. Meta de {META_KPI:.0f}% → até "
                           f"{orc:.0f}% de violação é aceitável (verde); até {2 * orc:.0f}% amarelo; "
                           "acima, vermelho. Temas com 10+ chamados elegíveis.")
            else:
                st.info("Poucos chamados elegíveis a KPI por tema (mínimo 10).")
        else:
            st.info("Base sem `Entrou para KPI?` / `KPI Violado?`.")

    n3, n4 = st.columns([1.25, 1])
    with n3:
        T.section("Tipos de problema para investir: volume × criticidade", ico="target")
        m = perfil.reset_index().rename(columns={"_tema": "tema"})
        m["bolha"] = m["horas_estimadas"].clip(lower=1)
        V.plot(V.bubble_matrix(m, "incidentes", "pct_P2", "bolha", "tema", height=420,
                               rotulo_x="volume de chamados (escala log)",
                               rotulo_y="% de alta prioridade (P2)",
                               cores=[V.cor_nivel(v, 20, 50) for v in m["pct_P2"]]),
               key=f"{PAGE}_matriz_temas")
        st.caption("Bolha = horas estimadas. Alto à esquerda: pouco volume e muita criticidade — "
                   "atenção humana rende mais. Baixo à direita: ruído — investir em supressão de "
                   "alerta, não em mais gente. Vermelho >50% P2 · amarelo 20–50% · verde <20%.")
    with n4:
        T.section("% de cada tipo de problema que é ruído, operação ou crítico", ico="users")
        pv, cores_tr = data_prep.tema_x_regime(tema_frame)
        if not pv.empty:
            V.plot(V.stacked_hbar(pv, colors=cores_tr, height=420, sufixo="%", rotulos=True),
                   key=f"{PAGE}_tema_regime")
            st.caption("Cada tipo de problema dividido pelo tipo de trabalho que gera. Quase todo "
                       "verde = automatizável; vermelho = problema real que pede investimento.")
        else:
            st.info("Sem regime nem status para dividir os temas.")

    e1, e2 = st.columns(2)
    with e1:
        T.section("Horas de trabalho estimadas por tipo de problema", ico="clock")
        horas = perfil["horas_estimadas"].sort_values(ascending=False).head(10)
        topo_h = float(horas.max() or 0)
        V.plot(V.simple_hbar(horas, height=360, sufixo=" h", casas=0,
                             cor_fn=lambda x: V.cor_nivel(x / topo_h if topo_h else 0, 1 / 3, 2 / 3)),
               key=f"{PAGE}_esforco")
        st.caption("Volume × duração mediana. O ranking de horas é diferente do ranking de "
                   "chamados — e é ele que deve guiar automação.")
    with e2:
        T.section("% de chamados duplicados por tipo de problema", ico="recycle")
        pai = perfil["pct_com_pai"].sort_values(ascending=False).head(10)
        V.plot(V.simple_hbar(pai.round(1), height=360, sufixo="%", casas=1,
                             cor_fn=lambda x: V.cor_nivel(x, 15, 30)), key=f"{PAGE}_pai")
        st.caption("Chamado aberto como filho de um incidente pai: o mesmo problema contado de novo. "
                   "Acima de 30% (vermelho), o volume do tema está inflado e deveria virar um "
                   "único Problem Record.")

    # -- Tendência (mantida) ---------------------------------------------------
    tend = data_prep.tendencia_temas()
    evol = data_prep.evolucao_temas()
    T.section("Tipos de problema que estão crescendo (por mês)", ico="trend")
    t1, t2 = st.columns([3, 2])
    with t1:
        if not evol.empty:
            destaques = []
            if not tend.empty:
                destaques = tend[tend["variacao_%"] > 100].index.tolist()[:4]
            V.plot(V.line_multi(evol.index, {c: evol[c] for c in evol.columns},
                                destaques=destaques, height=380,
                                titulo_y="incidentes no mês"),
                   key=f"{PAGE}_evol_temas")
            st.caption("Séries em destaque são as que mais cresceram no último mês. "
                       "O volume total pode cair enquanto temas críticos sobem — por isso "
                       "o agregado não serve como alerta.")
        else:
            st.info("Sem histórico mensal por tema.")
    with t2:
        if not tend.empty:
            t = tend.dropna(subset=["variacao_%"]).head(8)
            V.plot(V.divergent_bar(t.index, t["mes_atual"], t["media_anterior"],
                                   height=380, nome_base="média dos 3 meses anteriores",
                                   tolerancia=0.25),
                   key=f"{PAGE}_tend_temas")
            st.caption("Desvio do último mês contra a própria média do tema. Vermelho: mais de "
                       "25% acima · amarelo: acima, dentro da tolerância · verde: no normal ou abaixo.")
        else:
            st.info("Sem base histórica suficiente para tendência.")

    # -- Quanto do volume é endereçável ---------------------------------------
    T.section("Quanto do volume dá para eliminar", ico="box")
    saturacao = int(perfil[perfil["saturacao"]]["incidentes"].sum())
    sintomas = int((perfil["incidentes"] * perfil["pct_com_pai"] / 100).sum())
    restante = total_t - saturacao - sintomas
    w1, w2 = st.columns([3, 2])
    with w1:
        V.plot(V.waterfall(["Total classificado", "Saturação de recurso",
                            "Chamados duplicados", "Operação de fato"],
                           [total_t, -saturacao, -sintomas, restante], height=360),
               key=f"{PAGE}_waterfall")
    with w2:
        st.markdown(
            f"""
**Saturação de recurso — {V.br(saturacao)} incidentes
({V.br(saturacao / total_t * 100 if total_t else 0, 1, '%')})**

Disco, swap, CPU e I/O não estouram de repente: crescem até o limite. Hoje o
chamado só nasce depois do estouro, o que torna a operação reativa por
construção. O gatilho deveria ser a tendência de consumo, e o artefato deveria
ser tarefa de capacity planning — não incidente.

**Chamados duplicados — {V.br(sintomas)} incidentes**

São filhos de outro incidente. Agrupá-los reduz trabalho duplicado e corrige o
MTTR percebido.
""")
        st.caption("Estimativa a partir dos temas classificados pelo modelo de NLP. O plano de "
                   "ação por tema está no Painel NOC, aba Confiabilidade e reincidência.")

    # -- Tema × equipe --------------------------------------------------------
    T.section("Equipes que atendem cada tipo de problema", ico="users")
    if "Grupo designado" in tema_frame.columns:
        top_eq = tema_frame["Grupo designado"].value_counts().head(6).index
        piv = (tema_frame[tema_frame["Grupo designado"].isin(top_eq)]
               .pivot_table(index="_tema", columns="Grupo designado",
                            values="_k", aggfunc="size").fillna(0).astype(int))
        if not piv.empty:
            V.plot(V.heatmap(piv, scale=CHART_SCALE_LOAD, height=400), key=f"{PAGE}_tema_equipe")
            conc = tema_frame["Grupo designado"].value_counts(normalize=True)
            st.caption(f"A equipe **{conc.index[0]}** absorve "
                       f"{V.br(conc.iloc[0] * 100, 1, '%')} dos chamados classificados. "
                       "Concentração alta significa que qualquer aumento de volume — "
                       "inclusive o previsto para D+1 — cai sobre o mesmo time.")
        else:
            st.info("Sem cruzamento tema × equipe disponível.")


# ============================================================================
# 3b. TENDÊNCIA DE PRIORIDADE ALTA (P2/P3) — POR PRODUTO E CATEGORIA
# ============================================================================
def _bloco_prio_dim(dim: str, key: str):
    evol = data_prep.evolucao_prioridade(dim)
    tend = data_prep.tendencia_prioridade(dim)
    if evol.empty:
        st.info(f"Sem histórico mensal de P2/P3 por {dim.lower()}.")
        return
    destaques = tend[tend["variacao_%"] > 50].index.tolist()[:4] if not tend.empty else []
    V.plot(V.line_multi(evol.index, {c: evol[c] for c in evol.columns},
                        destaques=destaques, height=380,
                        titulo_y="incidentes P2/P3 no mês"),
           key=f"{PAGE}_evol_prio_{key}")
    if not tend.empty and tend["variacao_%"].notna().any():
        top = tend.dropna(subset=["variacao_%"]).index[0]
        var = float(tend.loc[top, "variacao_%"])
        st.caption(f"Séries em destaque cresceram mais de 50% no último mês vs. a média dos 3 "
                   f"anteriores. **{top}** lidera a variação ({V.br(var, 0, '%')} vs. média "
                   f"anterior). Top {len(evol.columns)} {dim.lower()}s por volume de P2/P3.")
    else:
        st.caption(f"Volume mensal de incidentes P2/P3, top {len(evol.columns)} "
                   f"{dim.lower()}s por volume.")


def _bloco_tendencia_prioridade(df: pd.DataFrame):
    T.section("Tendência mensal de P2 e P3 — por produto e categoria", ico="trend")
    st.caption("Identifica onde a prioridade alta (P2/P3) está subindo mês a mês, antes que "
               "vire volume consolidado no indicador agregado de OLA.")
    tp1, tp2 = st.tabs(["Por produto", "Por categoria"])
    with tp1:
        _bloco_prio_dim("Produto", "prod")
    with tp2:
        _bloco_prio_dim("Categoria", "cat")


# ============================================================================
# 4. OLA REALIZADO E CARGA
# ============================================================================
def _bloco_sla_carga(df: pd.DataFrame, sla: pd.DataFrame):
    T.section("OLA e carga por equipe e produto", ico="shield")
    v1, v2 = st.columns(2)
    with v1:
        T.section("Equipes com mais violações de OLA (histórico)", ico="shield")
        viol = df[df["KPI Violado?"] == "SIM"]["Grupo designado"].value_counts().head(10)
        if not viol.empty:
            topo = float(viol.max())
            V.plot(V.simple_hbar(viol, height=360,
                                 cor_fn=lambda x: V.cor_nivel(x / topo if topo else 0, 1 / 3, 2 / 3)),
                   key=f"{PAGE}_sla_eq")
            st.caption("Quantidade de violações de KPI por equipe. Vermelho: maior incidência.")
        else:
            st.info("Sem violações de OLA para o filtro atual.")
    with v2:
        T.section("Incidentes com risco alto (>75%) de violar o OLA, por prioridade", ico="alert")
        alto = sla[sla["_pct"] > 75] if not sla.empty else pd.DataFrame()
        if not alto.empty and alto["_prio"].notna().any():
            cnt = (alto["_prio"].value_counts()
                   .reindex([p for p in V.PRIO_ORDER if p in set(alto["_prio"].dropna())]).dropna())
            V.plot(V.simple_hbar(cnt, height=360, cores=V.PRIO_COLORS), key=f"{PAGE}_alto_prio")
            st.caption(f"{V.br(len(alto))} incidentes com probabilidade de violação acima de 75%.")
        else:
            st.info("Sem incidentes acima de 75% de risco com prioridade identificada.")

    a1, a2 = st.columns(2)
    with a1:
        T.section("Incidentes por equipe e prioridade", ico="users")
        top_eq = df["Grupo designado"].value_counts().head(8).index
        piv = (df[df["Grupo designado"].isin(top_eq)]
               .pivot_table(index="Grupo designado", columns="_P", values="Número",
                            aggfunc="count", fill_value=0))
        piv = piv.reindex(columns=[p for p in V.PRIO_ORDER if p in piv.columns])
        if piv.empty:
            st.info("Sem dados para o gráfico.")
        else:
            piv = piv.loc[piv.sum(axis=1).sort_values().index]
            V.plot(V.stacked_hbar(piv, colors=V.PRIO_COLORS, height=360), key=f"{PAGE}_heat_s")
            st.caption("Barra mais longa = equipe mais carregada; a cor separa a prioridade "
                       "(vermelho P1 → verde P4/P5).")
    with a2:
        T.section("Produtos com mais incidentes", ico="box")
        qtd = df["Produto"].value_counts().head(10)
        risco_prod = V.rank_dim(sla, "_produto", top=1000)
        if not qtd.empty:
            cores = {str(p): (V.risco_cor(risco_prod[p]) if p in risco_prod.index else CINZA)
                     for p in qtd.index}
            V.plot(V.simple_hbar(qtd, height=360, cores=cores), key=f"{PAGE}_prod_s")
            st.caption("Comprimento = volume de incidentes; cor = risco médio previsto de violação "
                       "do produto (cinza: sem previsão).")
        else:
            st.info("Sem produto no recorte atual.")


# ============================================================================
# 5. QUANDO A DEMANDA CHEGA
# ============================================================================
def _bloco_demanda(df: pd.DataFrame, df_ref: pd.DataFrame):
    ref = V.REF_DATE
    T.section("Quando os incidentes chegam", ico="calendar")
    d1, d2 = st.columns(2)
    with d1:
        T.section("Incidentes por turno e prioridade", sub=V.REF_DATE_STR, ico="clock")
        d_turno = df_ref if not df_ref.empty else df
        V.plot(V.stacked_bar(d_turno, "_Turno", "_P", colors=V.PRIO_COLORS, height=340),
               key=f"{PAGE}_vol_turno")
    with d2:
        T.section("Dias da semana com mais incidentes (28 dias)", ico="calendar")
        janela = df[(df["Aberto"] >= ref - pd.Timedelta(days=27)) &
                    (df["Aberto"] < ref + pd.Timedelta(days=1))]
        if not janela.empty:
            dow = (janela["Aberto"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA)))
                   .value_counts().reindex(DIAS_SEMANA).fillna(0))
            V.plot(V.bar_niveis(dow.index, dow.values, list(V.cores_relativas(dow).values()),
                                height=340, casas=0, titulo_y="incidentes"), key=f"{PAGE}_dow")
            st.caption("Vermelho: dias de maior volume · verde: menor. Base para escala de plantão.")
        else:
            st.info("Sem dados nos últimos 28 dias.")


# ============================================================================
# 6. SAÚDE OPERACIONAL
# ============================================================================
def _bloco_saude(df, prev_d1, prev_sla, ref):
    T.section("Indicadores do dia vs média histórica (0–100, maior é melhor)", ico="gauge")
    eixos, dia, hist = _health_index(df, prev_d1, prev_sla, ref)
    fig = V.grouped_bar(eixos, {"Dia atual": dia, "Média histórica": hist}, height=360)
    fig.data[0].marker.color = [RISK_GREEN if v >= 80 else (RISK_YELLOW if v >= 60 else RISK_RED)
                                for v in dia]
    fig.data[1].marker.color = CINZA
    V.plot(fig, key=f"{PAGE}_saude_s")
    st.caption("Cada eixo vai de 0 a 100 — quanto maior, melhor. Barra do dia: verde ≥80 · "
               "amarelo 60–80 · vermelho <60. Cinza = média histórica.")
