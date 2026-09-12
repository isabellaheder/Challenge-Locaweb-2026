"""
Tema visual do Predict Ops, inspirado na identidade da Locaweb:
tons de azul-marinho e vermelho, tipografia limpa, cartões com
bastante espaço em branco e sem elementos gráficos supérfluos.
"""
import streamlit as st

# ----------------------------------------------------------------------------
# Paleta de cores
# ----------------------------------------------------------------------------
NAVY = "#1F2733"
NAVY_LIGHT = "#2A343E"
RED = "#F0084A"
RED_DARK = "#C2013A"
BG = "#F4F5F7"
CARD = "#FFFFFF"
BORDER = "#E3E6EB"
TEXT = "#1F2733"
TEXT_MUTED = "#6B7280"

# Paletas para gráficos Plotly, alinhadas à marca (sem cores "arco-íris")
CHART_SEQUENCE = [RED, NAVY_LIGHT, "#8C93A6", "#FF7A9C", "#4E5B6E", "#C9CED6"]
CHART_SCALE_RED = ["#F4E4E9", "#F0084A"]
CHART_SCALE_NAVY = ["#DCE1E8", "#2A343E"]

# ----------------------------------------------------------------------------
# Paletas de risco / carga operacional (adicionadas para os visuais avançados)
# ----------------------------------------------------------------------------
RISK_GREEN = "#12A150"   # baixo
RISK_YELLOW = "#E8A700"  # médio
RISK_ORANGE = "#F27522"  # alto
RISK_RED = "#D30F45"     # crítico

RISK_COLORS = {
    "Baixo": RISK_GREEN,
    "Médio": RISK_YELLOW,
    "Alto": RISK_ORANGE,
    "Crítico": RISK_RED,
}
# Escala contínua verde -> amarelo -> laranja -> vermelho para heatmaps de risco
CHART_SCALE_RISK = [
    [0.00, "#EAF5EE"],
    [0.35, RISK_GREEN],
    [0.60, RISK_YELLOW],
    [0.80, RISK_ORANGE],
    [1.00, RISK_RED],
]
# Escala de "carga operacional" por nível: vazio neutro, pouca carga verde, muita
# carga vermelha. Antes ia de cinza a navy a vermelho e não comunicava nível.
CHART_SCALE_LOAD = [
    [0.00, "#F2F4F7"],
    [0.08, "#CDEBD8"],
    [0.30, RISK_GREEN],
    [0.55, RISK_YELLOW],
    [0.78, RISK_ORANGE],
    [1.00, RISK_RED],
]

# Cores de status operacional (consistentes em todas as telas)
STATUS_COLORS = {
    "Aberto": RED,
    "Em Atendimento": "#F27522",
    "Aguardando": "#E8A700",
    "Aguardando Problema": "#E8A700",
    "Resolvido": "#3E7CB1",
    "Encerrado": NAVY_LIGHT,
    "Encerrado Automaticamente": "#8C93A6",
    "Sem Intervenção": "#C9CED6",
}

# Fonte / configuração padrão dos gráficos Plotly
PLOTLY_FONT = dict(
    family='-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    size=13,
    color=TEXT,
)
# Passado a st.plotly_chart(config=...): habilita exportação PNG e limpa a modebar.
CHART_CONFIG = {
    "displaylogo": False,
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "predictops_grafico", "scale": 2},
}


# ----------------------------------------------------------------------------
# Tokens de superfície: elevação, raio e espaçamento
# ----------------------------------------------------------------------------
SURFACE = "#FFFFFF"
SURFACE_SUNK = "#EEF0F4"
BORDER_SOFT = "#EAECF0"
SHADOW_SM = "0 1px 2px rgba(16,24,40,.05)"
SHADOW_MD = "0 1px 3px rgba(16,24,40,.06), 0 1px 2px rgba(16,24,40,.04)"
SHADOW_LG = "0 4px 16px rgba(16,24,40,.07), 0 1px 3px rgba(16,24,40,.04)"
RADIUS = "12px"
RADIUS_SM = "8px"

FONT_STACK = ('"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
              'Helvetica, Arial, sans-serif')
FONT_MONO = '"JetBrains Mono", "SF Mono", ui-monospace, Menlo, Consolas, monospace'

PLOTLY_FONT = dict(family=FONT_STACK, size=12.5, color=TEXT)

