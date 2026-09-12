import streamlit as st
import theme as T
from data_loader import load_incident_data
from gemini_service import ask_manager_assistant
from kpi_context import contexto_gestor
from theme import apply_theme

def render_gestor_ia():
    apply_theme()
    T.hero("IA Generativa para Gestores",
           "Assistente executivo com Google Gemini para análises de tendência, dimensionamento "
           "e tomada de decisão estratégica. O histórico desta conversa fica salvo durante toda "
           "a sessão atual.")

    # KPIs de contexto calculados das tabelas do BigQuery — sem número fixo no código.
    df = load_incident_data()
    context_kpis = contexto_gestor(df)

    if "mgr_chat_history" not in st.session_state:
        st.session_state["mgr_chat_history"] = [
            {"role": "assistant", "content": "Olá, gestor. Sou o Assistente Estratégico do Predict Ops. Como posso apoiar suas decisões de planejamento e mitigação de riscos operacionais hoje?"}
        ]

    for msg in st.session_state["mgr_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    T.section("Consultas estratégicas recomendadas:", ico="search")
    col1, col2, col3 = st.columns(3)
    if col1.button("Previsão para a próxima semana"):
        st.session_state["mgr_pending_prompt"] = "Qual a previsão de volume de incidentes para a próxima semana (D+7) e quais produtos concentram o risco?"
    if col2.button("Equipes com risco de violação de SLA"):
        st.session_state["mgr_pending_prompt"] = "Quais equipes apresentam maior probabilidade de violação de SLA nos próximos dias e por quê?"
    if col3.button("Recomendações para redução de riscos"):
        st.session_state["mgr_pending_prompt"] = "Quais recomendações práticas e preventivas a plataforma sugere para reduzir a pressão operacional no time de suporte?"

    prompt = st.chat_input("Pergunte sobre estratégias, projeções de KPIs ou dimensionamento de equipes...")
    if "mgr_pending_prompt" in st.session_state and st.session_state["mgr_pending_prompt"]:
        prompt = st.session_state.pop("mgr_pending_prompt")

    if prompt:
        st.session_state["mgr_chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consultando a base de incidentes e gerando análise executiva via Google Gemini..."):
                historico_anterior = st.session_state["mgr_chat_history"][:-1]
                resp = ask_manager_assistant(prompt, context_kpis, historico_anterior)
                st.markdown(resp)
        st.session_state["mgr_chat_history"].append({"role": "assistant", "content": resp})
