"""Dashboard interativo (Streamlit) consumindo a API."""
import os
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 20
GREEN, RED, BLUE = "#16A34A", "#DC2626", "#4F46E5"
PAGE_SIZE = 25

st.set_page_config(
    page_title="Dashboard Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("token", None)
st.session_state.setdefault("username", None)


# ------------------------------------------------------------------ API
class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _logout():
    st.session_state.token = None
    st.session_state.username = None
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


@st.cache_data(ttl=20, show_spinner=False)
def fetch_overview(token: str, days: int) -> dict:
    return _request("GET", "/analytics/overview?days=" + str(days), token).json()


@st.cache_data(ttl=20, show_spinner=False)
def fetch_categories(token: str) -> list:
    return _request("GET", "/transactions/categories", token).json()


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
    {"warning": st.warning, "success": st.success}.get(ins["level"], st.info)(ins["message"])


# ----------------------------------------------------------------- Auth
def render_auth():
    st.title("📈 Dashboard Analytics")
    st.caption("Faça login ou crie sua conta para acessar o painel.")
    tab_login, tab_register = st.tabs(["Entrar", "Criar conta"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                try:
                    resp = _request("POST", "/auth/login", data={"username": username, "password": password})
                    st.session_state.token = resp.json()["access_token"]
                    st.session_state.username = username
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
                        st.success("Cadastro realizado! Faça login na aba “Entrar”.")
                    except ApiError as exc:
                        st.error(exc.detail)


# -------------------------------------------------------------- Sidebar
def render_sidebar() -> int:
    st.sidebar.title("📈 Dashboard")
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
        cat_choice = st.selectbox("Categoria", categories + [new_cat_label])
        new_cat = st.text_input("Nova categoria (se escolheu “nova” acima)")
        tx_date = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
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

    c1, c2, c3, c4, c5 = st.columns(5)
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
            st.info("Sem dados no período.")
        else:
            fig = go.Figure()
            fig.add_bar(x=ts["day"], y=ts["income"], name="Receita", marker_color=GREEN, opacity=0.8)
            fig.add_bar(x=ts["day"], y=-ts["expense"], name="Despesa", marker_color=RED, opacity=0.8)
            fig.add_scatter(
                x=ts["day"], y=ts["cumulative_balance"], name="Saldo acumulado",
                mode="lines", line=dict(color=BLUE, width=3), yaxis="y2",
            )
            fig.update_layout(
                height=400, barmode="relative", margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", y=1.1),
                yaxis=dict(title="Fluxo diário (R$)"),
                yaxis2=dict(title="Saldo acumulado (R$)", overlaying="y", side="right", showgrid=False),
            )
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Despesas por categoria")
        cats = [c for c in data["by_category"] if c["type"] == "expense"]
        if not cats:
            st.info("Sem despesas no período.")
        else:
            dfc = pd.DataFrame(cats).sort_values("amount")
            fig = go.Figure(
                go.Bar(
                    x=dfc["amount"], y=dfc["category"], orientation="h", marker_color=BLUE,
                    text=[f"{p:.0f}%" for p in dfc["share_pct"]], textposition="outside",
                )
            )
            fig.update_layout(height=400, margin=dict(l=10, r=40, t=10, b=10), xaxis_title="R$")
            st.plotly_chart(fig, use_container_width=True)

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
        st.info("Nenhuma despesa no período.")


# ----------------------------------------------------------- Tab: Análises
def tab_analytics(data: dict):
    st.subheader("Comparativo mensal")
    monthly = pd.DataFrame(data["monthly"])
    if monthly.empty:
        st.info("Sem histórico suficiente.")
    else:
        fig = go.Figure()
        fig.add_bar(x=monthly["month"], y=monthly["income"], name="Receita", marker_color=GREEN)
        fig.add_bar(x=monthly["month"], y=monthly["expense"], name="Despesa", marker_color=RED)
        fig.add_scatter(
            x=monthly["month"], y=monthly["savings_rate"], name="Poupança (%)",
            mode="lines+markers", yaxis="y2", line=dict(color=BLUE, width=3),
        )
        fig.update_layout(
            height=380, barmode="group", margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=1.1),
            yaxis2=dict(title="Poupança (%)", overlaying="y", side="right", showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Gasto por dia da semana")
        wd = pd.DataFrame(data["weekday"])
        fig = go.Figure(go.Bar(x=wd["weekday"], y=wd["total"], marker_color=BLUE))
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="R$")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Previsão de despesas (30 dias)")
        fc = data["forecast"]
        if not fc.get("available"):
            st.info(fc.get("reason", "Previsão indisponível."))
        else:
            daily = pd.DataFrame(fc["daily"])
            fig = go.Figure()
            fig.add_scatter(x=daily["day"], y=daily["upper"], mode="lines", line=dict(width=0), showlegend=False)
            fig.add_scatter(
                x=daily["day"], y=daily["lower"], mode="lines", line=dict(width=0),
                fill="tonexty", fillcolor="rgba(79,70,229,0.15)", name="Faixa ~80%",
            )
            fig.add_scatter(x=daily["day"], y=daily["expense"], mode="lines", name="Projeção",
                            line=dict(color=BLUE, width=3))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="R$/dia",
                              legend=dict(orientation="h", y=1.15))
            st.plotly_chart(fig, use_container_width=True)

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
        rec = pd.DataFrame(data["recurring"])[
            ["description", "type", "avg_amount", "every_days", "last_date", "next_expected"]
        ]
        rec["type"] = rec["type"].map({"expense": "Despesa", "income": "Receita"})
        st.dataframe(
            rec.rename(columns={"description": "Descrição", "type": "Tipo", "avg_amount": "Valor médio",
                                "every_days": "A cada (dias)", "last_date": "Última", "next_expected": "Próxima"}),
            use_container_width=True, hide_index=True,
            column_config={"Valor médio": st.column_config.NumberColumn(format="R$ %.2f")},
        )
    else:
        st.caption("Nenhum padrão mensal detectado (precisa de 3+ ocorrências com ~30 dias de intervalo).")


# --------------------------------------------------------- Tab: Orçamentos
def tab_budgets(data: dict):
    st.subheader("Orçamento do mês")
    budgets = data["budgets"]
    if not budgets:
        st.info("Defina limites mensais por categoria para acompanhar o consumo.")
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
        "Período", value=(date.today() - timedelta(days=90), date.today()), format="DD/MM/YYYY", key="f_period"
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
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%d/%m/%Y")
        df["Excluir"] = False
        view = df[["Excluir", "id", "date", "description", "category", "type", "amount"]]
        edited = st.data_editor(
            view, hide_index=True, use_container_width=True, key=f"tx_editor_{page}_{total}",
            disabled=["id", "date", "description", "category", "type", "amount"],
            column_config={
                "Excluir": st.column_config.CheckboxColumn("🗑️"),
                "id": "ID", "date": "Data", "description": "Descrição", "category": "Categoria", "type": "Tipo",
                "amount": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            },
        )
        selected = edited.loc[edited["Excluir"], "id"].tolist()
        if st.button(f"Excluir selecionadas ({len(selected)})", disabled=not selected, type="primary"):
            failed = 0
            for tx_id in selected:
                try:
                    api("DELETE", f"/transactions/{int(tx_id)}")
                except ApiError:
                    failed += 1
            if failed:
                st.warning(f"{failed} exclusão(ões) falharam.")
            refresh()
    else:
        st.info("Nenhuma transação encontrada com esses filtros.")

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
        st.markdown("**Importar CSV**")
        st.caption("Colunas: descricao, valor, categoria, tipo (receita/despesa), data. Aceita `;` ou `,`.")
        up = st.file_uploader("Arquivo .csv", type=["csv"], label_visibility="collapsed")
        if up is not None and st.button("Importar arquivo"):
            try:
                result = api("POST", "/transactions/import",
                             files={"file": (up.name, up.getvalue(), "text/csv")}).json()
                st.success(f"{result['imported']} importada(s), {result['skipped']} ignorada(s).")
                for err in result["errors"][:5]:
                    st.caption(f"Linha {err['row']}: {err['error']}")
                st.cache_data.clear()
            except ApiError as exc:
                st.error(exc.detail)


# --------------------------------------------------------- Tab: Insights
def tab_insights(data: dict):
    st.subheader("Insights automáticos")
    if not data["insights"]:
        st.info("Cadastre mais transações para gerar insights.")
    for ins in data["insights"]:
        show_insight(ins)


# ----------------------------------------------------------------- Main
def render_dashboard():
    days = render_sidebar()
    st.title("Painel de Análise")
    st.caption(f"Últimos {days} dias · atualizado às {datetime.now().strftime('%H:%M:%S')}")

    data = fetch_overview(st.session_state.token, days)

    t1, t2, t3, t4, t5 = st.tabs(["📊 Visão geral", "📈 Análises", "🎯 Orçamentos", "🧾 Transações", "💡 Insights"])
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


if st.session_state.token is None:
    render_auth()
else:
    try:
        render_dashboard()
    except ApiError as exc:
        if exc.status == 401:
            _logout()
            st.rerun()
        st.error(exc.detail)
