"""Dashboard interativo (Streamlit) consumindo a API."""
import base64
import html
import json
import os
import time
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st
import streamlit.components.v1 as components

from tx_edits import diff_rows  # mesmo diretorio (dashboard/): o Streamlit o poe no sys.path

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 20
# Fuso do "dia do usuario" (o mesmo da API): define "hoje" e a hora exibida, em vez do fuso do servidor
APP_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "America/Sao_Paulo"))
# Sessao persistida em cookie para sobreviver ao F5 (REMEMBER_SESSION=false desliga)
REMEMBER_SESSION = os.getenv("REMEMBER_SESSION", "true").strip().lower() not in ("0", "false", "no", "off")
SESSION_COOKIE = "ya_session"
# Paleta no estilo do portfolio: preto + verde-menta. Ambar so para linhas de tendencia.
GREEN, RED, AMBER = "#34D399", "#F87171", "#FBBF24"
BG, SURFACE, BORDER, MUTED, TEXT = "#07090C", "#0D1117", "#1C222B", "#8B96A5", "#E8EEF5"
PAGE_SIZE = 25

st.set_page_config(
    page_title="Dashboard Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# O Streamlit serve a pagina com lang="en"; tradutores do navegador (ex.: Chrome Translate) entao
# reescrevem o DOM e quebram as atualizacoes (valores presos, abas misturadas, textos truncados).
# Marcamos a pagina como pt-BR e "nao traduzir".
components.html(
    """<script>
    const d = window.parent.document;
    d.documentElement.setAttribute('lang', 'pt-BR');
    d.documentElement.setAttribute('translate', 'no');
    if (!d.querySelector('meta[name="google"]')) {
      const m = d.createElement('meta'); m.name = 'google'; m.content = 'notranslate'; d.head.appendChild(m);
    }
    </script>""",
    height=0,
)

# ---------------------------------------------------------------- Tema
pio.templates["dark_green"] = go.layout.Template(
    layout=dict(
        paper_bgcolor=SURFACE, plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=12),
        colorway=[GREEN, AMBER, RED, TEXT, MUTED],
        xaxis=dict(gridcolor="#161D27", zerolinecolor=BORDER, linecolor=BORDER, automargin=True, title=dict(standoff=14)),
        yaxis=dict(gridcolor="#161D27", zerolinecolor=BORDER, linecolor=BORDER, automargin=True, title=dict(standoff=14)),
        legend=dict(font=dict(color=MUTED)),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=GREEN, font=dict(color=TEXT)),
    )
)
pio.templates.default = "dark_green"

THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, .stApp, [class*="css"] {{ font-family: 'Geist', 'Inter', system-ui, sans-serif; }}
code, pre, kbd, .mono, div[data-testid="stCaptionContainer"], label p {{ font-family: 'JetBrains Mono', ui-monospace, monospace; }}

/* fundo: grade sutil + brilho verde no topo */
.stApp {{
    background-color: {BG};
    background-image:
        radial-gradient(ellipse 70% 38% at 50% 0%, rgba(52,211,153,0.14), transparent 70%),
        linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
    background-size: 100% 100%, 64px 64px, 64px 64px;
    background-attachment: fixed;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.5rem; padding-bottom: 4rem; max-width: 1320px; }}