CHART_CONFIG = {
    "displaylogo": False,
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "predictops_grafico", "scale": 3},
}


# ----------------------------------------------------------------------------
# Ícones — SVG monoline inline, no lugar de emoji
# ----------------------------------------------------------------------------
# Traço de 1.6px, canto arredondado, herda a cor do contexto via currentColor.
_ICON_PATHS = {
    "pulse":     'M3 12h4l3 8 4-16 3 8h4',
    "gauge":     'M12 20a8 8 0 1 1 8-8M12 12l4.5-4.5',
    "target":    'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z',
    "clock":     'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3.5 2',
    "calendar":  'M4 6h16v15H4zM4 10h16M8 3v4M16 3v4',
    "layers":    'M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5M3 17.5l9 5 9-5',
    "chart":     'M4 20V9M10 20V4M16 20v-7M22 20H2',
    "trend":     'M3 16l5-6 4 4 6-8M14 6h5v5',
    "grid":      'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
    "users":     'M16 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M9.5 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7M21 20v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
    "alert":     'M12 3 2.5 20h19L12 3ZM12 10v4M12 17.5h.01',
    "shield":    'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3ZM9 12.5l2 2 4-4',
    "brain":     'M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5.2A3 3 0 0 0 6 17a3 3 0 0 0 3 3V4ZM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5.2A3 3 0 0 1 18 17a3 3 0 0 1-3 3V4Z',
    "spark":     'M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4L12 3Z',
    "search":    'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM21 21l-4.3-4.3',
    "filter":    'M3 5h18l-7 8v6l-4 2v-8L3 5Z',
    "flow":      'M3 18c4 0 5-11 9-11s5 8 9 8',
    "recycle":   'M4 12a8 8 0 0 1 13.7-5.7M20 12a8 8 0 0 1-13.7 5.7M17 3v4h-4M7 21v-4h4',
    "moon":      'M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z',
    "sunrise":   'M12 3v5M5.6 10.6 4.2 9.2M18.4 10.6l1.4-1.4M2 18h20M6.5 18a5.5 5.5 0 0 1 11 0M8.5 6.5 12 3l3.5 3.5',
    "sun":       'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
    "sunset":    'M12 8V3M5.6 10.6 4.2 9.2M18.4 10.6l1.4-1.4M2 18h20M6.5 18a5.5 5.5 0 0 1 11 0M8.5 5 12 8.5 15.5 5',
    "box":       'M3 8l9-5 9 5v8l-9 5-9-5V8ZM3 8l9 5 9-5M12 13v10',
    "doc":       'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5ZM14 3v5h5M9 13h6M9 17h4',
    "robot":     'M12 3v3M6 6h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2ZM9 12h.01M15 12h.01M9.5 16h5',
}


def icon(name: str, size: int = 18, color: str = "currentColor", stroke: float = 1.6) -> str:
    """SVG inline de um ícone monoline. Devolve markup para usar em st.markdown."""
    d = _ICON_PATHS.get(name)
    if not d:
        return ""
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round" style="flex:0 0 auto;display:block;">'
        f'<path d="{d}"/></svg>'
    )


_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
    font-family: {FONT_STACK};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

