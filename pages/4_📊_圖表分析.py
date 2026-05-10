"""
圖表分析:時間序列 / 月度比較 / 分類分布 / 使用者比較
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from utils import (
    get_supabase,
    get_current_user,
    require_login,
    render_sidebar,
    get_all_users,
    user_id_to_name_map,
)


st.set_page_config(page_title="圖表分析", page_icon="📊", layout="wide")

require_login()
render_sidebar()
me = get_current_user()

st.title("📊 圖表分析")

users = get_all_users()
name_map = user_id_to_name_map()
name_to_id = {(u["display_name"] or u["id"][:8]): u["id"] for u in users}
display_names = list(name_to_id.keys())

# 顏色設定
COLOR_INCOME = "#10b981"
COLOR_EXPENSE = "#ef4444"
COLOR_MAP = {"收入": COLOR_INCOME, "支出": COLOR_EXPENSE}


# ---------- 篩選列 ----------
c1, c2, c3 = st.columns(3)
with c1:
    options = ["我自己", "所有人"] + display_names
    user_filter = st.selectbox("使用者", options, index=0)
with c2:
    start_date = st.date_input(
        "起始日期", value=date.today() - timedelta(days=90)
    )
with c3:
    end_date = st.date_input("結束日期", value=date.today())


# ---------- 取資料 ----------
try:
    query = (
        get_supabase()
        .table("transactions")
        .select("*")
        .gte("transaction_date", start_date.isoformat())
        .lte("transaction_date", end_date.isoformat())
    )
    if user_filter == "我自己":
        query = query.eq("user_id", me["id"])
    elif user_filter != "所有人":
        query = query.eq("user_id", name_to_id[user_filter])
    txs = query.execute().data or []
except Exception as e:
    st.error(f"讀取失敗:{e}")
    txs = []


if not txs:
    st.info("這個範圍沒有資料,先去「我的記帳」新增幾筆吧!")
    st.stop()

# ---------- 整理 dataframe ----------
df = pd.DataFrame(txs)
df["transaction_date"] = pd.to_datetime(df["transaction_date"])
df["使用者"] = df["user_id"].map(lambda x: name_map.get(x, x[:8]))
df["類型"] = df["type"].map({"income": "收入", "expense": "支出"})


# ---------- 摘要卡 ----------
income = df.loc[df["type"] == "income", "amount"].sum()
expense = df.loc[df["type"] == "expense", "amount"].sum()
balance = income - expense

c1, c2, c3 = st.columns(3)
c1.metric("總收入", f"${income:,.0f}")
c2.metric("總支出", f"${expense:,.0f}")
c3.metric("結餘", f"${balance:,.0f}", delta=f"{balance:,.0f}")

st.divider()


# ---------- 圖 1:每日收支折線圖(時間序列) ----------
st.subheader("📈 每日收支趨勢")
daily = (
    df.groupby([df["transaction_date"].dt.date, "類型"])["amount"]
    .sum()
    .reset_index()
    .rename(columns={"transaction_date": "日期", "amount": "金額"})
)
fig1 = px.line(
    daily,
    x="日期",
    y="金額",
    color="類型",
    markers=True,
    color_discrete_map=COLOR_MAP,
)
fig1.update_layout(height=400, hovermode="x unified")
st.plotly_chart(fig1, use_container_width=True, key="analysis_daily_trend")


# ---------- 圖 2:月度收支長條圖 ----------
st.subheader("📊 月度收支")
monthly = df.copy()
monthly["月份"] = monthly["transaction_date"].dt.to_period("M").astype(str)
monthly_sum = (
    monthly.groupby(["月份", "類型"])["amount"]
    .sum()
    .reset_index()
    .rename(columns={"amount": "金額"})
)
fig2 = px.bar(
    monthly_sum,
    x="月份",
    y="金額",
    color="類型",
    barmode="group",
    color_discrete_map=COLOR_MAP,
    text_auto=".0f",
)
fig2.update_layout(height=400)
st.plotly_chart(fig2, use_container_width=True, key="analysis_monthly_bar")


# ---------- 圖 3:支出分類圓餅圖 ----------
st.subheader("🥧 支出分類")
expense_df = df[df["type"] == "expense"]
if not expense_df.empty:
    cat_sum = (
        expense_df.groupby("category")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"category": "分類", "amount": "金額"})
        .sort_values("金額", ascending=False)
    )
    fig3 = px.pie(cat_sum, values="金額", names="分類", hole=0.4)
    fig3.update_traces(textposition="inside", textinfo="percent+label")
    fig3.update_layout(height=400)
    st.plotly_chart(fig3, use_container_width=True, key="analysis_category_pie")
else:
    st.info("這段期間沒有支出")


# ---------- 圖 4:使用者比較(只在「所有人」時顯示) ----------
if user_filter == "所有人" and df["使用者"].nunique() > 1:
    st.subheader("👥 各使用者收支比較")
    user_sum = (
        df.groupby(["使用者", "類型"])["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "金額"})
    )
    fig4 = px.bar(
        user_sum,
        x="使用者",
        y="金額",
        color="類型",
        barmode="group",
        color_discrete_map=COLOR_MAP,
        text_auto=".0f",
    )
    fig4.update_layout(height=400)
    st.plotly_chart(fig4, use_container_width=True, key="analysis_user_compare")


# ---------- 圖 5:累計結餘走勢 ----------
st.subheader("💹 累計結餘走勢")
df_sorted = df.sort_values("transaction_date")
df_sorted["delta"] = df_sorted.apply(
    lambda r: r["amount"] if r["type"] == "income" else -r["amount"], axis=1
)
daily_delta = (
    df_sorted.groupby(df_sorted["transaction_date"].dt.date)["delta"]
    .sum()
    .reset_index()
    .rename(columns={"transaction_date": "日期", "delta": "當日淨額"})
)
daily_delta["累計結餘"] = daily_delta["當日淨額"].cumsum()
fig5 = px.area(daily_delta, x="日期", y="累計結餘", markers=True)
fig5.update_traces(line_color="#3b82f6", fillcolor="rgba(59,130,246,0.2)")
fig5.update_layout(height=400)
st.plotly_chart(fig5, use_container_width=True, key="analysis_cumulative")
