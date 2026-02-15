import streamlit as st
import pandas as pd
from datetime import date
from firebase_config import get_db
import plotly.express as px

db = get_db()

st.set_page_config(page_title="Expense Tracker", layout="wide")

# ---------- THEME TOGGLE ----------
dark_mode = st.sidebar.toggle("Dark mode", value=False)

if dark_mode:
    theme_css = """
    <style>
    .main { background: #0b1220; color: #e5e7eb; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    h1, h2, h3 { color: #e5e7eb; }
    .kpi-card { background: #111827; color: #e5e7eb; box-shadow: 0 6px 18px rgba(0,0,0,0.3); }
    .kpi-title { color: #9ca3af; }
    .stButton>button { background: #2563eb; color: white; }
    .stButton>button:hover { background: #1d4ed8; }
    </style>
    """
else:
    theme_css = """
    <style>
    .main { background: #f4f6fb; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    h1 { font-size: 2.3rem; letter-spacing: -0.5px; }
    .kpi-card { background: white; padding: 1rem 1.2rem; border-radius: 14px; box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08); }
    .kpi-title { font-size: 0.9rem; color: #475569; }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: #0f172a; }
    .stButton>button { background: #0f172a; color: white; border-radius: 10px; border: none; padding: 0.6rem 1.2rem; }
    .stButton>button:hover { background: #1f2937; }
    </style>
    """

st.markdown(theme_css, unsafe_allow_html=True)

st.title("Expense Tracker 💸")
st.markdown("Money saved is equal to money earned")

CATEGORIES = ["Food", "Transport", "Bills", "Shopping", "Entertainment", "Health", "Education", "Other"]
PAYMENT_MODES = ["Cash", "Card", "UPI", "Bank Transfer", "Wallet", "Other"]

# ---------- SIDEBAR: ADD EXPENSE ----------
with st.sidebar:
    st.header("Add Expense")
    expense = st.text_input("Enter expense")
    amount = st.number_input("Enter amount", min_value=0.0, step=50.0, format="%.2f")
    expense_date = st.date_input("Expense date", value=date.today())

    category = st.selectbox("Category", CATEGORIES + ["Other"])
    if category == "Other":
        category_other = st.text_input("Custom category")
        if category_other:
            category = category_other.strip()

    payment_mode = st.selectbox("Payment mode", PAYMENT_MODES + ["Other"])
    if payment_mode == "Other":
        payment_other = st.text_input("Custom payment mode")
        if payment_other:
            payment_mode = payment_other.strip()

    if st.button("Add Expense"):
        if expense:
            db.collection("expenses").add({
                "expense": expense.strip(),
                "amount": float(amount),
                "category": category,
                "payment_mode": payment_mode,
                "date": expense_date.isoformat()
            })
            st.success("Expense added")
            st.rerun()
        else:
            st.warning("Please enter an expense")

# ---------- READ EXPENSES ----------
docs = db.collection("expenses").stream()
data = []
for doc in docs:
    row = doc.to_dict()
    row["id"] = doc.id
    data.append(row)

df = pd.DataFrame(data)

if not df.empty:
    for col in ["expense", "amount", "category", "payment_mode", "date"]:
        if col not in df.columns:
            df[col] = ""

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["category"] = df["category"].fillna("").replace("", "Uncategorized")
    df["payment_mode"] = df["payment_mode"].fillna("").replace("", "Unknown")
    df["date"] = df["date"].fillna("").replace("", "Unknown")

    df["sort_date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(by="sort_date", ascending=False, na_position="last")

    # ---------- FILTERS ----------
    st.subheader("Filters")
    show_all = st.checkbox("Show all expenses", value=True)

    if show_all:
        filtered_df = df.copy()
    else:
        min_date = df["sort_date"].min()
        max_date = df["sort_date"].max()

        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.date_input(
                "Select date range",
                value=(min_date.date(), max_date.date())
            )
        else:
            date_range = (date.today(), date.today())

        category_options = sorted(df["category"].unique())
        payment_options = sorted(df["payment_mode"].unique())

        category_filter = st.multiselect("Filter by category", category_options, default=category_options)
        payment_filter = st.multiselect("Filter by payment mode", payment_options, default=payment_options)

        filtered_df = df[
            df["category"].isin(category_filter) &
            df["payment_mode"].isin(payment_filter)
        ]

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df["sort_date"] >= pd.to_datetime(start_date)) &
                (filtered_df["sort_date"] <= pd.to_datetime(end_date))
            ]

    # ---------- KPI CARDS ----------
    total = filtered_df["amount"].sum()
    month_total = filtered_df[
        filtered_df["sort_date"].dt.month == date.today().month
    ]["amount"].sum()
    avg_entry = total / max(len(filtered_df), 1)

    col1, col2, col3 = st.columns(3)
    col1.markdown(f"<div class='kpi-card'><div class='kpi-title'>Total Expense</div><div class='kpi-value'>₹{total:,.2f}</div></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='kpi-card'><div class='kpi-title'>This Month</div><div class='kpi-value'>₹{month_total:,.2f}</div></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='kpi-card'><div class='kpi-title'>Avg/Entry</div><div class='kpi-value'>₹{avg_entry:,.2f}</div></div>", unsafe_allow_html=True)

    # ---------- TABLE + DOWNLOAD ----------
    st.subheader("Expenses")
    st.dataframe(
        filtered_df[["date", "expense", "amount", "category", "payment_mode"]],
        use_container_width=True
    )

    csv_data = filtered_df[["date", "expense", "amount", "category", "payment_mode"]].to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv_data, file_name="expenses.csv", mime="text/csv")

    # ---------- CHARTS (PLOTLY) ----------
    st.subheader("Spending Trend")
    trend = filtered_df.dropna(subset=["sort_date"]).copy()
    trend = trend.groupby(trend["sort_date"].dt.date)["amount"].sum().reset_index()
    fig_trend = px.line(trend, x="sort_date", y="amount", markers=True)
    fig_trend.update_layout(xaxis_title="Date", yaxis_title="Amount")
    st.plotly_chart(fig_trend, use_container_width=True)

    col4, col5 = st.columns(2)

    with col4:
        st.subheader("Category Split")
        cat_chart = filtered_df.groupby("category")["amount"].sum().reset_index()
        fig_pie = px.pie(cat_chart, names="category", values="amount", hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col5:
        st.subheader("Monthly Spending")
        monthly = filtered_df.dropna(subset=["sort_date"]).copy()
        monthly["month"] = monthly["sort_date"].dt.to_period("M").astype(str)
        monthly_sum = monthly.groupby("month")["amount"].sum().reset_index()
        fig_bar = px.bar(monthly_sum, x="month", y="amount")
        fig_bar.update_layout(xaxis_title="Month", yaxis_title="Amount")
        st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.warning("No expenses added yet")
