import streamlit as st
import theme as T
from config import APP_TITLE, APP_ICON
from theme import apply_theme, render_brand_header
from views.login import render_login
from views.operador_jornal import render_operador_jornal, render_gestor_jornal
from views.operador_painel import render_operador_painel
from views.operador_ia import render_operador_ia
from views.gestor_painel import render_gestor_painel
from views.gestor_ia import render_gestor_ia
from views.pesquisas_nl2sql import render_pesquisas
from views.justificativa_negocio import render_justificativa_negocio
from bq_loader import render_data_source_banner

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_theme() 

# Inicialização de Estado de Sessão
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_profile" not in st.session_state:
    st.session_state["user_profile"] = "operador"


def main():
    if not st.session_state["authenticated"]:
        render_login()
        return

    # Barra Lateral de Navegação
    with st.sidebar:
        render_brand_header(small=True)
        perfil = st.session_state["user_profile"]
        st.markdown(
            f"""<div style="margin:.55rem 0 .2rem;font-size:.82rem;line-height:1.5;">
                  <div style="color:#E7E9EE;font-weight:550;">
                    {st.session_state.get('user_name', 'Usuário')}</div>
                  <div style="color:#8D95A5;">
                    {'Operador NOC' if perfil == 'operador' else 'Gestor Estratégico'}</div>
                </div>""",
            unsafe_allow_html=True)

        st.divider()

        T.section("Navegação", ico="chart")
        if perfil == "operador":
            menu_options = [
                "Jornal de Turno",
                "Painel NOC",
                "IA para Operadores",
                "Pesquisas no Dataset (NL2SQL)",
                "Justificativa dos Modelos",
            ]
        else:
            menu_options = [
                "Painel Gerencial",
                "Jornal de Turno",
                "IA para Gestores",
                "Pesquisas no Dataset (NL2SQL)",
                "Justificativa dos Modelos",
            ]

        escolha = st.radio("Selecione o módulo:", menu_options, label_visibility="collapsed")

        st.divider()
        if st.button("Sair do sistema", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    # Aviso de origem dos dados (BigQuery x fallback local) — topo de toda tela
    render_data_source_banner()

    # Roteamento de Telas
    if escolha == "Jornal de Turno":
        # Mesmo módulo, duas leituras: o gestor recebe a versão sem cross-filter,
        # sem tabela por número de incidente e com gráficos de leitura direta.
        if st.session_state["user_profile"] == "operador":
            render_operador_jornal()
        else:
            render_gestor_jornal()
    elif escolha == "Painel NOC":
        render_operador_painel()
    elif escolha == "IA para Operadores":
        render_operador_ia()
    elif escolha == "Painel Gerencial":
        render_gestor_painel()
    elif escolha == "IA para Gestores":
        render_gestor_ia()
    elif escolha == "Pesquisas no Dataset (NL2SQL)":
        render_pesquisas()
    elif escolha == "Justificativa dos Modelos":
        render_justificativa_negocio()

if __name__ == "__main__":
    main()
