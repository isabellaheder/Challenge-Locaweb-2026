"""
Jornal de Turno — Central de Passagem Operacional.

Duas leituras da mesma fonte (BigQuery `predictops_gold`), ancoradas em 09/12/2025:

* `render_operador_jornal()` — perfil NOC: cross-filter, tabela crítica por
  incidente, heatmap, lista do que segue aberto na passagem.
* `render_gestor_jornal()`   — perfil gestor: mesmos números, leitura direta.
  Sem cross-filter, sem tabela por número de incidente, sem escala de cor
  contínua — barras simples e texto.

Regras desta tela:
* Todo gráfico responde pelo **dia e turno selecionados** (ou pelo dia, quando o
  gráfico compara os turnos entre si). Nenhum visual cai para a base inteira;
  histórico entra só como baseline de comparação do mesmo turno.
* Barras horizontais usam semáforo (verde / amarelo / vermelho) pelo nível.
* Ordem por valor operacional: passagem de turno → risco → carga → padrões →
  contexto do dia → resumo.
"""
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import PREV_DURACAO_UNIT, SLA_HORAS_POR_PRIORIDADE
from data_loader import load_incident_data, load_prediction_table
from theme import (apply_theme, RISK_COLORS, CHART_SCALE_LOAD, RED, NAVY_LIGHT,
                   RISK_RED, RISK_ORANGE, RISK_YELLOW, RISK_GREEN)
import theme as T
import viz_helpers as V
import data_prep

ENCERRADOS = {"Encerrado", "Encerrado Automaticamente"}
# Ícone monoline de cada turno (ver theme._ICON_PATHS) — sem emoji.
_ICO_TURNO = {V.TURNOS4[0]: "moon", V.TURNOS4[1]: "sunrise",
              V.TURNOS4[2]: "sun", V.TURNOS4[3]: "sunset"}

# Prioridade como nível (P1 vermelho → P4/P5 verde) — paleta global das telas.
_PRIO_NIVEL = V.PRIO_COLORS

# Situação do prazo na passagem de turno.
_PRAZO = ["Prazo estourado", "≥75% do prazo", "Dentro do prazo", "Sem prazo definido"]
_PRAZO_CORES = {_PRAZO[0]: RISK_RED, _PRAZO[1]: RISK_YELLOW,
                _PRAZO[2]: RISK_GREEN, _PRAZO[3]: "#C9CED6"}


def render_operador_jornal():
    _render_jornal("operador")


def render_gestor_jornal():
    _render_jornal("gestor")


# ============================================================================
def _heranca(df_ref: pd.DataFrame, sel_turno: str):
    """Incidentes do dia ainda abertos no fim do turno selecionado.

    A base não tem backlog "sem data de resolução" — mas tem `Resolvido`. Um
    incidente aberto às 17h30 e resolvido às 19h estava aberto na passagem das
    18h. É esse estado, reconstruído pelos timestamps, que o próximo turno
    recebe. Escopo: incidentes abertos na data de referência até o fim do turno.
    """
    ini_h, fim_h = V.TURNO_HOURS[sel_turno]
    inicio = V.REF_DATE + pd.Timedelta(hours=ini_h)
    fim = V.REF_DATE + pd.Timedelta(hours=fim_h)
    if df_ref.empty:
        return df_ref.iloc[0:0], fim

    base = df_ref[df_ref["Aberto"] < fim]
    res = base["_res"] if "_res" in base.columns else pd.Series(pd.NaT, index=base.index)
    ab = base[res.isna() | (res > fim)].copy()
    if ab.empty:
        return ab, fim

    ab["_idade_h"] = (fim - ab["Aberto"]).dt.total_seconds() / 3600
    ab["_limite_h"] = ab["_P"].map(SLA_HORAS_POR_PRIORIDADE)
    ab["_prazo_pct"] = ab["_idade_h"] / ab["_limite_h"] * 100
    ab["_faixa_prazo"] = np.select(
        [ab["_limite_h"].isna(), ab["_prazo_pct"] >= 100, ab["_prazo_pct"] >= 75],
        [_PRAZO[3], _PRAZO[0], _PRAZO[1]], default=_PRAZO[2])
    ab["_origem"] = np.where(ab["Aberto"] >= inicio, "Aberto neste turno",
                             "Herdado de turno anterior")
    return ab, fim


def _cores_regime(perfil: pd.DataFrame) -> dict:
    """Cor pelo tipo de trabalho do regime (ver `viz_helpers.cores_regime`)."""
    return V.cores_regime(perfil.index,
                          perfil["pct_P2"] if "pct_P2" in perfil.columns else None)