.stApp {{
    background:
        radial-gradient(1100px 520px at 12% -12%, #FFFFFF 0%, rgba(255,255,255,0) 60%),
        radial-gradient(900px 460px at 105% 0%, #FDF1F4 0%, rgba(253,241,244,0) 55%),
        {BG};
    background-attachment: fixed;
}}

#MainMenu, footer {{visibility: hidden;}}
header[data-testid="stHeader"] {{background: transparent; height: 0;}}
[data-testid="stToolbar"] {{right: 1rem;}}

.block-container {{
    padding-top: 2.4rem;
    padding-bottom: 4rem;
    max-width: 1500px;
}}

/* ---------- Tipografia ---------- */
h1, h2, h3, h4 {{
    color: {NAVY};
    font-weight: 650;
    letter-spacing: -.021em;
}}
h1 {{ font-size: 1.95rem; line-height: 1.15; }}
h2 {{ font-size: 1.35rem; }}
h3 {{ font-size: 1.08rem; }}
code, pre, kbd {{ font-family: {FONT_MONO}; font-size: .86em; }}
code {{
    background: {SURFACE_SUNK};
    color: {NAVY};
    padding: .1em .42em;
    border-radius: 5px;
    border: 1px solid {BORDER_SOFT};
}}

/* ---------- Barra lateral ---------- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #232C39 0%, {NAVY} 42%, #19212C 100%);
    border-right: none;
    box-shadow: inset -1px 0 0 rgba(255,255,255,.05);
}}
[data-testid="stSidebar"] * {{ color: #E7E9EE !important; }}
[data-testid="stSidebar"] hr {{
    border: none;
    border-top: 1px solid rgba(255,255,255,.09) !important;
    margin: 1rem 0;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .13em;
    color: #8D95A5 !important;
    font-weight: 600;
}}
[data-testid="stSidebar"] .stRadio > div {{ gap: .18rem; }}
[data-testid="stSidebar"] .stRadio label {{
    padding: .52rem .7rem;
    border-radius: {RADIUS_SM};
    border-left: 2px solid transparent;
    transition: background .16s ease, border-color .16s ease;
    font-size: .93rem;
}}
[data-testid="stSidebar"] .stRadio label:hover {{ background: rgba(255,255,255,.06); }}
[data-testid="stSidebar"] .stRadio label:has(input:checked) {{
    background: rgba(240,8,74,.16);
    border-left-color: {RED};
    font-weight: 600;
}}
[data-testid="stSidebar"] .stRadio label > div:first-child {{ display: none; }}

/* ---------- Botões ---------- */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
    background: {SURFACE};
    color: {NAVY} !important;
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    font-weight: 550;
    font-size: .9rem;
    padding: .5rem 1rem;
    box-shadow: {SHADOW_SM};
    transition: all .16s ease;
}}
.stButton > button:hover, .stFormSubmitButton > button:hover,
.stDownloadButton > button:hover {{
    border-color: {RED};
    color: {RED} !important;
    box-shadow: {SHADOW_MD};
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background: linear-gradient(180deg, {RED} 0%, {RED_DARK} 100%);
    color: #FFF !important;
    border-color: transparent;
    box-shadow: 0 2px 8px rgba(240,8,74,.28);
}}
.stButton > button[kind="primary"]:hover {{
    color: #FFF !important;
    box-shadow: 0 4px 14px rgba(240,8,74,.34);
}}
[data-testid="stSidebar"] .stButton > button {{
    background: rgba(255,255,255,.05);
    border: 1px solid rgba(255,255,255,.13);
    box-shadow: none;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255,255,255,.11);
    border-color: rgba(255,255,255,.22);
    color: #FFF !important;
    transform: none;
}}

/* ---------- Métricas ---------- */
[data-testid="stMetric"] {{
    position: relative;
    background: {SURFACE};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS};
    padding: 1.05rem 1.25rem 1rem;
    box-shadow: {SHADOW_MD};
    overflow: hidden;
    transition: box-shadow .18s ease, transform .18s ease;
}}
[data-testid="stMetric"]::before {{
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 3px;
    background: linear-gradient(90deg, {RED} 0%, {RED_DARK} 100%);
}}
[data-testid="stMetric"]:hover {{
    box-shadow: {SHADOW_LG};
    transform: translateY(-2px);
}}
[data-testid="stMetricLabel"] p {{
    color: {TEXT_MUTED};
    font-size: .74rem !important;
    font-weight: 600;
    letter-spacing: .07em;
    text-transform: uppercase;
}}
[data-testid="stMetricValue"] {{
    font-size: 2rem;
    font-weight: 660;
    letter-spacing: -.03em;
    color: {NAVY};
}}
[data-testid="stMetricDelta"] {{ font-size: .8rem; font-weight: 550; }}

/* ---------- Abas ---------- */
.stTabs [data-baseweb="tab-list"] {{
    gap: .25rem;
    background: {SURFACE_SUNK};
    padding: .3rem;
    border-radius: 10px;
    border-bottom: none;
    width: fit-content;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent;
    color: {TEXT_MUTED};
    font-weight: 550;
    font-size: .9rem;
    border-radius: 7px;
    padding: .42rem 1rem;
    border: none !important;
    transition: all .16s ease;
}}
.stTabs [data-baseweb="tab"]:hover {{ color: {NAVY}; }}
.stTabs [aria-selected="true"] {{
    background: {SURFACE} !important;
    color: {NAVY} !important;
    box-shadow: {SHADOW_SM};
}}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}
.stTabs [data-baseweb="tab-panel"] {{ padding-top: 1.4rem; }}

