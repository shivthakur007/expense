import streamlit as st
import pandas as pd
from datetime import date
import requests
from google_auth_oauthlib.flow import Flow
import plotly.express as px
from firebase_config import get_db

db = get_db()

st.set_page_config(page_title="Money Manager", layout="wide")

# ---------------- AUTH CONFIG ----------------
FIREBASE_API_KEY = st.secrets["auth"]["api_key"]
GOOGLE_CLIENT_ID = st.secrets["auth"]["google_client_id"]
GOOGLE_CLIENT_SECRET = st.secrets["auth"]["google_client_secret"]
REDIRECT_URI = st.secrets["auth"]["redirect_uri"]

def firebase_email_signup(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(url, json=payload).json()

def firebase_email_login(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(url, json=payload).json()

def firebase_google_login(id_token):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}"
    payload = {
        "postBody": f"id_token={id_token}&providerId=google.com",
        "requestUri": REDIRECT_URI,
        "returnSecureToken": True,
        "returnIdpCredential": True,
    }
    return requests.post(url, json=payload).json()

def start_google_oauth():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=["openid", "email", "profile"],
        redirect_uri=REDIRECT_URI,
    )

    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
    )

    return auth_url

def exchange_google_code(code):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=["openid", "email", "profile"],
        redirect_uri=REDIRECT_URI,
    )
    flow.fetch_token(code=code, client_secret=GOOGLE_CLIENT_SECRET)
    return flow.credentials.id_token
    
# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN UI ----------------
if st.session_state.user is None:
    st.title("Expense Tracker 💸")
    st.markdown("Please sign in to continue")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            resp = firebase_email_login(email, password)
            if "localId" in resp:
                st.session_state.user = {"uid": resp["localId"], "email": resp["email"]}
                st.rerun()
            else:
                st.error(resp.get("error", {}).get("message", "Login failed"))

        st.divider()
        st.markdown("Or sign in with Google")
        google_url = start_google_oauth()
        st.link_button("Continue with Google", google_url)

    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_pass")
        if st.button("Create Account"):
            resp = firebase_email_signup(email, password)
            if "localId" in resp:
                st.success("Account created. Please log in.")
            else:
                st.error(resp.get("error", {}).get("message", "Signup failed"))

    # Handle Google redirect
    query = st.query_params
    if "code" in query:
        id_token = exchange_google_code(query["code"])
        resp = firebase_google_login(id_token)
        if "localId" in resp:
            st.session_state.user = {"uid": resp["localId"], "email": resp["email"]}
            st.rerun()

    st.stop()

# ---------------- LOGOUT ----------------
st.sidebar.success(f"Logged in as {st.session_state.user['email']}")
if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# ---------------- UI THEME ----------------
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

uid = st.session_state.user["uid"]
expenses_ref = db.collection("users").document(uid).collection("expenses")

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
            expenses_ref.add({
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
docs = expenses_ref.stream()
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

    # ---------- SIDEBAR: DELETE + UPDATE ----------
    with st.sidebar:
        st.header("Delete Expense")

        action_df = filtered_df.copy()
        action_df["label"] = action_df.apply(
            lambda r: f"{r['date']} — {r['expense']} — ₹{r['amount']:.2f} [{r['category']}, {r['payment_mode']}]",
            axis=1
        )

        del_label = st.selectbox("Select expense to delete", action_df["label"], key="del_label")
        del_id = action_df.loc[action_df["label"] == del_label, "id"].values[0]

        if st.button("Delete Expense"):
            expenses_ref.document(del_id).delete()
            st.success("Expense deleted")
            st.rerun()

        st.header("Update Expense")

        edit_label = st.selectbox("Select expense to edit", action_df["label"], key="edit_label")
        selected_row = action_df[action_df["label"] == edit_label].iloc[0]

        new_expense = st.text_input("Update expense name", value=selected_row["expense"], key="edit_expense")
        new_amount = st.number_input(
            "Update amount",
            min_value=0.0,
            value=float(selected_row["amount"]),
            step=50.0,
            format="%.2f",
            key="edit_amount"
        )

        try:
            selected_date = pd.to_datetime(selected_row["date"]).date()
        except Exception:
            selected_date = date.today()
        new_date = st.date_input("Update date", value=selected_date, key="edit_date")

        category_options = sorted(set(CATEGORIES + action_df["category"].tolist() + ["Other"]))
        current_cat = selected_row["category"] if selected_row["category"] in category_options else "Other"
        new_category_select = st.selectbox(
            "Update category",
            category_options,
            index=category_options.index(current_cat),
            key="edit_category_select"
        )
        if new_category_select == "Other":
            new_category_custom = st.text_input(
                "Custom category",
                value=selected_row["category"] if current_cat == "Other" else "",
                key="edit_category_custom"
            )
            new_category = new_category_custom.strip() if new_category_custom.strip() else "Other"
        else:
            new_category = new_category_select

        payment_options = sorted(set(PAYMENT_MODES + action_df["payment_mode"].tolist() + ["Other"]))
        current_pay = selected_row["payment_mode"] if selected_row["payment_mode"] in payment_options else "Other"
        new_payment_select = st.selectbox(
            "Update payment mode",
            payment_options,
            index=payment_options.index(current_pay),
            key="edit_payment_select"
        )
        if new_payment_select == "Other":
            new_payment_custom = st.text_input(
                "Custom payment mode",
                value=selected_row["payment_mode"] if current_pay == "Other" else "",
                key="edit_payment_custom"
            )
            new_payment_mode = new_payment_custom.strip() if new_payment_custom.strip() else "Other"
        else:
            new_payment_mode = new_payment_select

        if st.button("Update Expense"):
            expenses_ref.document(selected_row["id"]).update({
                "expense": new_expense.strip(),
                "amount": float(new_amount),
                "category": new_category,
                "payment_mode": new_payment_mode,
                "date": new_date.isoformat()
            })
            st.success("Expense updated")
            st.rerun()

else:
    st.warning("No expenses added yet")

