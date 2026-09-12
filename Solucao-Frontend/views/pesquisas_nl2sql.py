import streamlit as st
import theme as T
import plotly.express as px
from data_loader import tabelas_disponiveis
from gemini_service import natural_language_to_sql
from theme import apply_theme, CHART_SCALE_NAVY


def _executar_pesquisa(user_query: str):
    """Executa a pesquisa NL2SQL e salva o resultado no histórico da sessão atual."""
    with st.spinner("O Google Gemini está construindo e executando a consulta SQL..."):
        sql_generated, df_result, ai_summary = natural_language_to_sql(user_query)

    if "sql_search_history" not in st.session_state:
        st.session_state["sql_search_history"] = []

    st.session_state["sql_search_history"].insert(0, {
        "pergunta": user_query,
        "sql": sql_generated,
        "resultado": df_result,
        "resumo": ai_summary,
    })


def _renderizar_resultado(item, expanded=False, titulo="Resultado da Consulta"):
    df_result = item["resultado"]

    with st.expander("Ver consulta SQL gerada pela IA", expanded=expanded):
        st.code(item["sql"], language="sql")

    T.section(titulo, ico="chart")
    st.dataframe(df_result, use_container_width=True)

    num_cols = df_result.select_dtypes(include=['number']).columns.tolist()
    obj_cols = df_result.select_dtypes(include=['object', 'string']).columns.tolist()

    if len(num_cols) >= 1 and len(obj_cols) >= 1 and len(df_result) <= 30:
        fig_auto = px.bar(
            df_result,
            x=obj_cols[0],
            y=num_cols[0],
            color=num_cols[0],
            title=f"{num_cols[0]} por {obj_cols[0]}",
            color_continuous_scale=CHART_SCALE_NAVY
        )
        st.plotly_chart(fig_auto, use_container_width=True)

    T.section("Síntese e Insights da IA", ico="chart")
    st.info(item["resumo"])


def render_pesquisas():
    apply_theme()
    T.hero("Pesquisas em Linguagem Natural no Dataset",
           "Faça perguntas em linguagem humana sobre o dataset. O Google Gemini converte "
           "sua pergunta em SQL, executa no banco e traz os dados, gráficos e uma análise "
           "executiva.")
    st.caption("Tabelas consultáveis: " + ", ".join(f"`{t}`" for t in tabelas_disponiveis()))
    st.caption("Todas as pesquisas realizadas nesta sessão ficam salvas no histórico abaixo.")

    with st.container(border=True):
        col_in, col_btn = st.columns([4, 1])
        user_query = col_in.text_input(
            "Digite sua pesquisa em linguagem natural:",
            value=st.session_state.get("quick_query", "me mostre os top 5 itens de configuração com mais incidentes"),
            placeholder="Ex: Quais são os 5 produtos com maior número de incidentes de prioridade Alta?"
        )
        exec_clicked = col_btn.button("Pesquisar", use_container_width=True, type="primary")

    st.caption("Exemplos rápidos:")
    c1, c2, c3 = st.columns(3)
    if c1.button("Top 5 Itens de Configuração"):
        st.session_state["quick_query"] = "me mostre os top 5 itens de configuração com mais incidentes"
        st.rerun()
    if c2.button("Top 5 Produtos com OLA Violado"):
        st.session_state["quick_query"] = "quais os 5 produtos que mais tiveram KPI Violado como SIM?"
        st.rerun()
    if c3.button("Distribuição por Status de Fechamento"):
        st.session_state["quick_query"] = "qual a quantidade de incidentes agrupados por Status?"
        st.rerun()
    c4, c5, c6 = st.columns(3)
    if c4.button("Previsão D+7 vs realizado"):
        st.session_state["quick_query"] = ("mostre a previsão D+7 e o realizado por data, "
                                           "das datas mais recentes para as mais antigas")
        st.rerun()
    if c5.button("Produtos que concentram risco de OLA"):
        st.session_state["quick_query"] = ("quais produtos têm a maior probabilidade média de "
                                           "violação de OLA e quantos incidentes cada um tem?")
        st.rerun()
    if c6.button("Previsão por turno"):
        st.session_state["quick_query"] = "compare incidentes previstos e reais por turno"
        st.rerun()

    if "sql_search_history" not in st.session_state:
        st.session_state["sql_search_history"] = []

    if exec_clicked and user_query:
        try:
            _executar_pesquisa(user_query)
            st.success("Consulta executada com sucesso.")
        except Exception as e:
            st.error(f"Erro ao processar pesquisa: {str(e)}")

    historico = st.session_state["sql_search_history"]

    if historico:
        st.divider()
        T.section(f'Pergunta atual: "{historico[0]["pergunta"]}"', ico="chart")
        _renderizar_resultado(historico[0], expanded=False)

        if len(historico) > 1:
            st.divider()
            T.section("Histórico de Pesquisas desta Sessão", ico="chart")
            for item in historico[1:]:
                with st.expander(f'"{item["pergunta"]}"'):
                    _renderizar_resultado(item, expanded=False, titulo="Resultado")
    else:
        st.info("Nenhuma pesquisa realizada ainda nesta sessão. Digite uma pergunta e clique em Pesquisar.")
