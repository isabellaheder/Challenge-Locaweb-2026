import streamlit as st
from theme import apply_theme, render_brand_header, NAVY, RED, TEXT_MUTED, BORDER_SOFT

def render_login():
    apply_theme()

    # Painel de fundo mais calmo na tela de entrada, sem o degradê rosado das telas internas.
    st.markdown(
        """<style>
        .stApp {background: radial-gradient(1200px 600px at 50% -20%, #FFFFFF 0%,
                 rgba(255,255,255,0) 62%), #F4F5F7;}
        [data-testid="stSidebar"] {display:none;}
        </style>
        <div style='margin-top: 4.5rem;'></div>""",
        unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
        render_brand_header()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(
            """
            <p style="text-align:center; font-size:1rem; color:#6B7280; margin-top:0.6rem; margin-bottom:2rem;">
                Plataforma de monitoramento inteligente e predição operacional — Locaweb
            </p>
            """,
            unsafe_allow_html=True
        )

        with st.container(border=True):
            st.markdown(
                f"""<div style="font-size:.72rem;font-weight:650;letter-spacing:.14em;
                          text-transform:uppercase;color:{TEXT_MUTED};margin-bottom:.9rem;">
                        Acesso à plataforma
                    </div>""",
                unsafe_allow_html=True)
            perfil = st.radio(
                "Selecione seu perfil de acesso:",
                ["Operador (NOC / Técnico)", "Gestor (Executivo / Líder)"],
                index=0
            )

            usuario = st.text_input("Usuário", value="analista.noc" if "Operador" in perfil else "gestor.operacoes")
            senha = st.text_input("Senha", type="password", value="predictops2026")

            st.markdown(
                f"""<div style="border-top:1px solid {BORDER_SOFT};margin:.9rem 0 .9rem;"></div>
                    <div style="font-size:.78rem;color:{TEXT_MUTED};">
                        Ambiente de demonstração integrado ao GCP.
                    </div>""",
                unsafe_allow_html=True)

            if st.button("Entrar no Predict Ops", use_container_width=True, type="primary"):
                st.session_state["authenticated"] = True
                st.session_state["user_profile"] = "operador" if "Operador" in perfil else "gestor"
                st.session_state["user_name"] = usuario
                st.rerun()
