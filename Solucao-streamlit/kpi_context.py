"""
Indicadores de contexto entregues aos assistentes de IA.

Antes esses números eram literais no código das telas (`"previsao_d1": "+3.5%"`,
`"previsao_d7": "-1.2%"`, volume médio dividido por 730 dias fixos). O assistente
citava esses valores como se fossem da operação — foi o que aconteceu na resposta
sobre D+7. Agora tudo é calculado das tabelas do BigQuery, e o que não puder ser
calculado volta como "indisponível" em vez de um número inventado.
"""
import pandas as pd

import viz_helpers as V
from data_loader import load_prediction_table

INDISPONIVEL = "indisponível (tabela não retornou dados)"


def _variacao_previsto_vs_real(tabela: str, col_prev: str, col_real: str) -> str:
    """Variação % entre o previsto e o realizado da tabela de forecast."""
    df = load_prediction_table(tabela)
    if df is None or df.empty:
        return INDISPONIVEL

    dcol = V.pick_col(df, "Data", "data", "dia", contains=True)
    pcol = V.pick_col(df, col_prev, "previsto", contains=True)
    rcol = V.pick_col(df, col_real, "real", contains=True)
    if not (dcol and pcol):
        return INDISPONIVEL

    d = df.copy()
    d[dcol] = V.to_dt(d[dcol])
    d = d.dropna(subset=[dcol]).drop_duplicates(subset=[dcol], keep="last").sort_values(dcol)
    if d.empty:
        return INDISPONIVEL

    linha = d[d[dcol].dt.date == V.REF_DATE.date()]
    linha = linha if not linha.empty else d.tail(1)
    previsto = pd.to_numeric(linha[pcol], errors="coerce").iloc[0]
    if pd.isna(previsto):
        return INDISPONIVEL

    base = pd.to_numeric(d[rcol], errors="coerce").dropna() if rcol else pd.Series(dtype=float)
    base = base.iloc[:-1] if len(base) > 1 else base
    if base.empty or base.mean() == 0:
        return f"{V.br(previsto, 0)} incidentes previstos (sem série realizada para comparar)"

    var = (previsto - base.mean()) / base.mean() * 100
    return (f"{V.br(previsto, 0)} incidentes previstos, "
            f"{'+' if var >= 0 else ''}{V.br(var, 1, '%')} vs a média realizada da série")


def contexto_gestor(df: pd.DataFrame) -> dict:
    """KPIs de contexto do assistente estratégico, todos derivados dos dados."""
    total = len(df)
    violados = int((df["KPI Violado?"] == "SIM").sum()) if "KPI Violado?" in df.columns else 0
    elegiveis = int((df["Entrou para KPI?"] == "SIM").sum()) if "Entrou para KPI?" in df.columns else 0

    dias = df["Aberto"].dt.date.nunique() if "Aberto" in df.columns else 0
    media_diaria = V.br(total / dias, 0) if dias else INDISPONIVEL

    if elegiveis:
        taxa = f"{violados / elegiveis * 100:.1f}% dos incidentes elegíveis a KPI ({V.br(elegiveis)} elegíveis)"
    else:
        taxa = f"{(violados / total * 100):.1f}% do total" if total else INDISPONIVEL

    return {
        "taxa_sla": taxa,
        "media_diaria": f"{media_diaria} (média sobre {V.br(dias)} dias de base)",
        "previsao_d1": _variacao_previsto_vs_real("previsao_d1", "Incidentes_Previstos",
                                                  "Incidentes_Reais"),
        "previsao_d7": _variacao_previsto_vs_real("previsao_d7", "Incidentes_Previstos_D7",
                                                  "Incidentes_Reais_D7"),
        "data_referencia": V.REF_DATE_STR,
    }


def contexto_operador(df: pd.DataFrame) -> dict:
    """KPIs de contexto do assistente operacional."""
    def top(col, n=3):
        if col not in df.columns or df[col].dropna().empty:
            return INDISPONIVEL
        return ", ".join(df[col].value_counts().head(n).index.astype(str))

    return {
        "total_incidentes": len(df),
        "kpi_violados": int((df["KPI Violado?"] == "SIM").sum()) if "KPI Violado?" in df.columns else 0,
        "top_equipes": top("Grupo designado"),
        "top_produtos": top("Produto"),
        "data_referencia": V.REF_DATE_STR,
    }
