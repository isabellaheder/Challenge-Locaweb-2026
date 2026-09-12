import streamlit as st
import theme as T
from data_loader import load_incident_data
from gemini_service import ask_operator_assistant
from kpi_context import contexto_operador
from theme import apply_theme

def render_operador_ia():
    apply_theme()
    T.hero("IA Generativa para Operadores",
           "Assistente inteligente alimentado pelo Google Gemini para diagnóstico ágil e "
           "investigação de reincidências. O histórico desta conversa fica salvo durante toda "
           "a sessão atual.")

    df = load_incident_data()
    context_kpis = contexto_operador(df)

    if "op_chat_history" not in st.session_state:
        st.session_state["op_chat_history"] = [
            {"role": "assistant", "content": "Olá, analista. Sou o assistente operacional do Predict Ops. Como posso apoiar o seu turno agora?"}
        ]

    # Exibição do histórico de mensagens salvo nesta sessão
    for msg in st.session_state["op_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Sugestões de perguntas rápidas
    T.section("Perguntas sugeridas:", ico="search")
    col1, col2, col3 = st.columns(3)
    if col1.button("Principais incidentes das últimas 24h"):
        st.session_state["pending_prompt"] = "Quais foram os principais incidentes das últimas 24 horas e quais produtos foram mais impactados?"
    if col2.button("Equipes com maior volume hoje"):
        st.session_state["pending_prompt"] = "Qual equipe apresentou maior volume de chamados e corre risco de sobrecarga?"
    if col3.button("Reincidência de Application Monitoring"):
        st.session_state["pending_prompt"] = "O incidente de descrição 'Application Monitoring' para o produto 'lhco' é reincidente?"

    prompt = st.chat_input("Digite sua dúvida técnica ou consulta operacional...")
    if "pending_prompt" in st.session_state and st.session_state["pending_prompt"]:
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        st.session_state["op_chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consultando a base de incidentes e analisando via Google Gemini..."):
                historico_anterior = st.session_state["op_chat_history"][:-1]
                response = ask_operator_assistant(prompt, context_kpis, historico_anterior)
                st.markdown(response)
        st.session_state["op_chat_history"].append({"role": "assistant", "content": response})
