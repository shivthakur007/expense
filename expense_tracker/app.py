import streamlit as st
import pandas as pd
from datetime import date
from firebase_config import get_db

db = get_db()

st.title("Expense Tracker 💸")
st.markdown("Money saved is equal to money earned")

CATEGORIES = ["Food", "Transport", "Bills", "Shopping", "Entertainment", "Health", "Education", "Other"]
PAYMENT_MODES = ["Cash", "Card", "UPI", "Bank Transfer", "Wallet", "Other"]

# ---------------- ADD EXPENSE ----------------
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

# ---------------- READ EXPENSES ----------------
docs = db.collection("expenses").stream()

data = []
for doc in docs:
    row = doc.to_dict()
    row["id"] = doc.id
    data.append(row)

df = pd.DataFrame(data)

st.subheader("Your Expenses")

if not df.empty:
    # Ensure columns exist for older records
    for col in ["expense", "amount", "category", "payment_mode", "date"]:
        if col not in df.columns:
            df[col] = ""

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["category"] = df["category"].fillna("").replace("", "Uncategorized")
    df["payment_mode"] = df["payment_mode"].fillna("").replace("", "Unknown")
    df["date"] = df["date"].fillna("").replace("", "Unknown")

    df["sort_date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(by="sort_date", ascending=False, na_position="last")

    # ---------------- FILTERS ----------------
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

        category_filter = st.multiselect(
            "Filter by category",
            options=category_options,
            default=category_options
        )

        payment_filter = st.multiselect(
            "Filter by payment mode",
            options=payment_options,
            default=payment_options
        )

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

    # ---------------- SHOW TABLE ----------------
    if filtered_df.empty:
        st.warning("No expenses match the current filters.")
    else:
        st.dataframe(
            filtered_df[["date", "expense", "amount", "category", "payment_mode"]],
            use_container_width=True
        )
        st.info(f"Total Expense (shown): ₹{filtered_df['amount'].sum():,.2f}")

    # ---------------- DELETE ----------------
    action_df = filtered_df.copy()
    action_df["label"] = action_df.apply(
        lambda r: f"{r['date']} — {r['expense']} — ₹{r['amount']:.2f} [{r['category']}, {r['payment_mode']}]",
        axis=1
    )

    st.subheader("Delete Expense")
    del_label = st.selectbox("Select expense to delete", action_df["label"], key="del_label")
    del_id = action_df.loc[action_df["label"] == del_label, "id"].values[0]

    if st.button("Delete Expense"):
        db.collection("expenses").document(del_id).delete()
        st.success("Expense deleted")
        st.rerun()

    # ---------------- UPDATE ----------------
    st.subheader("Update Expense")
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
        db.collection("expenses").document(selected_row["id"]).update({
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
