"""
公開總覽:所有人的記帳跟日誌,任何登入者都能看
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from utils import (
    get_supabase,
    require_login,
    render_sidebar,
    get_all_users,
    user_id_to_name_map,
)


st.set_page_config(page_title="公開總覽", page_icon="🌐", layout="wide")

require_login()
render_sidebar()

st.title("🌐 公開總覽")
st.caption("這裡可以看到所有使用者的記錄")

users = get_all_users()
name_map = user_id_to_name_map()
# 名字 → user_id 的反查表(用名字當下拉選單值)
name_to_id = {(u["display_name"] or u["id"][:8]): u["id"] for u in users}
display_names = list(name_to_id.keys())


tab_tx, tab_journal, tab_stats = st.tabs(["💰 所有記帳", "📔 所有日誌", "📊 使用者統計"])


# ===================== 所有記帳 =====================
with tab_tx:
    c1, c2, c3 = st.columns(3)
    with c1:
        start_date = st.date_input(
            "起始日期", value=date.today() - timedelta(days=30), key="pub_tx_start"
        )
    with c2:
        end_date = st.date_input("結束日期", value=date.today(), key="pub_tx_end")
    with c3:
        user_filter = st.selectbox("使用者", ["全部"] + display_names, key="pub_tx_user")

    try:
        query = (
            get_supabase()
            .table("transactions")
            .select("*")
            .gte("transaction_date", start_date.isoformat())
            .lte("transaction_date", end_date.isoformat())
            .order("transaction_date", desc=True)
        )
        if user_filter != "全部":
            query = query.eq("user_id", name_to_id[user_filter])
        txs = query.execute().data or []
    except Exception as e:
        st.error(f"讀取失敗:{e}")
        txs = []

    if txs:
        df = pd.DataFrame(txs)
        df["使用者"] = df["user_id"].map(lambda x: name_map.get(x, x[:8]))
        df["類型"] = df["type"].map({"income": "💰 收入", "expense": "💸 支出"})
        df["金額顯示"] = df.apply(
            lambda r: f"+${r['amount']:,.0f}"
            if r["type"] == "income"
            else f"-${r['amount']:,.0f}",
            axis=1,
        )
        df_show = df[
            ["transaction_date", "使用者", "類型", "category", "金額顯示", "description"]
        ].rename(
            columns={
                "transaction_date": "日期",
                "category": "分類",
                "金額顯示": "金額",
                "description": "備註",
            }
        )
        st.dataframe(df_show, use_container_width=True, hide_index=True)

        # 摘要
        income = df.loc[df["type"] == "income", "amount"].sum()
        expense = df.loc[df["type"] == "expense", "amount"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("總收入", f"${income:,.0f}")
        c2.metric("總支出", f"${expense:,.0f}")
        c3.metric("淨額", f"${income - expense:,.0f}")
    else:
        st.info("這個範圍沒有記錄")


# ===================== 所有日誌 =====================
with tab_journal:
    user_filter_j = st.selectbox(
        "使用者", ["全部"] + display_names, key="pub_j_user"
    )

    try:
        query = (
            get_supabase()
            .table("journal_entries")
            .select("*")
            .order("entry_date", desc=True)
            .order("id", desc=True)
            .limit(200)
        )
        if user_filter_j != "全部":
            query = query.eq("user_id", name_to_id[user_filter_j])
        entries = query.execute().data or []
    except Exception as e:
        st.error(f"讀取失敗:{e}")
        entries = []

    if entries:
        for entry in entries:
            who = name_map.get(entry["user_id"], entry["user_id"][:8])
            title = entry.get("title") or "(無標題)"
            with st.expander(f"📅 **{entry['entry_date']}** — 👤 {who} — {title}"):
                st.markdown(entry["content"])
    else:
        st.info("沒有日誌")


# ===================== 使用者統計 =====================
with tab_stats:
    st.subheader("各使用者收支總額")

    c1, c2 = st.columns(2)
    with c1:
        stats_start = st.date_input(
            "起始日期",
            value=date.today() - timedelta(days=30),
            key="stats_start",
        )
    with c2:
        stats_end = st.date_input("結束日期", value=date.today(), key="stats_end")

    try:
        result = (
            get_supabase()
            .table("transactions")
            .select("*")
            .gte("transaction_date", stats_start.isoformat())
            .lte("transaction_date", stats_end.isoformat())
            .execute()
        )
        all_tx = result.data or []
    except Exception as e:
        st.error(f"讀取失敗:{e}")
        all_tx = []

    if all_tx:
        df = pd.DataFrame(all_tx)
        df["使用者"] = df["user_id"].map(lambda x: name_map.get(x, x[:8]))

        summary = (
            df.groupby(["使用者", "type"])["amount"].sum().unstack(fill_value=0)
        )
        if "income" not in summary.columns:
            summary["income"] = 0
        if "expense" not in summary.columns:
            summary["expense"] = 0
        summary["結餘"] = summary["income"] - summary["expense"]
        summary = summary.rename(columns={"income": "收入", "expense": "支出"})[
            ["收入", "支出", "結餘"]
        ]

        st.dataframe(
            summary.style.format("${:,.0f}"),
            use_container_width=True,
        )

        # 分類細項
        st.subheader("各使用者支出分類")
        expense_df = df[df["type"] == "expense"]
        if not expense_df.empty:
            cat_summary = (
                expense_df.groupby(["使用者", "category"])["amount"]
                .sum()
                .unstack(fill_value=0)
            )
            st.dataframe(
                cat_summary.style.format("${:,.0f}"),
                use_container_width=True,
            )
    else:
        st.info("這個範圍沒有記錄")