# ============================================================================
def _render_jornal(perfil: str = "operador"):
    tecnico = (perfil == "operador")
    PAGE = "JORNAL" if tecnico else "JORNAL_G"

    apply_theme()
    T.hero("Jornal de Turno",
           ("Central de passagem de turno operacional NOC." if tecnico
            else "Passagem de turno — leitura executiva.")
           + f" Data operacional de referência: <code>{V.REF_DATE_STR}</code>.")

    # ── Dados ────────────────────────────────────────────────────────────────
    # Colunas derivadas vêm prontas do cache (ver data_prep.py).
    df = data_prep.incidentes()
    df_all = df  # base sem slicers — baseline histórico dos cards

    prev_turno = load_prediction_table("previsao_turno")
    prev_dur = load_prediction_table("previsao_duracao")

    ref = V.REF_DATE
    faixa_h = V.TURNO_HOURS

    # ── Navegação por turno ──────────────────────────────────────────────────
    T.section("# Selecione o turno", ico="clock")
    sel_turno = st.session_state.get(f"{PAGE}_turno", V.TURNOS4[3])
    nav = st.columns(4)
    for i, t in enumerate(V.TURNOS4):
        # O turno ativo é o botão primário — dispensa marcador textual.
        if nav[i].button(t.split(" (")[0], key=f"{PAGE}_nav_{i}",
                         type=("primary" if t == sel_turno else "secondary"),
                         use_container_width=True):
            st.session_state[f"{PAGE}_turno"] = t
            st.rerun()

    if tecnico:
        with st.expander("Filtros — Prioridade e Grupo Designado", expanded=False):
            df = V.global_slicers(df, PAGE, [("Prioridade", "_P"),
                                             ("Grupo Designado", "Grupo designado")])

    df_ref = df[df["Aberto"].dt.date == ref.date()]
    df_turno = df_ref[df_ref["_T"] == sel_turno]
    nome_turno = sel_turno.split(" (")[0]

    # ── previsao_turno: 1 linha por (data, turno) ────────────────────────────
    tt = V.turno_table(prev_turno)
    linha = tt[(tt["_data"] == ref.date()) & (tt["_turno"] == sel_turno)]

    prev_val = real_val = hist_val = None
    hist_fonte = None
    if not linha.empty:
        p, r = linha["_previsto"].iloc[0], linha["_real"].iloc[0]
        prev_val = int(round(p)) if pd.notna(p) else None
        real_val = int(round(r)) if pd.notna(r) else None
    if real_val is None:
        real_val = len(df_turno)

    outras = tt[(tt["_turno"] == sel_turno) & (tt["_data"] != ref.date())]["_real"].dropna()
    if not outras.empty:
        hist_val, hist_fonte = float(outras.mean()), "previsao_turno (demais datas)"
    else:
        ant = df_all[(df_all["_T"] == sel_turno) & (df_all["Aberto"] < ref)]
        if not ant.empty:
            diario = ant.groupby(ant["Aberto"].dt.date).size()
            if not diario.empty:
                hist_val, hist_fonte = float(diario.mean()), "média diária histórica do turno"

    var_prev = ((real_val - prev_val) / prev_val * 100) if (prev_val and real_val is not None) else None
    var_hist = ((real_val - hist_val) / hist_val * 100) if (hist_val and real_val is not None) else None

    # ── previsao_sla recortada no dia + turno ────────────────────────────────
    # `sla_frame` recompõe Produto / Grupo / Prioridade a partir de `incidentes`
    # quando o modelo grava essas colunas vazias. Sem fallback para a carteira
    # inteira do modelo: se o turno não tem incidente pontuado, a tela diz isso.
    sla = data_prep.sla()
    sla_turno = (sla[(sla["_dt"].dt.date == ref.date()) & (sla["_turno"] == sel_turno)]
                 if not sla.empty else sla)
    escopo_sla = f"{nome_turno} de {V.REF_DATE_STR}"

    # Não existe card de "SLA previsto" aqui: 100 - média(probabilidade) só seria
    # a conformidade esperada se o modelo pontuasse exatamente a população
    # elegível a KPI (4,3% dos incidentes de 09/12) e estivesse calibrado. A tela
    # mostra o risco previsto pelo modelo como risco, sem convertê-lo em SLA.
    risco_alto = int((sla_turno["_pct"] > 75).sum()) if not sla_turno.empty else 0
    risco_critico = int((sla_turno["_pct"] > 90).sum()) if not sla_turno.empty else 0

    heranca, fim_turno = _heranca(df_ref, sel_turno)

    # ── Cards do turno ───────────────────────────────────────────────────────
    st.divider()
    T.section("Indicadores do turno", sub=sel_turno, ico=_ICO_TURNO[sel_turno])
    c = st.columns(4)
    c[0].metric("Previsão para o turno", V.br(prev_val),
                delta=(f"{V.br(var_hist, 1, '%')} vs histórico" if var_hist is not None else None),
                delta_color="off")
    c[1].metric("Registrados no turno", V.br(real_val),
                delta=(f"{V.br(var_prev, 1, '%')} vs previsão" if var_prev is not None else None),
                delta_color="inverse")
    c[2].metric("Críticos P1/P2 no turno",
                V.br(int(df_turno["_P"].isin(["P1", "P2"]).sum())), delta_color="inverse")
    c[3].metric("Em risco elevado (>75%)", V.br(risco_alto),
                delta=(f"{V.br(risco_critico)} em risco crítico (>90%)"
                       if risco_critico else None),
                delta_color="inverse")
    st.caption(
        f"Previsto e registrados: linha única de `previsao_turno` em {V.REF_DATE_STR} "
        f"para o turno selecionado."
        + (f" Baseline histórico: {hist_fonte}." if hist_fonte else "")
        + f" Risco: probabilidade de violação da `previsao_sla` no escopo **{escopo_sla}**."
    )
    if tecnico and not linha.empty:
        with st.expander("Conferir os dados usados nos cards"):
            st.dataframe(linha.rename(columns={"_data": "Data", "_turno": "Turno",
                                               "_previsto": "Incidentes_Previstos",
                                               "_real": "Incidentes_Reais"}),
                         hide_index=True, use_container_width=True)
    elif tt.empty:
        st.warning("Tabela `previsao_turno` indisponível no BigQuery — cards sem previsão.")
    elif linha.empty:
        st.warning(f"`previsao_turno` não tem linha para {V.REF_DATE_STR} · {sel_turno}.")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 1. PASSAGEM DE TURNO — o que o próximo turno recebe
    # ════════════════════════════════════════════════════════════════════════
    T.section("O que passa para o próximo turno", ico="alert")
    p1, p2 = st.columns(2)
    with p1:
        T.section(f"Incidentes ainda abertos às {fim_turno.hour:02d}h, por equipe e prazo", ico="alert")
        if not heranca.empty:
            h = heranca.assign(_g=heranca["Grupo designado"].fillna("Sem grupo"))
            top_g = h["_g"].value_counts().head(10).index
            piv = (h[h["_g"].isin(top_g)]
                   .pivot_table(index="_g", columns="_faixa_prazo", values="Número",
                                aggfunc="count", fill_value=0))
            piv = piv.reindex(columns=[x for x in _PRAZO if x in piv.columns])
            piv = piv.loc[piv.sum(axis=1).sort_values().index]
            V.plot(V.stacked_hbar(piv, colors=_PRAZO_CORES, height=340), key=f"{PAGE}_heranca")
            n_est = int((heranca["_faixa_prazo"] == _PRAZO[0]).sum())
            n_75 = int((heranca["_faixa_prazo"] == _PRAZO[1]).sum())
            n_ant = int((heranca["_origem"] == "Herdado de turno anterior").sum())
            st.caption(
                f"**{V.br(len(heranca))} incidentes** passam abertos para o próximo turno "
                f"({V.br(len(heranca) - n_ant)} abertos neste turno, {V.br(n_ant)} vindos de "
                f"turnos anteriores do dia): **{V.br(n_est)} com prazo estourado** e "
                f"{V.br(n_75)} com 75% ou mais do prazo consumido. Prazo de referência por "
                "prioridade: `SLA_HORAS_POR_PRIORIDADE` (config.py).")
        else:
            st.success(f"Nenhum incidente de {V.REF_DATE_STR} segue aberto na passagem das "
                       f"{fim_turno.hour:02d}h — turno {nome_turno} entregue sem pendências.")
    with p2:
        T.section("Equipes com mais incidentes que o normal neste turno", ico="alert")
        base_hist = df_all[(df_all["_T"] == sel_turno) & (df_all["Aberto"] < ref)]
        if not df_turno.empty and not base_hist.empty:
            atual = df_turno["Grupo designado"].value_counts().head(10)
            dias = base_hist["Aberto"].dt.date.nunique() or 1
            media = (base_hist[base_hist["Grupo designado"].isin(atual.index)]
                     ["Grupo designado"].value_counts() / dias).reindex(atual.index).fillna(0)
            V.plot(V.divergent_bar(atual.index, atual.values, media.values, height=340,
                                   tolerancia=0.25),
                   key=f"{PAGE}_desvio")
            st.caption("Vermelho: mais de 25% acima da média histórica do turno. "
                       "Amarelo: acima, dentro da tolerância. Verde: no normal ou abaixo.")
        else:
            st.info(f"Sem base comparável para o turno {nome_turno}.")

    if tecnico and not heranca.empty:
        with st.expander(f"Incidentes que passam abertos para o próximo turno "
                         f"({V.br(len(heranca))})", expanded=False):
            tbl = heranca.copy()
            chaves = tbl["Número"].astype(str).str.strip()
            tbl["Situação do prazo"] = tbl["_faixa_prazo"]
            tbl["Tempo aberto na passagem (h)"] = tbl["_idade_h"].round(1)
            tbl["% do prazo consumido"] = tbl["_prazo_pct"].round(0)
            if not sla.empty:
                prob = sla.drop_duplicates(subset=["_num"], keep="last").set_index("_num")["_pct"]
                tbl["Probabilidade_Violacao_%"] = chaves.map(prob)
            else:
                tbl["Probabilidade_Violacao_%"] = np.nan
            ncol = V.pick_col(prev_dur, "Numero_Incidente", "numero incidente", contains=True)
            dcol = V.pick_col(prev_dur, "Duracao_Prevista", "duracao prevista", contains=True)
            if ncol and dcol:
                dur = (prev_dur.assign(_k=prev_dur[ncol].astype(str).str.strip())
                       .drop_duplicates(subset=["_k"], keep="last").set_index("_k")[dcol])
                dur_h = pd.to_numeric(dur, errors="coerce") * V.dur_to_hours(1.0, PREV_DURACAO_UNIT)
                tbl["Restante previsto (h)"] = (chaves.map(dur_h) - tbl["_idade_h"]).clip(lower=0).round(1)
            else:
                tbl["Restante previsto (h)"] = np.nan
            cols = ["Número", "_P", "Grupo designado"] + \
                   (["Produto"] if "Produto" in tbl.columns else []) + \
                   ["Aberto", "_origem", "Situação do prazo", "Tempo aberto na passagem (h)",
                    "% do prazo consumido", "Restante previsto (h)", "Probabilidade_Violacao_%"]
            tbl = (tbl[cols].rename(columns={"_P": "Prioridade", "_origem": "Origem"})
                   .sort_values(["% do prazo consumido", "Probabilidade_Violacao_%"],
                                ascending=False, na_position="last"))
            V.critical_table(tbl, "Probabilidade_Violacao_%", key=f"{PAGE}_tbl_heranca",
                             height=320)
            st.caption("Restante previsto: `previsao_duracao` menos o tempo já aberto na "
                       "passagem (vazio quando o modelo não pontuou o incidente).")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 2. RISCO DO TURNO
    # ════════════════════════════════════════════════════════════════════════
    T.section("Risco de violar o OLA neste turno", sub=escopo_sla, ico="alert")
    sla_view = sla_turno
    if tecnico:
        risk_sel = st.session_state.get(f"{PAGE}_risk")
        if risk_sel and not sla_turno.empty:
            sla_view = sla_turno[sla_turno["_faixa"] == risk_sel]

    est_rank = ({"sufixo": "%", "casas": 1, "cor_fn": V.risco_cor, "height": 320}
                if not tecnico else {"value_suffix": "%", "height": 320})
    sem_sla = (f"`previsao_sla` não pontuou incidentes do turno {nome_turno} de "
               f"{V.REF_DATE_STR}.")

    rr1, rr2 = st.columns(2)
    with rr1:
        T.section("Incidentes por nível de risco de violar o OLA", ico="alert")
        if not sla_turno.empty:
            counts = (sla_turno["_faixa"].value_counts()
                      .reindex(["Baixo", "Médio", "Alto", "Crítico"]).dropna())
            fig = V.donut(counts, colors=RISK_COLORS, center="Risco", height=320)
            if tecnico:
                sel = V.selectable(fig, key=f"{PAGE}_donut", field="label")
                if sel and st.session_state.get(f"{PAGE}_risk") != sel[0]:
                    st.session_state[f"{PAGE}_risk"] = sel[0]
                    st.rerun()
                if st.session_state.get(f"{PAGE}_risk"):
                    if st.button(f"Limpar filtro ({st.session_state[f'{PAGE}_risk']})",
                                 key=f"{PAGE}_risk_clear"):
                        st.session_state[f"{PAGE}_risk"] = None
                        st.rerun()
            else:
                V.plot(fig, key=f"{PAGE}_donut")
        elif sla.empty:
            st.info("`previsao_sla` indisponível ou sem probabilidade numérica.")
        else:
            st.info(sem_sla)
    with rr2:
        T.section("Produtos com maior risco de violar o OLA", ico="alert")
        V.render_ranking(
            V.rank_dim(sla_view, "_produto", top=10), key=f"{PAGE}_prod",
            risco=tecnico, simples=not tecnico,
            motivo_vazio=(sem_sla if sla_view.empty else
                          "Sem produto identificado nas linhas de `previsao_sla` deste "
                          "turno (nem na própria tabela, nem via join com `incidentes`)."),
            **est_rank)

    e1, e2 = st.columns(2)
    with e1:
        T.section("Equipes com maior risco de violar o OLA", ico="alert")
        V.render_ranking(
            V.rank_dim(sla_view, "_grupo", top=10), key=f"{PAGE}_eq_risco",
            risco=tecnico, simples=not tecnico,
            motivo_vazio=(sem_sla if sla_view.empty else
                          "Sem grupo designado nas linhas de `previsao_sla` deste turno."),
            **est_rank)
    with e2:
        T.section("Risco médio de violar o OLA, por prioridade", ico="alert")
        V.render_ranking(
            V.rank_dim(sla_view, "_prio", top=6), key=f"{PAGE}_prio_risco",
            risco=tecnico, simples=not tecnico,
            motivo_vazio=(sem_sla if sla_view.empty else
                          "Sem prioridade nas linhas de `previsao_sla` deste turno."),
            **est_rank)
    T.legend(T.LEGENDA_RISCO)

    if tecnico:
        T.section("Incidentes com maior chance de violar o OLA", ico="alert")
        if not sla_view.empty:
            tbl = (sla_view.rename(columns={
                "_num": "Numero_Incidente", "_prio": "Prioridade", "_grupo": "Grupo Designado",
                "_produto": "Produto", "_pct": "Probabilidade_Violacao_%", "_faixa": "Risco"})
                [["Numero_Incidente", "Prioridade", "Grupo Designado", "Produto",
                  "Probabilidade_Violacao_%", "Risco"]]
                .sort_values("Probabilidade_Violacao_%", ascending=False))
            V.critical_table(tbl, "Probabilidade_Violacao_%", key=f"{PAGE}_tbl",
                             search_cols=["Numero_Incidente", "Grupo Designado",
                                          "Produto", "Prioridade"])
        else:
            st.info(sem_sla if not sla.empty
                    else "Modelo `previsao_sla` indisponível para a tabela crítica.")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 3. CARGA DO TURNO
    # ════════════════════════════════════════════════════════════════════════
    T.section("Carga de trabalho do turno", sub=escopo_sla, ico="clock")
    k1, k2 = st.columns(2)
    with k1:
        T.section("Incidentes por equipe e prioridade", ico="clock")
        top_eq = (df_turno["Grupo designado"].value_counts().head(8).index
                  if not df_turno.empty else [])
        if len(top_eq):
            piv = (df_turno[df_turno["Grupo designado"].isin(top_eq)]
                   .pivot_table(index="Grupo designado", columns="_P", values="Número",
                                aggfunc="count", fill_value=0))
            piv = piv.reindex(columns=[p for p in V.PRIO_ORDER if p in piv.columns])
            if tecnico:
                V.plot(V.heatmap(piv, scale=CHART_SCALE_LOAD, height=340), key=f"{PAGE}_heat")
                st.caption("Quanto mais escura a célula, maior a carga da equipe naquela prioridade "
                           "— identifica gargalo e sobrecarga.")
            else:
                piv = piv.loc[piv.sum(axis=1).sort_values().index]
                V.plot(V.stacked_hbar(piv, colors=_PRIO_NIVEL, height=340), key=f"{PAGE}_heat_g")
                st.caption("Carga de cada equipe no turno, separada por prioridade "
                           "(vermelho P1 → verde P4/P5).")
        else:
            st.info(f"Sem incidentes no turno {nome_turno} para o gráfico.")
    with k2:
        T.section("Precisaram de pessoa vs fecharam sozinhos", ico="clock")
        # Status "Sem Intervenção" = fechado pela automação de monitoramento, sem
        # toque do NOC. É o que separa carga real de ruído.
        tratados = df_turno[df_turno["Status"] != "Sem Intervenção"]
        if not df_turno.empty:
            comp = pd.Series({
                "Auto-resolvido": int((df_turno["Status"] == "Sem Intervenção").sum()),
                "Com intervenção": len(tratados)})
            V.plot(V.donut(comp, colors={"Auto-resolvido": "#C9CED6", "Com intervenção": RED},
                           center="Turno", height=320), key=f"{PAGE}_atuacao")
            if not tratados.empty:
                por_prio = ", ".join(
                    f"{p}: {V.br(int(n))}" for p, n in
                    tratados["_P"].value_counts().reindex(
                        [x for x in V.PRIO_ORDER if x in set(tratados["_P"])]).dropna().items())
                st.caption(f"{V.br(len(tratados))} de {V.br(len(df_turno))} incidentes passaram "
                           f"por uma equipe ({por_prio}). O restante fechou sozinho.")
            else:
                st.caption(f"Os {V.br(len(df_turno))} incidentes do turno fecharam sozinhos, "
                           f"sem intervenção humana.")
        else:
            st.info(f"Sem incidentes no turno {nome_turno}.")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 4. PADRÕES E TEMAS DO TURNO
    # ════════════════════════════════════════════════════════════════════════
    # Regimes (`clusters_incidentes`) e temas (`cluster_nlp`) anexados ao recorte
    # dia + turno — nada da base inteira. O histórico entra só como média do
    # mesmo turno nos dias anteriores, para dizer o que está diferente hoje.
    T.section("Que tipo de problema chegou no turno", sub=escopo_sla, ico="brain")

    tema_turno = data_prep.com_tema(df_turno)
    regime_turno = data_prep.com_regime(df_turno)
    perfil_t = data_prep.perfil_temas_de(tema_turno, casas_horas=1)
    reg = data_prep.perfil_regimes(regime_turno)

    hist_turno = df[(df["Aberto"] < ref) & (df["_T"] == sel_turno)]
    dias_hist = hist_turno["Aberto"].dt.date.nunique() if not hist_turno.empty else 0
    tema_hist = data_prep.com_tema(hist_turno) if dias_hist else hist_turno.iloc[0:0]

    emerg = pd.DataFrame()
    if not tema_turno.empty and dias_hist:
        no_turno = tema_turno["_tema"].value_counts()
        media_t = (tema_hist["_tema"].value_counts() / dias_hist
                   if not tema_hist.empty else pd.Series(dtype=float))
        emerg = pd.DataFrame({"no_turno": no_turno, "media_turno": media_t}).fillna(0)
        emerg = emerg[(emerg["no_turno"] > 0) | (emerg["media_turno"] > 0)]
        emerg["desvio"] = emerg["no_turno"] - emerg["media_turno"]
        emerg["tendencia_%"] = np.where(emerg["media_turno"] > 0,
                                        (emerg["no_turno"] / emerg["media_turno"].where(
                                            emerg["media_turno"] > 0) - 1) * 100, np.nan)
        clusters_nome = pd.concat([tema_turno[["_tema", "_cluster"]],
                                   tema_hist[["_tema", "_cluster"]] if not tema_hist.empty
                                   else tema_turno[["_tema", "_cluster"]].iloc[0:0]])
        emerg["cluster"] = clusters_nome.drop_duplicates("_tema").set_index("_tema")["_cluster"]
        emerg = emerg.sort_values("no_turno", ascending=False)

    cl1, cl2 = st.columns(2)
    with cl1:
        T.section("Tipos de problema acima do normal neste turno", ico="alert")
        if not emerg.empty:
            e = emerg.reindex(emerg["desvio"].abs().sort_values(ascending=False).index).head(10)
            V.plot(V.divergent_bar(e.index, e["no_turno"], e["media_turno"], height=340,
                                   nome_base=f"média/{nome_turno.lower()} anterior",
                                   tolerancia=0.25),
                   key=f"{PAGE}_emergentes")
            st.caption("Vermelho: tema mais de 25% acima do seu próprio normal neste turno. "
                       "Amarelo: acima, dentro da tolerância. Verde: no normal ou abaixo.")
        elif tema_turno.empty:
            st.info(f"Nenhum incidente do turno {nome_turno} tem tema em `cluster_nlp`.")
        else:
            st.info(f"Sem histórico do turno {nome_turno} anterior a {V.REF_DATE_STR} para comparar.")

    with cl2:
        T.section("Horas de trabalho estimadas por tipo de problema", ico="clock")
        if not perfil_t.empty:
            horas = perfil_t["horas_estimadas"].sort_values(ascending=False).head(8)
            if float(horas.max() or 0) > 0:
                V.plot(V.lollipop(horas, height=340, sufixo=" h", casas=1,
                                  cores=V.cores_relativas(horas)),
                       key=f"{PAGE}_esforco_tema")
                st.caption("Volume do turno × duração mediana do turno. Vermelho: maior consumo "
                           "de horas; verde: menor. Priorizar por contagem engana.")
            else:
                st.info(f"Os temas do turno {nome_turno} fecharam em minutos — esforço "
                        "estimado próximo de zero.")
        else:
            st.info(f"Nenhum incidente do turno {nome_turno} tem tema em `cluster_nlp`.")

    tm1, tm2 = st.columns(2)
    with tm1:
        T.section("Incidentes do turno: ruído automático, operação ou crítico", ico="layers")
        if not reg.empty:
            V.plot(V.lollipop(reg["incidentes"], height=300, cores=_cores_regime(reg)),
                   key=f"{PAGE}_regimes")
            total = int(reg["incidentes"].sum())
            ruido = int(reg[reg.index.astype(str).str.contains("ru[íi]do", case=False,
                                                               regex=True)]["incidentes"].sum())
            humano = total - ruido
            if total:
                st.caption(f"De {V.br(total)} incidentes do turno, **{V.br(humano)} "
                           f"({V.br(humano / total * 100, 1, '%')}) exigem pessoa** — o resto "
                           "é ruído automatizado. Verde: ruído · amarelo: operação · "
                           "vermelho: cauda crítica.")
        else:
            st.info(f"Nenhum incidente do turno {nome_turno} tem regime em `clusters_incidentes`.")

    with tm2:
        T.section("% de chamados duplicados por tipo de problema", ico="recycle")
        base_pai = (perfil_t[perfil_t["incidentes"] >= 3] if not perfil_t.empty else perfil_t)
        if not base_pai.empty:
            pai = base_pai["pct_com_pai"].sort_values(ascending=False).head(8)
            V.plot(V.lollipop(pai, height=300, sufixo="%", casas=1,
                              cores={k: V.cor_nivel(v, 15, 30) for k, v in pai.items()}),
                   key=f"{PAGE}_tempestade")
            topo = pai.index[0] if len(pai) else None
            if topo is not None and pai.iloc[0] > 30:
                st.caption(f"Em **{topo}**, {V.br(pai.iloc[0], 1, '%')} dos chamados do turno são "
                           "duplicados de um incidente já aberto — é 1 problema contado várias "
                           "vezes. Vermelho >30% · amarelo 15–30% · verde <15%.")
            else:
                st.caption("Proporção de chamados do turno vinculados a um incidente pai, por tema "
                           "(temas com 3+ chamados). Vermelho >30% · amarelo 15–30% · verde <15%.")
        else:
            st.info(f"Sem temas com volume suficiente no turno {nome_turno}.")

    if not emerg.empty:
        with st.expander("Categorias predominantes e tendências do turno",
                         expanded=not tecnico):
            vista = emerg.head(10).copy()
            vista["Tendência"] = vista["tendencia_%"].apply(
                lambda v: "—" if pd.isna(v) else ("▲ " if v > 0 else "▼ ") + V.br(abs(v), 0, "%"))
            vista = vista.reset_index(names="Tema").rename(columns={
                "cluster": "Cluster", "no_turno": "No turno",
                "media_turno": "Média do turno (dias anteriores)"})
            vista["Média do turno (dias anteriores)"] = vista["Média do turno (dias anteriores)"].round(1)
            st.dataframe(vista[["Tema", "Cluster", "No turno",
                                "Média do turno (dias anteriores)", "Tendência"]],
                         hide_index=True, use_container_width=True)
            emergentes = emerg[(emerg["tendencia_%"] > 50) & (emerg["no_turno"] >= 3)].head(3)
            if not emergentes.empty:
                st.warning(f"Temas em alta no turno {nome_turno}: "
                           + " · ".join(emergentes.index.astype(str)))

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 5. CONTEXTO DO DIA — o turno selecionado frente aos demais
    # ════════════════════════════════════════════════════════════════════════
    T.section(f"Como foi o dia inteiro ({V.REF_DATE_STR})", ico="trend")
    x1, x2 = st.columns(2)
    with x1:
        T.section("Incidentes previstos vs registrados em cada turno", ico="trend")
        dia = tt[tt["_data"] == ref.date()] if not tt.empty else tt
        if not dia.empty:
            agg = dia.set_index("_turno")[["_previsto", "_real"]].reindex(V.TURNOS4).fillna(0)
            fig = V.grouped_bar([t.split(" (")[0] for t in agg.index],
                                {"Previsto": agg["_previsto"], "Real": agg["_real"]}, height=320)
            fig.update_traces(marker_opacity=[1.0 if t == sel_turno else 0.4 for t in agg.index])
            V.plot(fig, key=f"{PAGE}_pvr")
            st.caption(f"Turno {nome_turno} em destaque.")
        else:
            st.info("Tabela `previsao_turno` sem linhas na data de referência.")
    with x2:
        T.section("Incidentes abertos por hora (turno em vermelho)", ico="clock")
        if not df_ref.empty:
            serie = df_ref.groupby(df_ref["Aberto"].dt.hour).size().reindex(range(24), fill_value=0)
            V.plot(V.hour_bar(serie, height=320, destaque=faixa_h[sel_turno]), key=f"{PAGE}_hora")
            st.caption(f"Barras em vermelho: janela do turno {sel_turno}.")
        else:
            st.info(f"Sem incidentes em {V.REF_DATE_STR} para o filtro atual.")

    t1, t2 = st.columns(2)
    with t1:
        T.section("Incidentes por hora vs média do dia", ico="clock")
        if not df_ref.empty:
            serie = df_ref.groupby(df_ref["Aberto"].dt.hour).size().reindex(range(24), fill_value=0)
            media, std = serie.mean(), serie.std()
            anom = serie[serie > media + 2 * std]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[f"{h:02d}h" for h in serie.index], y=list(serie.values),
                                     mode="lines+markers", line=dict(color=RED, width=2.5),
                                     fill="tozeroy", fillcolor="rgba(240,8,74,0.08)",
                                     name="Incidentes/h",
                                     hovertemplate="%{x}<br>%{y} incidentes<extra></extra>"))
            fig.add_hline(y=media, line=dict(color=NAVY_LIGHT, dash="dash", width=1),
                          annotation_text=f"média {media:.0f}")
            if not anom.empty and tecnico:
                fig.add_trace(go.Scatter(x=[f"{h:02d}h" for h in anom.index], y=list(anom.values),
                                         mode="markers",
                                         marker=dict(color=RISK_RED, size=13, symbol="x"),
                                         name="Anomalia"))
            fig.update_layout(xaxis_title="Hora", yaxis_title="Incidentes")
            V.plot(V.style_fig(fig, height=320, legend=True, legend_top=True), key=f"{PAGE}_24h")
        else:
            st.info(f"Sem incidentes em {V.REF_DATE_STR} para o filtro atual.")
    with t2:
        T.section("Prioridade dos incidentes em cada turno", ico="clock")
        if not df_ref.empty:
            piv = (df_ref.pivot_table(index="_T", columns="_P", values="Número",
                                      aggfunc="count", fill_value=0)
                   .reindex(V.TURNOS4).fillna(0))
            piv.index = [t.split(" (")[0] for t in piv.index]
            piv = piv.reindex(columns=[p for p in V.PRIO_ORDER if p in piv.columns])
            V.plot(V.stacked_hbar(piv, colors=_PRIO_NIVEL, height=320), key=f"{PAGE}_mix")
        else:
            st.info("Sem incidentes na data de referência.")

    st.divider()

    # ── Resumo executivo (copiloto) ──────────────────────────────────────────
    _resumo_executivo(PAGE, sel_turno, df_turno, sla_turno, prev_val, real_val,
                      risco_alto, risco_critico, hist_val, heranca, fim_turno)