/* titulos */
h1 {{ font-weight: 700 !important; letter-spacing: -0.035em !important; line-height: 1.05 !important;
     background: linear-gradient(180deg, #FFFFFF 30%, #A7F3D0 100%); -webkit-background-clip: text;
     background-clip: text; -webkit-text-fill-color: transparent; }}
h2, h3 {{ font-weight: 600 !important; letter-spacing: -0.02em !important; margin-top: .6rem; padding-bottom: .4rem !important; }}
.stApp h3::before {{ content: "$ "; font-family: 'JetBrains Mono', monospace; color: {GREEN}; font-weight: 500; }}
div[data-testid="stCaptionContainer"] {{ color: {MUTED}; font-size: 0.8rem; }}

/* selo "disponivel" com ponto de status */
.ya-badge {{ display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px; margin-bottom: 14px;
            border: 1px solid {BORDER}; border-radius: 999px; background: rgba(13,17,23,0.7);
            font: 500 12px 'JetBrains Mono', monospace; color: {MUTED}; }}
.ya-badge::before {{ content: ""; width: 8px; height: 8px; border-radius: 50%; background: {GREEN};
                    box-shadow: 0 0 0 3px rgba(52,211,153,0.2), 0 0 10px {GREEN}; }}

/* sidebar */
section[data-testid="stSidebar"] {{ background: rgba(10,13,18,0.92); border-right: 1px solid {BORDER}; }}
section[data-testid="stSidebar"] h1 {{ font-size: 1.15rem; font-family: 'JetBrains Mono', monospace;
    -webkit-text-fill-color: {TEXT}; background: none; letter-spacing: -0.01em !important; }}
section[data-testid="stSidebar"] h3::before {{ content: "> "; }}

/* espacamento entre colunas/blocos */
div[data-testid="stHorizontalBlock"] {{ gap: 1.1rem; align-items: stretch; }}
div[data-testid="stVerticalBlock"] {{ gap: 1.1rem; }}

/* cards de metricas: mesma altura, conteudo alinhado ao topo, mais respiro */
div[data-testid="stMetric"] {{ background: linear-gradient(180deg, rgba(17,22,30,0.9), rgba(10,13,18,0.9));
    border: 1px solid {BORDER}; border-radius: 16px; padding: 22px 24px; min-height: 148px; box-sizing: border-box;
    display: flex; flex-direction: column; justify-content: flex-start; gap: 6px;
    transition: border-color .2s, box-shadow .2s; }}
div[data-testid="stMetric"]:hover {{ border-color: rgba(52,211,153,0.45); box-shadow: 0 0 24px rgba(52,211,153,0.08); }}
div[data-testid="stMetricLabel"] p {{ color: {MUTED}; font: 500 11px 'JetBrains Mono', monospace;
    text-transform: uppercase; letter-spacing: 0.08em; white-space: normal; line-height: 1.4; }}
div[data-testid="stMetricValue"] {{ font-weight: 600; letter-spacing: -0.02em; font-size: 1.65rem; line-height: 1.2; }}
div[data-testid="stMetricValue"] > div {{ overflow: visible; text-overflow: clip; }}
div[data-testid="stMetricDelta"] {{ font-size: 0.85rem; }}

/* botoes */
button[kind="primary"], button[kind="primaryFormSubmit"] {{
    background: {GREEN}; border: 1px solid {GREEN}; color: #04130D; font-weight: 600; border-radius: 12px;
    box-shadow: 0 8px 24px rgba(52,211,153,0.28); transition: box-shadow .2s, transform .2s; }}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p {{ color: #04130D !important; }}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {{
    background: #5EEAB4; border-color: #5EEAB4; box-shadow: 0 10px 30px rgba(52,211,153,0.42); transform: translateY(-1px); }}
button[kind="primary"]:disabled {{ background: #1C222B; border-color: #1C222B; box-shadow: none; }}
button[kind="primary"]:disabled p {{ color: {MUTED} !important; }}
button[kind="secondary"], button[kind="secondaryFormSubmit"], div[data-testid="stDownloadButton"] button {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; font-weight: 500; }}
button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover, div[data-testid="stDownloadButton"] button:hover {{
    border-color: rgba(52,211,153,0.6); color: {GREEN}; }}
button[kind="secondary"]:hover p, button[kind="secondaryFormSubmit"]:hover p {{ color: {GREEN}; }}

/* abas estilo menu do portfolio */
div[data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid {BORDER}; }}
button[data-baseweb="tab"] p {{ font: 500 12px 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; color: {MUTED}; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color: {GREEN}; }}
div[data-baseweb="tab-highlight"] {{ background-color: {GREEN}; box-shadow: 0 0 10px {GREEN}; }}
div[data-baseweb="tab-border"] {{ background-color: transparent; }}

/* campos, forms, tabelas, graficos */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"], textarea {{
    background: {SURFACE} !important; border-radius: 12px !important; border-color: {BORDER} !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within {{ border-color: {GREEN} !important; }}
div[data-testid="stForm"] {{ background: rgba(13,17,23,0.7); border: 1px solid {BORDER}; border-radius: 16px; padding: 1.4rem 1.4rem 1.2rem; }}
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {{ border: 1px solid {BORDER}; border-radius: 16px; overflow: hidden; }}
div[data-testid="stPlotlyChart"] {{ border: 1px solid {BORDER}; border-radius: 16px; overflow: hidden; padding: 0; background: {SURFACE}; }}
div[data-testid="stProgress"] > div > div > div {{ background-color: {GREEN}; }}
hr {{ border-color: {BORDER}; }}

/* avisos neutros */
.ya-info {{ background: rgba(52,211,153,0.07); border: 1px solid rgba(52,211,153,0.3); border-radius: 12px;
           padding: 12px 16px; color: {TEXT}; margin-bottom: 1rem; font-size: 0.92rem; }}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)


def badge(text: str):
    st.markdown('<span class="ya-badge">' + html.escape(text) + "</span>", unsafe_allow_html=True)


def info(message: str):
    """Aviso neutro na cor da marca (no lugar do st.info azul)."""
    st.markdown('<div class="ya-info">' + html.escape(str(message)) + "</div>", unsafe_allow_html=True)


def show_chart(fig):
    """theme=None mantem o template amarelo/preto em vez do tema padrao do Streamlit."""
    st.plotly_chart(fig, use_container_width=True, theme=None)


st.session_state.setdefault("token", None)
st.session_state.setdefault("username", None)


def today_local() -> date:
    return datetime.now(APP_TZ).date()


# ------------------------------------------------------------------ API
class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _logout():
    st.session_state.token = None
    st.session_state.username = None
    st.session_state._cookie_checked = True  # o cookie so e apagado no proximo run: nao restaurar a sessao
    st.session_state._cookie_op = ("clear", None)
    st.cache_data.clear()


def _request(method: str, path: str, token: Optional[str] = None, **kwargs) -> requests.Response:
    headers = {"Authorization": "Bearer " + token} if token else {}
    try:
        resp = requests.request(method, API_URL + path, headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise ApiError(0, "Não foi possível conectar à API (" + API_URL + "): " + str(exc)) from exc
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        if isinstance(detail, list):  # erro de validação (422)
            detail = "; ".join(str(d.get("msg", d)) for d in detail)
        raise ApiError(resp.status_code, str(detail))
    return resp


def api(method: str, path: str, **kwargs) -> requests.Response:
    """Chamada autenticada; sessão expirada (401) faz logout automático."""
    try:
        return _request(method, path, st.session_state.token, **kwargs)
    except ApiError as exc:
        if exc.status == 401:
            _logout()
            st.rerun()
        raise


# ------------------------------------------------------- Sessao (cookie)
# O Streamlit nao consegue gravar cookies pelo servidor; o cookie e gravado por um snippet JS no
# documento pai (mesma origem) e lido de volta em st.context.cookies no carregamento seguinte.
# Mitigacoes: SameSite=Strict, Secure em https, validade = a do JWT e revogacao no servidor
# (trocar a senha invalida o token). O snippet roda no run SEGUINTE ao login/logout, porque o
# st.rerun() imediato impediria o componente de renderizar.
def _token_ttl_seconds(token: str) -> int:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return max(int(json.loads(base64.urlsafe_b64decode(payload))["exp"] - time.time()), 0)
    except Exception:
        return 3600


def sync_session_cookie():
    op = st.session_state.pop("_cookie_op", None)
    if not op:
        return
    kind, token = op
    if kind == "set" and REMEMBER_SESSION and token:
        max_age, value = _token_ttl_seconds(token), token
    else:
        max_age, value = 0, ""
    js = (
        "const d = window.parent.document;"
        "const secure = window.parent.location.protocol === 'https:' ? '; Secure' : '';"
        f"d.cookie = {json.dumps(SESSION_COOKIE)} + '=' + {json.dumps(value)} + "
        f"'; path=/; max-age={max_age}; SameSite=Strict' + secure;"
    ).replace("</", "<\\/")
    components.html(f"<script>{js}</script>", height=0)


def restore_session():
    """Primeiro run de uma sessao nova (ex.: apos F5): recupera o login a partir do cookie."""
    if st.session_state.token is not None or st.session_state.get("_cookie_checked"):
        return
    st.session_state._cookie_checked = True
    if not REMEMBER_SESSION:
        return
    token = st.context.cookies.get(SESSION_COOKIE)
    if not token:
        return
    try:
        me = _request("GET", "/auth/me", token).json()
    except ApiError as exc:
        if exc.status == 401:  # expirado/revogado: limpa o cookie. API fora do ar (status 0): mantem
            st.session_state._cookie_op = ("clear", None)
        return
    st.session_state.token = token
    st.session_state.username = me.get("username")


@st.cache_data(ttl=20, show_spinner=False)
def fetch_overview(token: str, days: int) -> dict:
    return _request("GET", "/analytics/overview?days=" + str(days), token).json()


@st.cache_data(ttl=20, show_spinner=False)
def fetch_categories(token: str) -> list:
    return _request("GET", "/transactions/categories", token).json()


@st.cache_data(ttl=20, show_spinner=False)
def fetch_accounts(token: str) -> list:
    return _request("GET", "/accounts/", token).json()


@st.cache_data(ttl=20, show_spinner=False)
def fetch_me(token: str) -> dict:
    return _request("GET", "/auth/me", token).json()


def flash(message: str):
    """Mensagem que sobrevive ao st.rerun() (que refresh() dispara)."""
    st.session_state._flash = message


def show_flash():
    message = st.session_state.pop("_flash", None)
    if message:
        st.success(message)


def account_label(accounts: list):
    names = {a["id"]: a["name"] for a in accounts}
    return lambda account_id: "Sem conta" if account_id is None else names.get(account_id, str(account_id))


def money(value) -> str:
    """R$ 1.234,56 (formato brasileiro)."""
    if value is None:
        return "—"
    text = f"{value:,.2f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_delta(pct):
    return None if pct is None else f"{pct:+.1f}%"


def refresh():
    st.cache_data.clear()
    st.rerun()


def show_insight(ins: dict):
    {"warning": st.warning, "success": st.success}.get(ins["level"], info)(ins["message"])


# ----------------------------------------------------------------- Auth
def _clear_link_params():
    st.query_params.clear()
    st.rerun()


def render_email_links() -> bool:
    """Trata os links enviados por e-mail (?verify_token=... e ?reset_token=...). True se tratou."""
    verify_token = st.query_params.get("verify_token")
    reset_token = st.query_params.get("reset_token")
    if not verify_token and not reset_token:
        return False

    badge("link do e-mail")
    st.title("Dashboard Analytics")
    if verify_token:
        if "_verify_result" not in st.session_state:  # um unico POST por abertura do link
            try:
                _request("POST", "/auth/verify-email", json={"token": verify_token})
                st.session_state._verify_result = (True, "E-mail verificado com sucesso!")
            except ApiError as exc:
                st.session_state._verify_result = (False, exc.detail)
        ok, message = st.session_state._verify_result
        (st.success if ok else st.error)(message)
        if st.button("Continuar", type="primary"):
            st.session_state.pop("_verify_result", None)
            _clear_link_params()
        return True

    st.subheader("Criar nova senha")
    if st.session_state.get("_reset_done"):
        st.success("Senha alterada! Entre com a nova senha.")
        if st.button("Ir para o login", type="primary"):
            st.session_state.pop("_reset_done", None)
            _clear_link_params()
        return True
    with st.form("reset_form"):
        new_pass = st.text_input("Nova senha (mín. 8 caracteres)", type="password")
        new_pass2 = st.text_input("Confirme a nova senha", type="password")
        if st.form_submit_button("Salvar nova senha", use_container_width=True, type="primary"):
            if new_pass != new_pass2:
                st.error("As senhas não coincidem.")
            else:
                try:
                    _request("POST", "/auth/reset-password", json={"token": reset_token, "new_password": new_pass})
                    st.session_state._reset_done = True
                    st.rerun()
                except ApiError as exc:
                    st.error(exc.detail)
    return True


def render_auth():
    badge("acesso seguro")
    st.title("Dashboard Analytics")
    st.caption("Faça login ou crie sua conta para acessar o painel.")
    tab_login, tab_register, tab_forgot = st.tabs(["Entrar", "Criar conta", "Esqueci a senha"])

    with tab_forgot:
        st.caption("Informe o e-mail da conta e enviaremos um link para criar uma nova senha.")
        with st.form("forgot_form"):
            email = st.text_input("E-mail")
            if st.form_submit_button("Enviar link", use_container_width=True):
                try:
                    msg = _request("POST", "/auth/forgot-password", json={"email": email}).json()["detail"]
                    st.success(msg)
                except ApiError as exc:
                    st.error(exc.detail)

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                try:
                    resp = _request("POST", "/auth/login", data={"username": username, "password": password})
                    st.session_state.token = resp.json()["access_token"]
                    st.session_state.username = username.strip().lower()
                    st.session_state._cookie_op = ("set", st.session_state.token)
                    st.rerun()
                except ApiError as exc:
                    st.error(exc.detail)

    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("Usuário (letras, números, _ . -)")
            new_email = st.text_input("E-mail")
            new_pass = st.text_input("Senha (mín. 8 caracteres)", type="password")
            new_pass2 = st.text_input("Confirme a senha", type="password")
            if st.form_submit_button("Cadastrar", use_container_width=True):
                if new_pass != new_pass2:
                    st.error("As senhas não coincidem.")
                else:
                    try:
                        _request(
                            "POST",
                            "/auth/register",
                            json={"username": new_user, "email": new_email, "password": new_pass},
                        )
                        st.success(
                            "Cadastro realizado! Enviamos um link de confirmação para o seu e-mail. "
                            "Faça login na aba “Entrar”."
                        )
                    except ApiError as exc:
                        st.error(exc.detail)


# -------------------------------------------------------------- Sidebar
def render_sidebar() -> int:
    st.sidebar.title("● dashboard.analytics")
    st.sidebar.write("Usuário: **" + str(st.session_state.username) + "**")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("🔄 Atualizar", use_container_width=True):
        refresh()
    if c2.button("Sair", use_container_width=True):
        _logout()
        st.rerun()

    st.sidebar.divider()
    days = st.sidebar.select_slider(
        "Período", options=[7, 14, 30, 60, 90, 180, 365], value=30, format_func=lambda d: f"{d} dias"
    )

    st.sidebar.divider()
    st.sidebar.subheader("Relatório")
    if st.sidebar.button("📄 Gerar PDF do período", use_container_width=True):
        try:
            st.session_state.pdf_report = (days, api("GET", "/analytics/report.pdf", params={"days": days}).content)
        except ApiError as exc:
            st.sidebar.error(exc.detail)
    report = st.session_state.get("pdf_report")
    if report and report[0] == days:
        st.sidebar.download_button("⬇️ Baixar PDF", report[1], file_name=f"relatorio_{days}d.pdf",
                                   mime="application/pdf", use_container_width=True)

    st.sidebar.divider()
    st.sidebar.subheader("Nova transação")
    new_cat_label = "➕ nova categoria…"
    categories = fetch_categories(st.session_state.token)
    with st.sidebar.form("new_tx", clear_on_submit=True):
        desc = st.text_input("Descrição")
        amount = st.number_input("Valor (R$)", min_value=0.01, step=1.0, format="%.2f")
        tx_type = st.selectbox(
            "Tipo", ["expense", "income"], format_func=lambda t: "Despesa" if t == "expense" else "Receita"
        )
        accounts = fetch_accounts(st.session_state.token)
        account_id = st.selectbox(
            "Conta", [None] + [a["id"] for a in accounts], format_func=account_label(accounts)
        )
        cat_choice = st.selectbox("Categoria", categories + [new_cat_label])
        new_cat = st.text_input("Nova categoria (se escolheu “nova” acima)")
        tx_date = st.date_input("Data", value=today_local(), format="DD/MM/YYYY")
        if st.form_submit_button("Adicionar", use_container_width=True, type="primary"):
            category = new_cat.strip() if cat_choice == new_cat_label else cat_choice
            if not desc.strip() or not category:
                st.error("Informe descrição e categoria.")
            else:
                payload = {
                    "description": desc,
                    "amount": float(amount),
                    "category": category,
                    "type": tx_type,
                    "date": datetime.combine(tx_date, datetime.min.time()).isoformat(),
                    "account_id": account_id,
                }
                try:
                    api("POST", "/transactions/", json=payload)
                    refresh()
                except ApiError as exc:
                    st.error(exc.detail)
    return days


# ------------------------------------------------------------- Tab: Geral
def tab_overview(data: dict, days: int):
    s = data["summary"]
    ch = s["comparison"]["change_pct"]

    c1, c2, c3, c4, c5 = st.columns(5, gap="medium")
    c1.metric("Receitas", money(s["total_income"]), fmt_delta(ch["income"]))
    c2.metric("Despesas", money(s["total_expense"]), fmt_delta(ch["expense"]), delta_color="inverse")
    c3.metric("Saldo", money(s["balance"]), fmt_delta(ch["balance"]))
    rate = s["savings_rate"]
    c4.metric("Taxa de poupança", "—" if rate is None else f"{rate:.1f}%")
    c5.metric("Gasto médio por dia", money(s["avg_daily_expense"]))
    st.caption(f"As variações comparam com os {days} dias anteriores.")

    for ins in data["insights"][:3]:
        show_insight(ins)

    ts = pd.DataFrame(data["timeseries"])
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Evolução diária")
        if ts.empty:
            info("Sem dados no período.")
        else:
            fig = go.Figure()
            fig.add_bar(x=ts["day"], y=ts["income"], name="Receita", marker_color=GREEN, opacity=0.8)
            fig.add_bar(x=ts["day"], y=-ts["expense"], name="Despesa", marker_color=RED, opacity=0.8)
            fig.add_scatter(
                x=ts["day"], y=ts["cumulative_balance"], name="Saldo acumulado",
                mode="lines", line=dict(color=AMBER, width=3), yaxis="y2",
            )
            fig.update_layout(
                height=400, barmode="relative", margin=dict(l=24, r=24, t=56, b=24),
                legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                yaxis=dict(title="Fluxo diário (R$)"),
                yaxis2=dict(title="Saldo acumulado (R$)", overlaying="y", side="right", showgrid=False),
            )
            show_chart(fig)

    with right:
        st.subheader("Despesas por categoria")
        cats = [c for c in data["by_category"] if c["type"] == "expense"]
        if not cats:
            info("Sem despesas no período.")
        else:
            dfc = pd.DataFrame(cats).sort_values("amount")
            fig = go.Figure(
                go.Bar(
                    x=dfc["amount"], y=dfc["category"], orientation="h", marker_color=GREEN,
                    text=[f"{p:.0f}%" for p in dfc["share_pct"]], textposition="outside", cliponaxis=False,
                )
            )
            fig.update_layout(height=400, margin=dict(l=24, r=72, t=48, b=24), xaxis_title="R$")
            show_chart(fig)

    st.subheader("Maiores despesas")
    if data["top_expenses"]:
        top = pd.DataFrame(data["top_expenses"])
        top["date"] = pd.to_datetime(top["date"]).dt.strftime("%d/%m/%Y")
        st.dataframe(
            top.rename(columns={"description": "Descrição", "amount": "Valor", "category": "Categoria", "date": "Data"}),
            use_container_width=True, hide_index=True,
            column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")},
        )
    else:
        info("Nenhuma despesa no período.")


# ----------------------------------------------------------- Tab: Análises
def tab_analytics(data: dict):
    st.subheader("Comparativo mensal")
    monthly = pd.DataFrame(data["monthly"])
    if monthly.empty:
        info("Sem histórico suficiente.")
    else:
        fig = go.Figure()
        fig.add_bar(x=monthly["month"], y=monthly["income"], name="Receita", marker_color=GREEN)
        fig.add_bar(x=monthly["month"], y=monthly["expense"], name="Despesa", marker_color=RED)
        fig.add_scatter(
            x=monthly["month"], y=monthly["savings_rate"], name="Poupança (%)",
            mode="lines+markers", yaxis="y2", line=dict(color=AMBER, width=3),
        )
        fig.update_layout(
            height=380, barmode="group", margin=dict(l=24, r=24, t=56, b=24),
            legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
            yaxis2=dict(title="Poupança (%)", overlaying="y", side="right", showgrid=False),
        )
        show_chart(fig)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Gasto por dia da semana")
        wd = pd.DataFrame(data["weekday"])
        fig = go.Figure(go.Bar(x=wd["weekday"], y=wd["total"], marker_color=GREEN))
        fig.update_layout(height=320, margin=dict(l=24, r=24, t=56, b=24), yaxis_title="R$")
        show_chart(fig)

    with col_b:
        st.subheader("Previsão de despesas (30 dias)")
        fc = data["forecast"]
        if not fc.get("available"):
            info(fc.get("reason", "Previsão indisponível."))
        else:
            daily = pd.DataFrame(fc["daily"])
            fig = go.Figure()
            fig.add_scatter(x=daily["day"], y=daily["upper"], mode="lines", line=dict(width=0), showlegend=False)
            fig.add_scatter(
                x=daily["day"], y=daily["lower"], mode="lines", line=dict(width=0),
                fill="tonexty", fillcolor="rgba(251,191,36,0.15)", name="Faixa ~80%",
            )
            fig.add_scatter(x=daily["day"], y=daily["expense"], mode="lines", name="Projeção",
                            line=dict(color=AMBER, width=3))
            fig.update_layout(height=320, margin=dict(l=24, r=24, t=56, b=24), yaxis_title="R$/dia",
                              legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0))
            show_chart(fig)

    if data["forecast"].get("available"):
        fc = data["forecast"]
        m1, m2, m3 = st.columns(3)
        m1.metric("Despesa projetada", money(fc["projected_expense"]))
        m2.metric("Receita projetada", money(fc["projected_income"]))
        m3.metric("Saldo projetado", money(fc["projected_balance"]))
        st.caption(
            f"Método: {fc['method']}. Faixa para o total de despesas: "
            f"{money(fc['projected_expense_lower'])} a {money(fc['projected_expense_upper'])}. "
            "É uma estimativa estatística simples, não uma garantia."
        )

    st.subheader("⚠️ Gastos atípicos")
    if data["anomalies"]:
        an = pd.DataFrame(data["anomalies"])[["date", "description", "category", "amount", "expected", "times_expected"]]
        st.dataframe(
            an.rename(columns={"date": "Data", "description": "Descrição", "category": "Categoria",
                               "amount": "Valor", "expected": "Típico", "times_expected": "× do típico"}),
            use_container_width=True, hide_index=True,
            column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f"),
                           "Típico": st.column_config.NumberColumn(format="R$ %.2f")},
        )
    else:
        st.success("Nenhum gasto fora do padrão no período.")

    st.subheader("🔁 Despesas e receitas recorrentes")
    if data["recurring"]:
        rec = pd.DataFrame(data["recurring"])
        rec["automated"] = rec.get("automated", False)
        rec = rec[["description", "type", "avg_amount", "every_days", "last_date", "next_expected", "automated"]]
        rec["type"] = rec["type"].map({"expense": "Despesa", "income": "Receita"})
        st.dataframe(
            rec.rename(columns={"description": "Descrição", "type": "Tipo", "avg_amount": "Valor médio",
                                "every_days": "A cada (dias)", "last_date": "Última", "next_expected": "Próxima",
                                "automated": "Automática"}),
            use_container_width=True, hide_index=True,
            column_config={"Valor médio": st.column_config.NumberColumn(format="R$ %.2f")},
        )
    else:
        st.caption("Nenhum padrão mensal detectado (precisa de 3+ ocorrências com ~30 dias de intervalo).")
    if data["recurring"] and not all(r.get("automated") for r in data["recurring"]):
        st.caption("Para gerar esses lançamentos sozinhos, use a aba “🧩 Gestão” → Recorrentes.")


# --------------------------------------------------------- Tab: Orçamentos
def tab_budgets(data: dict):
    st.subheader("Orçamento do mês")
    budgets = data["budgets"]
    if not budgets:
        info("Defina limites mensais por categoria para acompanhar o consumo.")
    for b in budgets:
        icon = {"ok": "🟢", "warning": "🟡", "exceeded": "🔴"}[b["status"]]
        left, right = st.columns([4, 1])
        left.markdown(
            f"{icon} **{b['category']}**: {money(b['spent'])} de {money(b['monthly_limit'])} "
            f"({b['pct_used']:.0f}%) · restante {money(b['remaining'])}"
        )
        left.progress(min(b["pct_used"] / 100, 1.0))
        if b["projected_exceeds"] and b["status"] != "exceeded":
            left.caption(f"No ritmo atual deve chegar a {money(b['projected_month_end'])} no fim do mês.")
        if right.button("Remover", key="del_b_" + b["category"]):
            try:
                api("DELETE", "/budgets/" + quote(b["category"], safe=""))
                refresh()
            except ApiError as exc:
                st.error(exc.detail)

    st.divider()
    st.subheader("Definir / atualizar limite")
    known = fetch_categories(st.session_state.token)
    with st.form("budget_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        category = c1.selectbox("Categoria existente", [""] + known)
        custom = c2.text_input("…ou digite uma categoria")
        limit = c3.number_input("Limite (R$)", min_value=1.0, step=50.0, format="%.2f")
        if st.form_submit_button("Salvar limite", type="primary"):
            chosen = (custom or category).strip()
            if not chosen:
                st.error("Escolha ou digite uma categoria.")
            else:
                try:
                    api("PUT", "/budgets/" + quote(chosen, safe=""), json={"monthly_limit": float(limit)})
                    refresh()
                except ApiError as exc:
                    st.error(exc.detail)


# -------------------------------------------------------- Tab: Transações
def tab_transactions():
    st.subheader("Transações")
    categories = fetch_categories(st.session_state.token)

    f1, f2, f3, f4 = st.columns([2, 1, 1, 2])
    q = f1.text_input("Buscar na descrição", key="f_q")
    f_type = f2.selectbox(
        "Tipo", ["", "expense", "income"], key="f_type",
        format_func=lambda t: {"": "Todos", "expense": "Despesa", "income": "Receita"}[t],
    )
    f_cat = f3.selectbox("Categoria", [""] + categories, key="f_cat", format_func=lambda c: c or "Todas")
    period = f4.date_input(
        "Período", value=(today_local() - timedelta(days=90), today_local()), format="DD/MM/YYYY", key="f_period"
    )
    s1, s2 = st.columns(2)
    sort_labels = {"date": "Data", "amount": "Valor", "category": "Categoria", "description": "Descrição"}
    sort_by = s1.selectbox("Ordenar por", list(sort_labels), key="f_sort", format_func=sort_labels.get)
    order = s2.radio(
        "Ordem", ["desc", "asc"], horizontal=True, key="f_order",
        format_func=lambda o: "Maior → menor" if o == "desc" else "Menor → maior",
    )

    params = {}
    if q:
        params["q"] = q
    if f_type:
        params["type"] = f_type
    if f_cat:
        params["category"] = f_cat
    if isinstance(period, (tuple, list)) and len(period) == 2:
        params["start_date"] = datetime.combine(period[0], datetime.min.time()).isoformat()
        params["end_date"] = datetime.combine(period[1], datetime.max.time()).replace(microsecond=0).isoformat()

    page = st.session_state.setdefault("tx_page", 0)
    try:
        resp = api(
            "GET", "/transactions/",
            params={**params, "sort_by": sort_by, "order": order, "skip": page * PAGE_SIZE, "limit": PAGE_SIZE},
        )
    except ApiError as exc:
        st.error(exc.detail)
        return
    total = int(resp.headers.get("X-Total-Count", 0))
    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    if page >= pages:
        st.session_state.tx_page = page = pages - 1

    rows = resp.json()
    st.caption(f"{total} transação(ões) · página {page + 1} de {pages}")
    if rows:
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["Excluir"] = False
        view = df[["Excluir", "id", "date", "description", "category", "type", "amount"]].reset_index(drop=True)
        st.caption("Clique numa célula para editar (descrição, categoria, tipo, valor, data) e salve abaixo.")
        edited = st.data_editor(
            view, hide_index=True, use_container_width=True,
            key=f"tx_editor_{page}_{total}_{st.session_state.setdefault('tx_editor_ver', 0)}",
            disabled=["id"],
            column_config={
                "Excluir": st.column_config.CheckboxColumn("🗑️"),
                "id": "ID",
                "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                "description": st.column_config.TextColumn("Descrição", max_chars=200, required=True),
                "category": st.column_config.TextColumn("Categoria", max_chars=80, required=True),
                "type": st.column_config.SelectboxColumn("Tipo", options=["expense", "income"], required=True),
                "amount": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.01, required=True),
            },
        )
        changes, invalid = diff_rows(
            view.drop(columns=["Excluir"]).to_dict("records"), edited.drop(columns=["Excluir"]).to_dict("records")
        )
        if invalid:
            st.warning(f"{len(invalid)} linha(s) com valor inválido (campo vazio, valor ≤ 0): não serão salvas.")
        if st.button(f"💾 Salvar alterações ({len(changes)})", disabled=not changes, type="primary"):
            failed = []
            for tx_id, payload in changes.items():
                try:
                    api("PUT", f"/transactions/{tx_id}", json=payload)
                except ApiError as exc:
                    failed.append(f"#{tx_id}: {exc.detail}")
            if failed:
                st.error("Algumas alterações falharam: " + "; ".join(failed[:3]))
            else:
                flash(f"{len(changes)} transação(ões) atualizada(s).")
                st.session_state.tx_editor_ver += 1  # descarta o estado do editor (as edicoes ja foram salvas)
                refresh()

        selected = edited.loc[edited["Excluir"], "id"].tolist()
        if st.button(f"Excluir selecionadas ({len(selected)})", disabled=not selected):
            failed = 0
            for tx_id in selected:
                try:
                    api("DELETE", f"/transactions/{int(tx_id)}")
                except ApiError:
                    failed += 1
            if failed:
                st.warning(f"{failed} exclusão(ões) falharam.")
            st.session_state.tx_editor_ver += 1
            refresh()
    else:
        info("Nenhuma transação encontrada com esses filtros.")

    p1, p2, _ = st.columns([1, 1, 6])
    if p1.button("⬅️ Anterior", disabled=page == 0):
        st.session_state.tx_page = page - 1
        st.rerun()
    if p2.button("Próxima ➡️", disabled=page >= pages - 1):
        st.session_state.tx_page = page + 1
        st.rerun()

    st.divider()
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**Exportar (usa os filtros acima)**")
        b1, b2 = st.columns(2)
        if b1.button("Gerar CSV"):
            try:
                st.session_state.csv_export = api("GET", "/transactions/export", params=params).content
            except ApiError as exc:
                st.error(exc.detail)
        if b2.button("Gerar Excel"):
            try:
                st.session_state.xlsx_export = api("GET", "/transactions/export.xlsx", params=params).content
            except ApiError as exc:
                st.error(exc.detail)
        if st.session_state.get("csv_export"):
            b1.download_button("⬇️ Baixar CSV", st.session_state.csv_export,
                               file_name="transacoes.csv", mime="text/csv")
        if st.session_state.get("xlsx_export"):
            b2.download_button(
                "⬇️ Baixar Excel", st.session_state.xlsx_export, file_name="transacoes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    with e2:
        st.markdown("**Importar CSV ou OFX**")
        st.caption("CSV: descricao, valor, categoria, tipo (receita/despesa), data (`;` ou `,`). OFX: extrato do banco.")
        skip_dups = st.checkbox(
            "Pular transações repetidas", value=True,
            help="Compara dia + valor + descrição + tipo com o que você já tem. Reimportar o mesmo arquivo não duplica.",
        )
        accounts = fetch_accounts(st.session_state.token)
        import_account = st.selectbox(
            "Vincular à conta", [None] + [a["id"] for a in accounts], format_func=account_label(accounts),
            key="import_account",
        )
        up = st.file_uploader("Arquivo", type=["csv", "ofx", "qfx"], label_visibility="collapsed")
        if up is not None and st.button("Importar arquivo"):
            import_params = {"skip_duplicates": str(skip_dups).lower()}
            if import_account:
                import_params["account_id"] = import_account
            try:
                result = api("POST", "/transactions/import", params=import_params,
                             files={"file": (up.name, up.getvalue(), "application/octet-stream")}).json()
                st.success(
                    f"{result['imported']} importada(s), {result.get('duplicates', 0)} repetida(s) ignorada(s), "
                    f"{result['skipped']} com erro."
                )
                for err in result["errors"][:5]:
                    st.caption(f"Linha {err['row']}: {err['error']}")
                st.cache_data.clear()
            except ApiError as exc:
                st.error(exc.detail)


# --------------------------------------------------------- Tab: Insights
def tab_insights(data: dict):
    st.subheader("Insights automáticos")
    if not data["insights"]:
        info("Cadastre mais transações para gerar insights.")
    for ins in data["insights"]:
        show_insight(ins)


# ------------------------------------------------------------ Tab: Gestão
ACCOUNT_TYPES = {"checking": "Conta corrente", "savings": "Poupança", "cash": "Dinheiro",
                 "credit": "Cartão de crédito", "investment": "Investimentos"}
FREQUENCIES = {"weekly": "Semanal", "monthly": "Mensal", "yearly": "Anual"}


def _call(method: str, path: str, ok_message: str = "", **kwargs):
    """Chama a API; em sucesso guarda a mensagem e recarrega. Em erro mostra o motivo. True se deu certo."""
    try:
        api(method, path, **kwargs)
    except ApiError as exc:
        st.error(exc.detail)
        return False
    if ok_message:
        flash(ok_message)
    refresh()
    return True


def manage_categories():
    st.markdown("#### Categorias")
    st.caption("Renomear ou unir atualiza transações, recorrentes e orçamentos de uma vez. "
               "Ao unir, o limite de orçamento da categoria de destino prevalece.")
    cats = api("GET", "/categories/").json()
    if not cats:
        info("Nenhuma categoria ainda: elas aparecem conforme você cadastra transações.")
        return
    table = pd.DataFrame(cats).rename(
        columns={"category": "Categoria", "transactions": "Transações", "budget_limit": "Orçamento mensal"}
    )
    st.dataframe(table, hide_index=True, use_container_width=True,
                 column_config={"Orçamento mensal": st.column_config.NumberColumn(format="R$ %.2f")})
    names = [c["category"] for c in cats]

    c1, c2 = st.columns(2)
    with c1, st.form("rename_cat_form", clear_on_submit=True):
        st.markdown("**Renomear**")
        old = st.selectbox("Categoria", names)
        new = st.text_input("Novo nome (se já existir, as duas são unidas)")
        if st.form_submit_button("Renomear", use_container_width=True):
            if not new.strip():
                st.error("Informe o novo nome.")
            else:
                try:
                    res = api("PUT", "/categories/" + quote(old, safe=""), json={"new_name": new}).json()
                    flash(f"{res['transactions_updated']} transação(ões) movida(s) para “{res['target']}”"
                          + (" (categorias unidas)." if res["merged"] else "."))
                    refresh()
                except ApiError as exc:
                    st.error(exc.detail)
    with c2, st.form("merge_cat_form", clear_on_submit=True):
        st.markdown("**Unir várias**")
        sources = st.multiselect("Categorias de origem", names)
        target = st.text_input("Categoria de destino")
        if st.form_submit_button("Unir", use_container_width=True):
            if not sources or not target.strip():
                st.error("Escolha as origens e informe o destino.")
            else:
                try:
                    res = api("POST", "/categories/merge", json={"sources": sources, "target": target}).json()
                    flash(f"{res['transactions_updated']} transação(ões) movida(s) para “{res['target']}”.")
                    refresh()
                except ApiError as exc:
                    st.error(exc.detail)


def manage_accounts():
    st.markdown("#### Contas e carteiras")
    accounts = fetch_accounts(st.session_state.token)
    if accounts:
        table = pd.DataFrame(accounts)
        table["type"] = table["type"].map(ACCOUNT_TYPES).fillna(table["type"])
        st.dataframe(
            table[["name", "type", "initial_balance", "income", "expense", "balance", "transaction_count"]].rename(
                columns={"name": "Conta", "type": "Tipo", "initial_balance": "Saldo inicial", "income": "Receitas",
                         "expense": "Despesas", "balance": "Saldo atual", "transaction_count": "Transações"}),
            hide_index=True, use_container_width=True,
            column_config={c: st.column_config.NumberColumn(format="R$ %.2f")
                           for c in ("Saldo inicial", "Receitas", "Despesas", "Saldo atual")},
        )
        st.metric("Saldo total das contas", money(sum(a["balance"] for a in accounts)))
    else:
        info("Cadastre contas (banco, carteira, cartão) para ver o saldo de cada uma.")

    with st.form("account_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 2])
        name = c1.text_input("Nome da conta")
        acc_type = c2.selectbox("Tipo", list(ACCOUNT_TYPES), format_func=ACCOUNT_TYPES.get)
        initial = c3.number_input("Saldo inicial (R$)", value=0.0, step=100.0, format="%.2f")
        if st.form_submit_button("Criar conta", type="primary"):
            if not name.strip():
                st.error("Informe o nome da conta.")
            else:
                _call("POST", "/accounts/", f"Conta “{name.strip()}” criada.",
                      json={"name": name, "type": acc_type, "initial_balance": float(initial)})
    if accounts:
        d1, d2 = st.columns([3, 1])
        to_delete = d1.selectbox("Excluir conta (as transações ficam sem conta)", [a["id"] for a in accounts],
                                 format_func=account_label(accounts), key="del_account")
        if d2.button("Excluir conta"):
            _call("DELETE", f"/accounts/{to_delete}", "Conta excluída.")


def manage_goals():
    st.markdown("#### Metas de poupança")
    goals = api("GET", "/goals/").json()
    if not goals:
        info("Crie uma meta (viagem, reserva de emergência…) e registre quanto já guardou.")
    status_icon = {"active": "🟢", "completed": "✅", "overdue": "🔴"}
    for g in goals:
        left, mid, right = st.columns([4, 2, 1])
        deadline = f" · prazo {datetime.fromisoformat(g['deadline']).strftime('%d/%m/%Y')}" if g["deadline"] else ""
        left.markdown(f"{status_icon[g['status']]} **{g['name']}**: {money(g['saved_amount'])} de "
                      f"{money(g['target_amount'])} ({g['pct']:.0f}%){deadline}")
        left.progress(min(g["pct"] / 100, 1.0))
        if g["required_monthly"] is not None:
            left.caption(f"Para chegar no prazo: guardar {money(g['required_monthly'])} por mês.")
        elif g["status"] == "overdue":
            left.caption("Prazo vencido. Faltam " + money(g["remaining"]) + ".")
        amount = mid.number_input("Valor (R$)", min_value=0.01, step=50.0, format="%.2f", key=f"g_amt_{g['id']}")
        b1, b2 = mid.columns(2)
        if b1.button("Guardar", key=f"g_add_{g['id']}"):
            _call("POST", f"/goals/{g['id']}/contribute", json={"amount": float(amount)})
        if b2.button("Retirar", key=f"g_sub_{g['id']}"):
            _call("POST", f"/goals/{g['id']}/contribute", json={"amount": -float(amount)})
        if right.button("Excluir", key=f"g_del_{g['id']}"):
            _call("DELETE", f"/goals/{g['id']}", "Meta excluída.")

    st.divider()
    with st.form("goal_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 2, 2])
        name = c1.text_input("Nome da meta")
        target = c2.number_input("Valor alvo (R$)", min_value=1.0, step=100.0, format="%.2f")
        saved = c3.number_input("Já guardado (R$)", min_value=0.0, step=50.0, format="%.2f")
        use_deadline = st.checkbox("Definir prazo")
        deadline = st.date_input("Prazo", value=today_local() + timedelta(days=180), format="DD/MM/YYYY")
        if st.form_submit_button("Criar meta", type="primary"):
            if not name.strip():
                st.error("Informe o nome da meta.")
            else:
                _call("POST", "/goals/", f"Meta “{name.strip()}” criada.", json={
                    "name": name, "target_amount": float(target), "saved_amount": float(saved),
                    "deadline": deadline.isoformat() if use_deadline else None})


def manage_recurring(data: dict):
    st.markdown("#### Transações recorrentes")
    st.caption("Cada regra gera sozinha a transação de cada ocorrência (ao abrir o painel). "
               "Uma data de início no passado gera também os lançamentos atrasados.")
    rules = api("GET", "/recurring/").json()
    accounts = fetch_accounts(st.session_state.token)
    if rules:
        table = pd.DataFrame(rules)
        table["type"] = table["type"].map({"expense": "Despesa", "income": "Receita"})
        table["frequency"] = table["frequency"].map(FREQUENCIES)
        table["active"] = table["active"].map({True: "Ativa", False: "Pausada/encerrada"})
        st.dataframe(
            table[["description", "type", "amount", "category", "frequency", "next_date", "end_date", "active"]].rename(
                columns={"description": "Descrição", "type": "Tipo", "amount": "Valor", "category": "Categoria",
                         "frequency": "Frequência", "next_date": "Próxima", "end_date": "Fim", "active": "Situação"}),
            hide_index=True, use_container_width=True,
            column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")},
        )
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        chosen = c1.selectbox("Regra", [r["id"] for r in rules], key="rule_pick",
                              format_func=lambda i: next(r["description"] for r in rules if r["id"] == i))
        active_now = next(r["active"] for r in rules if r["id"] == chosen)
        if c2.button("Pausar" if active_now else "Retomar"):
            _call("PUT", f"/recurring/{chosen}", json={"active": not active_now})
        if c3.button("Gerar agora"):
            res = api("POST", "/recurring/run").json()
            flash(f"{res['created']} transação(ões) gerada(s).")
            refresh()
        if c4.button("Excluir regra"):
            _call("DELETE", f"/recurring/{chosen}", "Regra excluída (as transações já geradas continuam).")
    else:
        info("Nenhuma regra ainda.")

    pending = [r for r in data.get("recurring", []) if not r.get("automated")]
    if pending:
        st.markdown("**Detectadas nos seus dados e ainda não automáticas**")
        for i, r in enumerate(pending):
            lt, rt = st.columns([4, 1])
            kind = "despesa" if r["type"] == "expense" else "receita"
            lt.write(f"{r['description']} · {money(r['avg_amount'])} · {kind} · próxima ~ {r['next_expected']}")
            if rt.button("Automatizar", key=f"auto_{i}"):
                _call("POST", "/recurring/", f"“{r['description']}” agora é gerada automaticamente.", json={
                    "description": r["description"], "amount": r["avg_amount"], "category": r["category"],
                    "type": r["type"], "frequency": "monthly", "start_date": r["next_expected"]})

    with st.form("rule_form", clear_on_submit=True):
        st.markdown("**Nova regra**")
        c1, c2, c3 = st.columns([3, 2, 2])
        desc = c1.text_input("Descrição")
        amount = c2.number_input("Valor (R$)", min_value=0.01, step=10.0, format="%.2f")
        tx_type = c3.selectbox("Tipo", ["expense", "income"],
                               format_func=lambda t: "Despesa" if t == "expense" else "Receita")
        d1, d2, d3 = st.columns([2, 2, 2])
        category = d1.text_input("Categoria", value="geral")
        frequency = d2.selectbox("Frequência", list(FREQUENCIES), index=1, format_func=FREQUENCIES.get)
        account_id = d3.selectbox("Conta", [None] + [a["id"] for a in accounts], format_func=account_label(accounts))
        e1, e2 = st.columns(2)
        start = e1.date_input("Primeira ocorrência", value=today_local(), format="DD/MM/YYYY")
        use_end = e2.checkbox("Tem data final")
        end = e2.date_input("Data final", value=today_local() + timedelta(days=365), format="DD/MM/YYYY")
        if st.form_submit_button("Criar regra", type="primary"):
            if not desc.strip():
                st.error("Informe a descrição.")
            else:
                _call("POST", "/recurring/", f"Regra “{desc.strip()}” criada.", json={
                    "description": desc, "amount": float(amount), "category": category or "geral", "type": tx_type,
                    "frequency": frequency, "start_date": start.isoformat(), "account_id": account_id,
                    "end_date": end.isoformat() if use_end else None})


def manage_alerts():
    st.markdown("#### Alertas de orçamento")
    st.caption("Avisamos uma única vez por categoria e por mês quando o gasto chega ao percentual escolhido "
               "(100% = limite atingido; acima disso = estourado).")
    cfg = api("GET", "/alerts/settings").json()
    with st.form("alerts_form"):
        email_on = st.checkbox("Avisar por e-mail", value=cfg["email_enabled"])
        webhook = st.text_input("Webhook (URL que receberá um POST em JSON)", value=cfg["webhook_url"] or "",
                                placeholder="https://hooks.exemplo.com/...")
        threshold = st.slider("Avisar quando chegar a (% do limite)", 50, 200, int(cfg["threshold_pct"]), step=5)
        if st.form_submit_button("Salvar alertas", type="primary"):
            _call("PUT", "/alerts/settings", "Alertas salvos.",
                  json={"email_enabled": email_on, "webhook_url": webhook or None, "threshold_pct": threshold})
    if st.button("Verificar orçamentos agora"):
        try:
            sent = api("POST", "/alerts/check").json()["sent"]
            if sent:
                st.success("Avisos enviados: " + ", ".join(f"{a['category']} ({a['pct_used']:.0f}%)" for a in sent))
            else:
                st.caption("Nada novo para avisar (ou os alertas já foram enviados neste mês).")
        except ApiError as exc:
            st.error(exc.detail)


def tab_manage(data: dict):
    sub = st.tabs(["🗂️ Categorias", "🏦 Contas", "🏁 Metas", "🔁 Recorrentes", "🔔 Alertas"])
    with sub[0]:
        manage_categories()
    with sub[1]:
        manage_accounts()
    with sub[2]:
        manage_goals()
    with sub[3]:
        manage_recurring(data)
    with sub[4]:
        manage_alerts()


# ------------------------------------------------------- Tab: Conta (LGPD)
def tab_account():
    me = fetch_me(st.session_state.token)
    st.subheader("Minha conta")
    st.write(f"**Usuário:** {me['username']}  ·  **E-mail:** {me['email']}")
    if me.get("email_verified"):
        st.success("E-mail verificado.")
    else:
        st.warning("E-mail ainda não verificado. Use o link que enviamos quando você criou a conta.")
        if st.button("Reenviar link de verificação"):
            try:
                st.info(api("POST", "/auth/resend-verification").json()["detail"])
            except ApiError as exc:
                st.error(exc.detail)

    st.divider()
    st.subheader("Meus dados (LGPD)")
    st.caption("Você pode baixar uma cópia de tudo que guardamos sobre você (conta, transações, orçamentos, contas, "
               "metas, recorrentes e alertas) ou excluir a conta e todos os dados.")
    if st.button("Gerar arquivo com meus dados"):
        try:
            st.session_state.my_data = api("GET", "/auth/me/export").content
        except ApiError as exc:
            st.error(exc.detail)
    if st.session_state.get("my_data"):
        st.download_button("⬇️ Baixar meus dados (JSON)", st.session_state.my_data,
                           file_name="meus_dados.json", mime="application/json")

    with st.expander("Excluir minha conta"):
        st.error("Isto apaga a conta e TODOS os seus dados, de forma definitiva. Baixe uma cópia antes, se quiser.")
        with st.form("delete_account_form"):
            password = st.text_input("Confirme com a sua senha", type="password")
            sure = st.checkbox("Entendo que não é possível desfazer")
            if st.form_submit_button("Excluir conta definitivamente"):
                if not sure or not password:
                    st.error("Informe a senha e marque a confirmação.")
                else:
                    try:
                        api("DELETE", "/auth/me", json={"password": password})
                    except ApiError as exc:
                        st.error(exc.detail)
                    else:
                        _logout()
                        st.rerun()


# ----------------------------------------------------------------- Main
def render_dashboard():
    days = render_sidebar()
    badge(f"ao vivo · últimos {days} dias · {datetime.now(APP_TZ).strftime('%H:%M:%S')}")
    st.title("Painel de Análise")
    show_flash()

    data = fetch_overview(st.session_state.token, days)

    t1, t2, t3, t4, t5, t6, t7 = st.tabs(
        ["📊 Visão geral", "📈 Análises", "🎯 Orçamentos", "🧾 Transações", "💡 Insights", "🧩 Gestão", "🔒 Conta"]
    )
    with t1:
        tab_overview(data, days)
    with t2:
        tab_analytics(data)
    with t3:
        tab_budgets(data)
    with t4:
        tab_transactions()
    with t5:
        tab_insights(data)
    with t6:
        tab_manage(data)
    with t7:
        tab_account()


restore_session()
sync_session_cookie()
if render_email_links():
    pass  # link de verificacao/redefinicao aberto: so a tela do link
elif st.session_state.token is None:
    render_auth()
else:
    try:
        render_dashboard()
    except ApiError as exc:
        if exc.status == 401:
            _logout()
            st.rerun()
        st.error(exc.detail)