/* ---------- Gráficos ---------- */
[data-testid="stPlotlyChart"] {{
    background: {SURFACE};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS};
    padding: .55rem .6rem .45rem;   /* simétrico: o gráfico fica centrado no cartão */
    box-shadow: {SHADOW_MD};
    overflow: hidden;
}}
[data-testid="stPlotlyChart"] > div, [data-testid="stPlotlyChart"] .js-plotly-plot {{
    width: 100% !important;
}}
[data-testid="stPlotlyChart"] .modebar {{ opacity: 0; transition: opacity .2s ease; }}
[data-testid="stPlotlyChart"]:hover .modebar {{ opacity: .55; }}

/* ---------- Tabelas ---------- */
[data-testid="stDataFrame"], [data-testid="stTable"] {{
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS};
    overflow: hidden;
    box-shadow: {SHADOW_SM};
}}

/* ---------- Expansores ---------- */
[data-testid="stExpander"] {{
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS};
    background: {SURFACE};
    box-shadow: {SHADOW_SM};
    overflow: hidden;
}}
[data-testid="stExpander"] summary {{ font-weight: 550; font-size: .92rem; }}
[data-testid="stExpander"] summary:hover {{ color: {RED}; }}

/* ---------- Avisos ---------- */
[data-testid="stAlert"] {{
    border-radius: {RADIUS_SM};
    border: 1px solid {BORDER_SOFT};
    border-left-width: 3px;
    box-shadow: {SHADOW_SM};
    padding: .8rem 1rem;
    font-size: .9rem;
}}

/* ---------- Campos ---------- */
.stTextInput input, .stNumberInput input, .stTextArea textarea,
[data-baseweb="select"] > div {{
    border-radius: {RADIUS_SM} !important;
    border-color: {BORDER} !important;
    background: {SURFACE} !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {RED} !important;
    box-shadow: 0 0 0 3px rgba(240,8,74,.10) !important;
}}
[data-baseweb="tag"] {{
    background: {NAVY} !important;
    border-radius: 6px !important;
}}
.stMultiSelect label, .stSelectbox label, .stTextInput label, .stRadio label p {{
    font-size: .82rem;
    font-weight: 550;
    color: {TEXT_MUTED};
}}

/* ---------- Chat ---------- */
[data-testid="stChatMessage"] {{
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS};
    background: {SURFACE};
    box-shadow: {SHADOW_SM};
    padding: 1rem 1.2rem;
}}

