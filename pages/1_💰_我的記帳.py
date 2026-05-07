"""
我的記帳:新增 / 列表 / 刪除 自己的收支記錄
"""
import streamlit as st
import pandas as pd
from datetime import date
from utils import get_supabase, get_current_user, require_login, render_sidebar


st.set_page_config(page_title="我的記帳", page_icon="💰", layout="wide")

require_login()
render_sidebar()
user = get_current_user()

st.title("💰 我的記帳")

# 分類選單(可自行修改)
CATEGORIES_EXPENSE = ["飲食", "交通", "娛樂", "購物", "房租水電", "醫療", "教育", "其他支出"]
CATEGORIES_INCOME = ["薪水", "獎金", "投資", "禮金", "其他收入"]


# ---------- 新增記帳 ----------
with st.expander("➕ 新增一筆記帳", expanded=True):
    with st.form("add_transaction", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            tx_type = st.selectbox(
                "類型",
                ["expense", "income"],
                format_func=lambda x: "💸 支出" if x == "expense" else "💰 收入",
            )
        with col2:
            amount = st.number_input("金額", min_value=0.0, step=10.0, value=0.0)
        with col3:
            tx_date = st.date_input("日期", value=date.today())

        col4, col5 = st.columns([1, 2])
        with col4:
            cats = CATEGORIES_EXPENSE if tx_type == "expense" else CATEGORIES_INCOME
            category = st.selectbox("分類", cats)
        with col5:
            description = st.text_input("備註(可選)")

        submit = st.form_submit_button("新增", type="primary", use_container_width=True)

        if submit:
            if amount <= 0:
                st.error("金額必須大於 0")
            else:
                try:
                    get_supabase().table("transactions").insert(
                        {
                            "user_id": user["id"],
                            "amount": float(amount),
                            "type": tx_type,
                            "category": category,
                            "description": description or None,
                            "transaction_date": tx_date.isoformat(),
                        }
                    ).execute()
                    st.success("已新增 ✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"新增失敗:{e}")


st.divider()


# ---------- 篩選 + 列表 ----------
st.subheader("我的記錄")

today = date.today()
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "起始日期", value=date(today.year, today.month, 1), key="my_start"
    )
with col2:
    end_date = st.date_input("結束日期", value=today, key="my_end")

try:
    result = (
        get_supabase()
        .table("transactions")
        .select("*")
        .eq("user_id", user["id"])
        .gte("transaction_date", start_date.isoformat())
        .lte("transaction_date", end_date.isoformat())
        .order("transaction_date", desc=True)
        .execute()
    )
    transactions = result.data or []
except Exception as e:
    st.error(f"讀取失敗:{e}")
    transactions = []

if transactions:
    df = pd.DataFrame(transactions)
    income = df.loc[df["type"] == "income", "amount"].sum()
    expense = df.loc[df["type"] == "expense", "amount"].sum()
    balance = income - expense

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 收入", f"${income:,.0f}")
    c2.metric("💸 支出", f"${expense:,.0f}")
    c3.metric("結餘", f"${balance:,.0f}", delta=f"{balance:,.0f}")

    st.markdown("---")

    # 表頭
    h = st.columns([1.5, 1.2, 1.5, 3, 0.7])
    h[0].markdown("**日期**")
    h[1].markdown("**類型/分類**")
    h[2].markdown("**金額**")
    h[3].markdown("**備註**")
    h[4].markdown("**動作**")

    # 每一筆顯示為一個 row
    for tx in transactions:
        cols = st.columns([1.5, 1.2, 1.5, 3, 0.7])
        cols[0].text(tx["transaction_date"])

        type_emoji = "💸" if tx["type"] == "expense" else "💰"
        cols[1].text(f"{type_emoji} {tx.get('category') or '-'}")

        sign = "-" if tx["type"] == "expense" else "+"
        color = "🔴" if tx["type"] == "expense" else "🟢"
        cols[2].markdown(f"{color} `{sign}${tx['amount']:,.0f}`")

        cols[3].text(tx.get("description") or "—")

        if cols[4].button("🗑️", key=f"del_tx_{tx['id']}", help="刪除這筆"):
            try:
                get_supabase().table("transactions").delete().eq("id", tx["id"]).execute()
                st.toast("已刪除", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"刪除失敗:{e}")
else:
    st.info("這段期間還沒有記錄,新增一筆試試!")
