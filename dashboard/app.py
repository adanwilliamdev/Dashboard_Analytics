"""Dashboard interativo (Streamlit) consumindo a API."""
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Dashboard Analytics",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None


def api_headers():
    return {"Authorization": "Bearer " + str(st.session_state.token)}


def api_post(path, **kwargs):
    return requests.post(API_URL + path, timeout=15, **kwargs)


def api_get(path, **kwargs):
    return requests.get(API_URL + path, timeout=15, **kwargs)


def render_auth():
    st.title("Dashboard Analytics")
    st.caption("Login ou cadastro para acessar o painel")

    tab1, tab2 = st.tabs(["Login", "Cadastro"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            if submit:
                try:
                    r = api_post(
                        "/auth/login",
                        data={"username": username, "password": password},
                    )
                    if r.status_code == 200:
                        st.session_state.token = r.json()["access_token"]
                        st.session_state.username = username
                        st.success("Login realizado!")
                        st.rerun()
                    else:
                        st.error("Erro: " + str(r.json().get("detail", "Falha no login")))
                except Exception as e:
                    st.error("Erro de conexao: " + str(e))

    with tab2:
        with st.form("register_form"):
            new_user = st.text_input("Usuario (novo)")
            new_email = st.text_input("E-mail")
            new_pass = st.text_input("Senha", type="password")
            new_pass2 = st.text_input("Confirme a senha", type="password")
            submit = st.form_submit_button("Cadastrar", use_container_width=True)
            if submit:
                if new_pass != new_pass2:
                    st.error("As senhas nao coincidem")
                elif len(new_pass) < 6:
                    st.error("Senha deve ter ao menos 6 caracteres")
                else:
                    try:
                        r = api_post(
                            "/auth/register",
                            json={
                                "username": new_user,
                                "email": new_email,
                                "password": new_pass,
                            },
                        )
                        if r.status_code == 201:
                            st.success("Cadastro realizado! Faca login.")
                        else:
                            st.error("Erro: " + str(r.json().get("detail", "Falha no cadastro")))
                    except Exception as e:
                        st.error("Erro de conexao: " + str(e))


def render_dashboard():
    st.sidebar.title("Dashboard")
    st.sidebar.write("Usuario: **" + str(st.session_state.username) + "**")
    if st.sidebar.button("Sair"):
        st.session_state.token = None
        st.session_state.username = None
        st.rerun()

    st.sidebar.markdown("---")
    days = st.sidebar.slider("Periodo (dias)", 7, 365, 30)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Nova transacao")
    with st.sidebar.form("new_tx"):
        desc = st.text_input("Descricao")
        amount = st.number_input("Valor", min_value=0.01, step=0.01, format="%.2f")
        category = st.text_input("Categoria", value="geral")
        tx_type = st.selectbox("Tipo", ["expense", "income"])
        date = st.date_input("Data", value=datetime.utcnow().date())
        submit = st.form_submit_button("Adicionar", use_container_width=True)
        if submit and desc and amount > 0:
            payload = {
                "description": desc,
                "amount": float(amount),
                "category": category,
                "type": tx_type,
                "date": datetime.combine(date, datetime.min.time()).isoformat(),
            }
            r = api_post("/transactions/", json=payload, headers=api_headers())
            if r.status_code == 201:
                st.sidebar.success("Transacao adicionada!")
                st.rerun()
            else:
                st.sidebar.error("Erro: " + r.text)

    st.title("Painel de Analise")
    st.caption("Ultimos " + str(days) + " dias")

    summary = api_get("/analytics/summary?days=" + str(days), headers=api_headers()).json()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Receitas", "R$ {:,.2f}".format(summary.get("total_income", 0)))
    c2.metric("Despesas", "R$ {:,.2f}".format(summary.get("total_expense", 0)))
    c3.metric("Saldo", "R$ {:,.2f}".format(summary.get("balance", 0)))
    c4.metric("Transacoes", summary.get("transaction_count", 0))

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Evolucao diaria")
        ts = api_get("/analytics/timeseries?days=" + str(days), headers=api_headers()).json()
        if ts:
            df_ts = pd.DataFrame(ts)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_ts["day"], y=df_ts["income"], name="Receita", mode="lines+markers"))
            fig.add_trace(go.Scatter(x=df_ts["day"], y=df_ts["expense"], name="Despesa", mode="lines+markers"))
            fig.add_trace(go.Bar(x=df_ts["day"], y=df_ts["balance"], name="Saldo", opacity=0.4))
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados no periodo.")

    with col_right:
        st.subheader("Por categoria")
        cats = api_get("/analytics/by-category?days=" + str(days), headers=api_headers()).json()
        if cats:
            df_cat = pd.DataFrame(cats)
            fig = px.pie(df_cat, values="amount", names="category", color="type", hole=0.4)
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados no periodo.")

    st.subheader("Top 5 despesas")
    top = api_get("/analytics/top-expenses?limit=5", headers=api_headers()).json()
    if top:
        st.dataframe(pd.DataFrame(top), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma despesa registrada.")

    st.subheader("Transacoes recentes")
    txs = api_get("/transactions/?limit=20", headers=api_headers()).json()
    if txs:
        df_tx = pd.DataFrame(txs)
        df_tx["date"] = pd.to_datetime(df_tx["date"]).dt.strftime("%d/%m/%Y")
        st.dataframe(
            df_tx[["id", "date", "description", "category", "type", "amount"]],
            use_container_width=True,
            hide_index=True,
        )

        tx_id = st.number_input("ID para excluir", min_value=0, step=1, value=0)
        if st.button("Excluir transacao") and tx_id > 0:
            r = requests.delete(API_URL + "/transactions/" + str(tx_id), headers=api_headers(), timeout=15)
            if r.status_code == 204:
                st.success("Transacao " + str(tx_id) + " excluida!")
                st.rerun()
            else:
                st.error("Falha ao excluir. Verifique o ID.")
    else:
        st.info("Nenhuma transacao cadastrada ainda.")


if st.session_state.token is None:
    render_auth()
else:
    try:
        render_dashboard()
    except Exception as e:
        st.error("Erro ao carregar dashboard: " + str(e))
        st.session_state.token = None