/* ---------- Separadores e rolagem ---------- */
hr {{
    border: none;
    border-top: 1px solid {BORDER_SOFT};
    margin: 1.9rem 0 1.5rem;
}}
[data-testid="stCaptionContainer"] p {{
    color: {TEXT_MUTED};
    font-size: .81rem;
    line-height: 1.55;
}}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{
    background: #CBD1DA;
    border-radius: 10px;
    border: 2px solid {BG};
}}
::-webkit-scrollbar-thumb:hover {{ background: #AEB6C2; }}

/* ---------- Blocos próprios ---------- */
.po-section {{
    display: flex;
    align-items: center;
    gap: .65rem;
    margin: .2rem 0 .85rem;
}}
.po-section-ico {{
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px; height: 30px;
    border-radius: {RADIUS_SM};
    background: linear-gradient(180deg, #FDEDF1 0%, #FCE1E8 100%);
    color: {RED};
    flex: 0 0 auto;
}}
.po-section-tt {{
    font-size: 1.02rem;
    font-weight: 620;
    color: {NAVY};
    letter-spacing: -.015em;
    line-height: 1.25;
}}
.po-section-sub {{
    font-size: .79rem;
    color: {TEXT_MUTED};
    margin-top: .1rem;
    line-height: 1.35;
}}

.po-eyebrow {{
    display: flex;
    align-items: center;
    gap: .55rem;
    font-size: .71rem;
    font-weight: 650;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: {TEXT_MUTED};
    margin: 2.1rem 0 .9rem;
}}
.po-eyebrow::after {{
    content: "";
    flex: 1 1 auto;
    height: 1px;
    background: linear-gradient(90deg, {BORDER} 0%, rgba(227,230,235,0) 100%);
}}

.po-legend {{
    display: flex;
    flex-wrap: wrap;
    gap: .3rem .95rem;
    font-size: .78rem;
    color: {TEXT_MUTED};
    margin-top: .45rem;
}}
.po-legend span.d {{
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: .38rem;
    vertical-align: middle;
}}

.po-chip {{
    display: inline-flex;
    align-items: center;
    gap: .45rem;
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-left: 3px solid {RED};
    border-radius: {RADIUS_SM};
    padding: .5rem .85rem;
    font-size: .87rem;
    color: {NAVY};
    box-shadow: {SHADOW_SM};
}}

.po-hero {{
    background: linear-gradient(135deg, {NAVY} 0%, #2B3644 55%, #34202E 100%);
    border-radius: 16px;
    padding: 1.6rem 1.9rem;
    color: #EDEFF3;
    box-shadow: 0 8px 26px rgba(31,39,51,.20);
    position: relative;
    overflow: hidden;
    margin-bottom: 1.4rem;
}}
.po-hero::after {{
    content: "";
    position: absolute;
    right: -70px; top: -90px;
    width: 260px; height: 260px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(240,8,74,.30) 0%, rgba(240,8,74,0) 70%);
}}
.po-hero h1 {{
    color: #FFFFFF;
    font-size: 1.75rem;
    margin: 0 0 .35rem;
    letter-spacing: -.025em;
}}
.po-hero p {{
    margin: 0;
    color: #A9B2C1;
    font-size: .92rem;
    line-height: 1.55;
    max-width: 80ch;
}}
.po-hero code {{
    background: rgba(255,255,255,.10);
    border-color: rgba(255,255,255,.14);
    color: #EDEFF3;
}}
</style>
"""


def apply_theme() -> None:
    """Injeta o CSS da identidade visual na página atual."""
    st.markdown(_CSS, unsafe_allow_html=True)


def render_brand_header(small: bool = False) -> None:
    """Logotipo 'predictops' no padrão tipográfico da Locaweb."""
    size = "1.25rem" if small else "1.9rem"
    st.markdown(
        f"""
        <div style="line-height:1;letter-spacing:-.03em;">
            <span style="font-size:{size};font-weight:700;color:{NAVY_LIGHT};">predict</span
            ><span style="font-size:{size};font-weight:700;color:{RED};">ops</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(titulo: str, sub: str = "", ico: str = "chart") -> None:
    """Cabeçalho de bloco: ícone monoline + título + linha de apoio opcional."""
    sub_html = f'<div class="po-section-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="po-section"><div class="po-section-ico">{icon(ico, 17)}</div>'
        f'<div><div class="po-section-tt">{titulo}</div>{sub_html}</div></div>',
        unsafe_allow_html=True,
    )


def eyebrow(texto: str) -> None:
    """Rótulo de agrupamento entre seções, com filete degradê."""
    st.markdown(f'<div class="po-eyebrow">{texto}</div>', unsafe_allow_html=True)


def hero(titulo: str, descricao: str = "") -> None:
    """Cabeçalho de página com fundo escuro da marca."""
    desc = f"<p>{descricao}</p>" if descricao else ""
    st.markdown(f'<div class="po-hero"><h1>{titulo}</h1>{desc}</div>',
                unsafe_allow_html=True)


def legend(itens) -> None:
    """Legenda de cores com discos, no lugar de emojis de círculo colorido.

    `itens` é uma sequência de (cor, texto).
    """
    partes = "".join(
        f'<span><span class="d" style="background:{cor}"></span>{txt}</span>'
        for cor, txt in itens)
    st.markdown(f'<div class="po-legend">{partes}</div>', unsafe_allow_html=True)


def chip(texto: str, ico: str = "filter") -> None:
    """Etiqueta de estado (ex.: cross-filter ativo)."""
    st.markdown(f'<div class="po-chip">{icon(ico, 15)}<span>{texto}</span></div>',
                unsafe_allow_html=True)


# Legenda padrão das faixas de risco, reaproveitada nas telas.
LEGENDA_RISCO = [
    (RISK_RED, "&gt;90% Crítico"),
    (RISK_ORANGE, "75–90% Alto"),
    (RISK_YELLOW, "60–75% Médio"),
    (RISK_GREEN, "&lt;60% Baixo"),
]