# ============================================================================
def _resumo_executivo(PAGE, sel_turno, df_turno, sla_turno, prev_val, real_val,
                      risco_alto, risco_critico, hist_val, heranca=None, fim_turno=None):
    """Resumo em frases, no formato de uma passagem de turno escrita."""
    T.section("Resumo da passagem de turno (Copiloto)", ico="clock")
    equipe = (df_turno["Grupo designado"].value_counts().idxmax()
              if not df_turno.empty else "—")
    rk_prod = V.rank_dim(sla_turno, "_produto", top=1)
    produto = str(rk_prod.index[0]) if len(rk_prod) else "—"
    nome_turno = sel_turno.split(" (")[0]
    faixa = sel_turno.split("(")[1].replace(")", "") if "(" in sel_turno else ""
    if prev_val and real_val is not None:
        desvio = real_val - prev_val
        veredito = ("dentro do previsto" if abs(desvio) <= max(5, 0.1 * prev_val)
                    else (f"{V.br(abs(desvio))} acima do previsto" if desvio > 0
                          else f"{V.br(abs(desvio))} abaixo do previsto"))
    else:
        veredito = "sem previsão disponível para comparação"

    frases = [
        f"<b>{V.br(prev_val)}</b> incidentes previstos.",
        f"<b>{V.br(real_val)}</b> incidentes registrados — {veredito}.",
        f"<b>{V.br(risco_alto)}</b> incidentes apresentam risco elevado de violação"
        + (f", sendo <b>{V.br(risco_critico)}</b> em risco crítico." if risco_critico else "."),
        f"Equipe mais pressionada: <b>{equipe}</b>.",
        f"Produto com maior criticidade: <b>{produto}</b>.",
    ]
    if hist_val:
        frases.insert(2, f"Média histórica do turno: <b>{V.br(hist_val, 0)}</b> incidentes.")
    if heranca is not None and fim_turno is not None:
        if heranca.empty:
            frases.append(f"Nenhum incidente segue aberto na passagem das "
                          f"{fim_turno.hour:02d}h.")
        else:
            n_est = int((heranca["_faixa_prazo"] == _PRAZO[0]).sum())
            frases.append(f"<b>{V.br(len(heranca))}</b> incidentes passam abertos para o "
                          f"próximo turno" + (f", <b>{V.br(n_est)}</b> com prazo estourado."
                                              if n_est else "."))

    itens = "".join(f"<li style='margin:0.25rem 0'>{f}</li>" for f in frases)
    st.markdown(f"""
<div style="background:#1F2733;border-radius:12px;padding:1.4rem 1.8rem;color:#E7E9EE;
     font-family:'Segoe UI',system-ui,sans-serif;border-left:4px solid {RED};">
  <div style="font-size:1.15rem;font-weight:700;color:{RED};margin-bottom:0.9rem;">
    Turno {nome_turno} · {faixa} · {V.REF_DATE_STR}
  </div>
  <ul style="margin:0;padding-left:1.1rem;line-height:1.75;font-size:0.98rem;">{itens}</ul>
  <p style="margin:0.9rem 0 0;font-size:0.82rem;color:#9CA3AF;">
     Gerado a partir de <code>previsao_turno</code>, <code>previsao_sla</code> e da base
     <code>incidentes</code> no BigQuery.
  </p>
</div>
""", unsafe_allow_html=True)

    limpo = [f.replace("<b>", "").replace("</b>", "") for f in frases]
    txt = "\n".join([f"Turno {nome_turno} ({faixa}) · {V.REF_DATE_STR}", ""]
                    + [f"- {f}" for f in limpo])
    st.download_button("Baixar resumo da passagem de turno (TXT)", txt,
                       file_name=f"passagem_turno_{nome_turno.lower()}.txt",
                       key=f"{PAGE}_dl_resumo")
