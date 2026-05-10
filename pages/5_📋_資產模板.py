"""
資產模板:每月個人總資產追蹤
- 本月資產:輸入/編輯本月各帳戶餘額,支援 USD→TWD 換算
- 資產走勢:歷月總資產走勢圖
- 管理類別:新增/編輯/刪除自己的資產類別
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from utils import (
    get_supabase,
    get_current_user,
    require_login,
    render_sidebar,
    get_all_users,
    user_id_to_name_map,
)


st.set_page_config(page_title="資產模板", page_icon="📋", layout="wide")

require_login()
render_sidebar()
me = get_current_user()

st.title("📋 資產模板")
st.caption("追蹤每月個人總資產(支援多幣別)")


# ====== 預設模板(第一次使用一鍵建立) ======
DEFAULT_TEMPLATE = [
    # 帳戶資產
    {"section": "bank", "name": "國泰",     "default_currency": "TWD", "has_cost_value": False, "display_order": 1},
    {"section": "bank", "name": "台銀",     "default_currency": "TWD", "has_cost_value": False, "display_order": 2},
    {"section": "bank", "name": "中信",     "default_currency": "TWD", "has_cost_value": False, "display_order": 3},
    {"section": "bank", "name": "郵局",     "default_currency": "TWD", "has_cost_value": False, "display_order": 4},
    {"section": "bank", "name": "定存",     "default_currency": "TWD", "has_cost_value": False, "display_order": 5},
    {"section": "bank", "name": "外幣帳戶", "default_currency": "USD", "has_cost_value": False, "display_order": 6},
    # 投資帳戶
    {"section": "investment", "name": "國泰",     "default_currency": "TWD", "has_cost_value": True, "display_order": 1},
    {"section": "investment", "name": "台新",     "default_currency": "TWD", "has_cost_value": True, "display_order": 2},
    {"section": "investment", "name": "複委託",   "default_currency": "USD", "has_cost_value": True, "display_order": 3},
    {"section": "investment", "name": "海外帳戶", "default_currency": "USD", "has_cost_value": True, "display_order": 4},
    # 其他項目
    {"section": "other", "name": "保險現值",     "default_currency": "TWD", "has_cost_value": False, "display_order": 1},
    {"section": "other", "name": "現金",         "default_currency": "TWD", "has_cost_value": False, "display_order": 2},
    {"section": "other", "name": "悠遊卡/iCash", "default_currency": "TWD", "has_cost_value": False, "display_order": 3},
    {"section": "other", "name": "不動產",       "default_currency": "TWD", "has_cost_value": False, "display_order": 4},
    {"section": "other", "name": "車輛",         "default_currency": "TWD", "has_cost_value": False, "display_order": 5},
    {"section": "other", "name": "應收款",       "default_currency": "TWD", "has_cost_value": False, "display_order": 6},
]

SECTION_ICONS = {"bank": "🏦", "investment": "📈", "other": "📦"}
SECTION_NAMES = {"bank": "帳戶資產", "investment": "投資帳戶", "other": "其他項目"}
SECTION_ORDER = ["bank", "investment", "other"]


# ====== 取資料的工具函式 ======
def get_my_categories():
    """取得目前使用者的所有資產類別。"""
    try:
        result = (
            get_supabase()
            .table("asset_categories")
            .select("*")
            .eq("user_id", me["id"])
            .eq("is_active", True)
            .order("display_order")
            .execute()
        )
        return result.data or []
    except Exception as e:
        st.error(f"讀取類別失敗:{e}")
        return []


def get_monthly_data(user_id, year, month):
    """讀某個 user 某月的所有資產記錄,回傳 dict: {category_id: row}。"""
    try:
        result = (
            get_supabase()
            .table("monthly_assets")
            .select("*")
            .eq("user_id", user_id)
            .eq("year", year)
            .eq("month", month)
            .execute()
        )
        return {row["category_id"]: row for row in (result.data or [])}
    except Exception as e:
        st.error(f"讀取月度資料失敗:{e}")
        return {}


def install_default_template():
    """一鍵建立預設模板。"""
    rows = [{**c, "user_id": me["id"]} for c in DEFAULT_TEMPLATE]
    try:
        get_supabase().table("asset_categories").insert(rows).execute()
        st.success(f"已建立 {len(rows)} 個預設類別!")
        st.rerun()
    except Exception as e:
        st.error(f"建立失敗:{e}")


def install_missing_defaults():
    """只補上預設模板裡有、但使用者還沒建立的類別(用 (section, name) 比對)。"""
    existing = (
        get_supabase()
        .table("asset_categories")
        .select("section, name")
        .eq("user_id", me["id"])
        .execute()
        .data
    ) or []
    existing_keys = {(c["section"], c["name"]) for c in existing}

    missing = [
        c for c in DEFAULT_TEMPLATE
        if (c["section"], c["name"]) not in existing_keys
    ]
    if not missing:
        st.toast("已經全部存在,沒有要補的", icon="✅")
        return
    rows = [{**c, "user_id": me["id"]} for c in missing]
    try:
        get_supabase().table("asset_categories").insert(rows).execute()
        st.success(f"已補建 {len(rows)} 個類別!")
        st.rerun()
    except Exception as e:
        st.error(f"補建失敗:{e}")


def to_twd(amount, currency, rate):
    """把任意幣別轉成 TWD。"""
    if amount is None:
        return 0.0
    if currency == "USD":
        return float(amount) * float(rate or 0)
    return float(amount)


# ====== 五個 Tab ======
tab_monthly, tab_chart, tab_combined, tab_io, tab_manage = st.tabs(
    ["📅 本月資產", "📈 資產走勢", "🤝 共同資產", "📤 匯入匯出", "⚙️ 管理類別"]
)


# =====================================================================
#  Tab 1:本月資產
# =====================================================================
def _render_tab_monthly():
    categories = get_my_categories()

    if not categories:
        st.info(
            "👋 你還沒有任何資產類別,先建立模板吧!\n\n"
            "**選項 1**:用我預設準備好的模板(國泰/台銀/中信/郵局/定存/外幣帳戶 + "
            "國泰/台新/複委託/海外帳戶投資帳戶)"
        )
        if st.button("📋 建立預設模板", type="primary"):
            install_default_template()

        st.info("**選項 2**:到「⚙️ 管理類別」分頁自己一個一個加")
        return

    # ---------- 月份選擇 ----------
    today = date.today()
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        year = st.selectbox(
            "年份",
            list(range(today.year - 5, today.year + 2)),
            index=5,  # 對應今年
        )
    with c2:
        month = st.selectbox(
            "月份",
            list(range(1, 13)),
            index=today.month - 1,
            format_func=lambda m: f"{m:02d} 月",
        )
    with c3:
        if st.button("📥 套用上月資料(會覆蓋目前輸入)"):
            prev_year = year if month > 1 else year - 1
            prev_month = month - 1 if month > 1 else 12
            prev_data = get_monthly_data(me["id"], prev_year, prev_month)
            if not prev_data:
                st.warning("上個月還沒有資料")
            else:
                # 寫進 session_state 讓 widgets 用
                for cat in categories:
                    pd = prev_data.get(cat["id"])
                    if not pd:
                        continue
                    base = f"a_{cat['id']}_{year}_{month}"
                    st.session_state[f"{base}_curr"] = pd.get("currency", "TWD")
                    st.session_state[f"{base}_rate"] = float(pd.get("exchange_rate") or 1)
                    st.session_state[f"{base}_value"] = float(pd.get("current_value") or 0)
                    if cat["has_cost_value"]:
                        st.session_state[f"{base}_cost"] = float(pd.get("cost") or 0)
                st.rerun()

    # ---------- 載入既有資料 ----------
    existing = get_monthly_data(me["id"], year, month)

    # ---------- 狀態提示 ----------
    if existing:
        st.success(
            f"📝 **編輯模式** — 本月已儲存 **{len(existing)}** 筆記錄,"
            f"修改後請按下方「💾 儲存本月資料」更新"
        )
    else:
        st.info("✨ **新增模式** — 本月還沒有資料,填完按下方「💾 儲存本月資料」")

    # ---------- 依 section 渲染 ----------
    grand_total = 0.0
    section_totals = {}
    # 暫存所有輸入的值,儲存時用
    pending_rows = []

    for section in SECTION_ORDER:
        cats_in_section = [c for c in categories if c["section"] == section]
        if not cats_in_section:
            continue

        st.markdown(f"### {SECTION_ICONS[section]} {SECTION_NAMES[section]}")
        section_total = 0.0

        for cat in cats_in_section:
            cat_id = cat["id"]
            existing_row = existing.get(cat_id, {})
            base_key = f"a_{cat_id}_{year}_{month}"

            # 從 existing 拿預設值
            default_curr = existing_row.get("currency", cat["default_currency"])
            default_rate = float(existing_row.get("exchange_rate") or 1)
            default_value = float(existing_row.get("current_value") or 0)
            default_cost = float(existing_row.get("cost") or 0)

            if cat["has_cost_value"]:
                # 投資帳戶:幣別 + 成本 + 現值 + 匯率
                cols = st.columns([2, 1.2, 1.5, 1.5, 1.2, 2])
                cols[0].markdown(f"**{cat['name']}**")
                currency = cols[1].selectbox(
                    "幣別",
                    ["TWD", "USD"],
                    index=0 if default_curr == "TWD" else 1,
                    key=f"{base_key}_curr",
                    label_visibility="collapsed",
                )
                cost = cols[2].number_input(
                    "成本",
                    step=100,
                    value=int(default_cost),
                    key=f"{base_key}_cost",
                    label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
                    format="%d",
                    help="允許負數(例如未實現的負成本調整)",
                )
                current_value = cols[3].number_input(
                    "現值",
                    step=100,
                    value=int(default_value),
                    key=f"{base_key}_value",
                    label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
                    format="%d",
                    help="允許負數(例如貸款、信用卡欠款等負債)",
                )
                if currency == "USD":
                    rate = cols[4].number_input(
                        "匯率",
                        min_value=0.0,
                        step=0.1,
                        value=default_rate if default_rate > 0 else 31.5,
                        key=f"{base_key}_rate",
                        label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
                    )
                else:
                    cols[4].markdown("&nbsp;")
                    rate = 1.0

                value_twd = to_twd(current_value, currency, rate)
                cost_twd = to_twd(cost, currency, rate)
                pnl = value_twd - cost_twd

                pnl_color = "🟢" if pnl >= 0 else "🔴"
                # 負數現值用紅字標示(代表負債)
                value_html = (
                    f"<span style='color:#ef4444'>NT${value_twd:,.0f}</span>"
                    if value_twd < 0
                    else f"NT${value_twd:,.0f}"
                )
                cols[5].markdown(
                    f"{value_html}<br>"
                    f"<small>{pnl_color} {pnl:+,.0f}</small>",
                    unsafe_allow_html=True,
                )

                section_total += value_twd
                pending_rows.append(
                    {
                        "user_id": me["id"],
                        "category_id": cat_id,
                        "year": year,
                        "month": month,
                        "currency": currency,
                        "exchange_rate": rate,
                        "current_value": current_value,
                        "cost": cost,
                    }
                )

            else:
                # 一般帳戶:幣別 + 金額 + 匯率(USD 才顯示)
                cols = st.columns([2, 1.2, 2, 1.5, 2])
                cols[0].markdown(f"**{cat['name']}**")
                currency = cols[1].selectbox(
                    "幣別",
                    ["TWD", "USD"],
                    index=0 if default_curr == "TWD" else 1,
                    key=f"{base_key}_curr",
                    label_visibility="collapsed",
                )
                current_value = cols[2].number_input(
                    "金額",
                    step=100,
                    value=int(default_value),
                    key=f"{base_key}_value",
                    label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
                    format="%d",
                    help="允許負數(例如貸款餘額、信用卡欠款等負債)",
                )
                if currency == "USD":
                    rate = cols[3].number_input(
                        "匯率",
                        min_value=0.0,
                        step=0.1,
                        value=default_rate if default_rate > 0 else 31.5,
                        key=f"{base_key}_rate",
                        label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
                    )
                else:
                    cols[3].markdown("&nbsp;")
                    rate = 1.0

                value_twd = to_twd(current_value, currency, rate)
                # 負數紅字顯示(代表負債)
                if value_twd < 0:
                    cols[4].markdown(
                        f"<span style='color:#ef4444'>NT${value_twd:,.0f}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    cols[4].markdown(f"NT${value_twd:,.0f}")

                section_total += value_twd
                pending_rows.append(
                    {
                        "user_id": me["id"],
                        "category_id": cat_id,
                        "year": year,
                        "month": month,
                        "currency": currency,
                        "exchange_rate": rate,
                        "current_value": current_value,
                        "cost": None,
                    }
                )

        st.markdown(f"<small>小計:**NT$ {section_total:,.0f}**</small>", unsafe_allow_html=True)
        st.markdown("---")
        section_totals[section] = section_total
        grand_total += section_total

    # ---------- 總計 + 儲存 ----------
    st.markdown("## 💎 總資產")
    cols = st.columns(4)
    for i, sec in enumerate(SECTION_ORDER):
        if sec in section_totals:
            cols[i].metric(
                f"{SECTION_ICONS[sec]} {SECTION_NAMES[sec]}",
                f"NT$ {section_totals[sec]:,.0f}",
            )
    cols[3].metric("總計", f"NT$ {grand_total:,.0f}")

    save_col, del_col = st.columns([3, 1])
    with save_col:
        if st.button("💾 儲存本月資料", type="primary", use_container_width=True):
            try:
                # 先刪除這個月的舊資料,再批次插入(這樣比 upsert 簡單可靠)
                client = get_supabase()
                client.table("monthly_assets").delete().eq("user_id", me["id"]).eq(
                    "year", year
                ).eq("month", month).execute()
                client.table("monthly_assets").insert(pending_rows).execute()
                st.success(f"已儲存 {year} 年 {month:02d} 月資料 ✅")
            except Exception as e:
                st.error(f"儲存失敗:{e}")

    with del_col:
        # 用 session_state 做二次確認(防止誤按)
        confirm_key = f"confirm_del_{year}_{month}"
        if not st.session_state.get(confirm_key):
            if existing and st.button(
                "🗑️ 清空本月",
                use_container_width=True,
                help=f"刪除 {year}/{month:02d} 的所有資料",
            ):
                st.session_state[confirm_key] = True
                st.rerun()
        else:
            st.warning("⚠️ 確定要刪除嗎?")
            yes, no = st.columns(2)
            if yes.button("確定", type="primary", key=f"yes_{year}_{month}"):
                try:
                    get_supabase().table("monthly_assets").delete().eq(
                        "user_id", me["id"]
                    ).eq("year", year).eq("month", month).execute()
                    # 清掉這個月對應的 session_state widget keys
                    for cat in categories:
                        base = f"a_{cat['id']}_{year}_{month}"
                        for suffix in ("_curr", "_rate", "_value", "_cost"):
                            st.session_state.pop(f"{base}{suffix}", None)
                    st.session_state.pop(confirm_key, None)
                    st.success(f"已刪除 {year}/{month:02d} 全部資料")
                    st.rerun()
                except Exception as e:
                    st.error(f"刪除失敗:{e}")
            if no.button("取消", key=f"no_{year}_{month}"):
                st.session_state.pop(confirm_key, None)
                st.rerun()


# =====================================================================
#  Tab 2:資產走勢
# =====================================================================
def _render_tab_chart():
    name_map = user_id_to_name_map()
    all_users = get_all_users()
    name_to_id = {(u["display_name"] or u["id"][:8]): u["id"] for u in all_users}

    # ===== 篩選列 =====
    c1, c2 = st.columns([1, 2])
    with c1:
        view_options = ["我自己", "所有人"] + list(name_to_id.keys())
        view_user = st.selectbox("看誰的資產", view_options, key="chart_user")
    with c2:
        # 快速時間範圍選擇
        range_options = {
            "近 3 個月": 3,
            "近 6 個月": 6,
            "近 12 個月": 12,
            "今年": "ytd",
            "全部": "all",
        }
        chart_range = st.radio(
            "範圍",
            list(range_options.keys()),
            index=2,
            horizontal=True,
            key="chart_range",
        )

    # ===== 取資料(全部,後面再過濾) =====
    try:
        query = (
            get_supabase()
            .table("monthly_assets")
            .select("*, asset_categories(name, section)")
            .order("year")
            .order("month")
        )
        if view_user == "我自己":
            query = query.eq("user_id", me["id"])
        elif view_user != "所有人":
            query = query.eq("user_id", name_to_id[view_user])
        records = query.execute().data or []
    except Exception as e:
        st.error(f"讀取失敗:{e}")
        records = []

    if not records:
        st.info("還沒有資料,先到「📅 本月資產」儲存幾筆吧!")
        return

    # ===== 整理 dataframe =====
    df = pd.DataFrame(records)
    df["transaction_date"] = pd.to_datetime(
        df.apply(lambda r: f"{r['year']:04d}-{r['month']:02d}-01", axis=1)
    )
    df["年月"] = df["transaction_date"].dt.strftime("%Y-%m")
    df["TWD"] = df.apply(
        lambda r: to_twd(r["current_value"], r["currency"], r["exchange_rate"]),
        axis=1,
    )
    df["cost_TWD"] = df.apply(
        lambda r: to_twd(r.get("cost") or 0, r["currency"], r["exchange_rate"]),
        axis=1,
    )
    df["section"] = df["asset_categories"].apply(
        lambda c: c["section"] if c else "other"
    )
    df["section_name"] = df["section"].map(SECTION_NAMES)
    df["使用者"] = df["user_id"].map(lambda x: name_map.get(x, x[:8]))
    df["類別"] = df["asset_categories"].apply(lambda c: c["name"] if c else "?")

    # ===== 套用時間範圍 =====
    range_val = range_options[chart_range]
    today_dt = pd.Timestamp.today().to_period("M").to_timestamp()
    if range_val == "ytd":
        start_dt = pd.Timestamp(today_dt.year, 1, 1)
        df_ranged = df[df["transaction_date"] >= start_dt]
    elif range_val == "all":
        df_ranged = df
    else:
        # 整數月數
        start_dt = today_dt - pd.DateOffset(months=range_val - 1)
        df_ranged = df[df["transaction_date"] >= start_dt]

    if df_ranged.empty:
        st.warning(f"在範圍「{chart_range}」內沒有資料")
        return

    # ===== KPI 卡(只在「我自己」或單人時顯示) =====
    if view_user != "所有人":
        monthly_total = df_ranged.groupby("年月")["TWD"].sum().sort_index()
        if len(monthly_total) >= 1:
            latest_total = monthly_total.iloc[-1]
            first_total = monthly_total.iloc[0]
            change = latest_total - first_total
            avg_change = (
                (latest_total - first_total) / max(len(monthly_total) - 1, 1)
                if len(monthly_total) > 1
                else 0
            )
            high_month = monthly_total.idxmax()
            low_month = monthly_total.idxmin()

            st.markdown("### 📊 區間摘要")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(
                f"最新 ({monthly_total.index[-1]})",
                f"NT$ {latest_total:,.0f}",
            )
            k2.metric(
                "區間變化",
                f"NT$ {change:+,.0f}",
                delta=f"{(change / abs(first_total) * 100):+.1f}%"
                if first_total != 0 else None,
            )
            k3.metric("平均月增", f"NT$ {avg_change:+,.0f}")
            k4.metric(
                "最高 / 最低",
                f"{high_month}",
                delta=f"低點 {low_month}",
                delta_color="off",
            )
            st.divider()

    # ===== 圖 1:總資產走勢 =====
    st.markdown("### 💎 總資產走勢")
    if view_user == "所有人":
        total_by_month = (
            df_ranged.groupby(["年月", "使用者"])["TWD"].sum().reset_index()
        )
        fig = px.line(
            total_by_month, x="年月", y="TWD", color="使用者", markers=True
        )
    else:
        total_by_month = df_ranged.groupby("年月")["TWD"].sum().reset_index()
        fig = px.line(total_by_month, x="年月", y="TWD", markers=True)
        fig.update_traces(line_color="#3b82f6", line_width=3)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
    fig.update_layout(height=380, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # ===== 圖 2:每月差額(本期 - 上期) =====
    if view_user != "所有人":
        st.markdown("### 📈 每月變化")
        mt = df_ranged.groupby("年月")["TWD"].sum().sort_index()
        diff = mt.diff().dropna()
        if len(diff) > 0:
            diff_df = diff.reset_index()
            diff_df.columns = ["年月", "變化"]
            fig_diff = go.Figure()
            fig_diff.add_trace(
                go.Bar(
                    x=diff_df["年月"],
                    y=diff_df["變化"],
                    marker_color=[
                        "#10b981" if v >= 0 else "#ef4444" for v in diff_df["變化"]
                    ],
                    text=diff_df["變化"].apply(lambda v: f"{v:+,.0f}"),
                    textposition="outside",
                )
            )
            fig_diff.update_layout(
                height=320, hovermode="x unified",
                yaxis_title="台幣變化", showlegend=False,
            )
            st.plotly_chart(fig_diff, use_container_width=True)
        else:
            st.caption("(只有一個月的資料,還沒辦法算月差)")

    # ===== 圖 3:依分區堆疊面積 =====
    if view_user != "所有人":
        st.markdown("### 📊 資產組成(依分區)")
        section_by_month = (
            df_ranged.groupby(["年月", "section_name"])["TWD"].sum().reset_index()
        )
        fig2 = px.area(
            section_by_month,
            x="年月",
            y="TWD",
            color="section_name",
            color_discrete_map={
                "帳戶資產": "#3b82f6",
                "投資帳戶": "#10b981",
                "其他項目": "#f59e0b",
            },
        )
        fig2.update_layout(height=350, hovermode="x unified", legend_title_text="")
        st.plotly_chart(fig2, use_container_width=True)

    # ===== 圖 4:投資成本 vs 現值 =====
    inv_df = df_ranged[df_ranged["section"] == "investment"].copy()
    if not inv_df.empty and view_user != "所有人":
        st.markdown("### 📈 投資:成本 vs 現值")
        inv_monthly = inv_df.groupby("年月")[["TWD", "cost_TWD"]].sum().reset_index()
        inv_monthly["損益"] = inv_monthly["TWD"] - inv_monthly["cost_TWD"]
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=inv_monthly["年月"], y=inv_monthly["cost_TWD"],
            name="成本", mode="lines+markers",
            line=dict(color="#94a3b8", dash="dot"),
        ))
        fig3.add_trace(go.Scatter(
            x=inv_monthly["年月"], y=inv_monthly["TWD"],
            name="現值", mode="lines+markers",
            line=dict(color="#10b981", width=3),
            fill="tonexty", fillcolor="rgba(16,185,129,0.15)",
        ))
        fig3.update_layout(height=350, hovermode="x unified")
        st.plotly_chart(fig3, use_container_width=True)

        # 損益 bar
        st.markdown("### 💰 投資損益")
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            x=inv_monthly["年月"], y=inv_monthly["損益"],
            marker_color=[
                "#10b981" if v >= 0 else "#ef4444"
                for v in inv_monthly["損益"]
            ],
            text=inv_monthly["損益"].apply(lambda v: f"{v:+,.0f}"),
            textposition="outside",
        ))
        fig4.update_layout(height=300, hovermode="x unified", showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)

    # ===== 月份明細 =====
    st.divider()
    st.markdown("### 📋 月份明細")

    if view_user == "所有人":
        st.caption("(看「所有人」時無法選單一月份明細,請選特定使用者)")
        return

    available_ym = sorted(df["年月"].unique(), reverse=True)
    if not available_ym:
        return

    selected_ym = st.selectbox(
        "選擇月份",
        available_ym,
        index=0,
        key="chart_detail_ym",
    )

    detail_df = df[df["年月"] == selected_ym].copy()
    if detail_df.empty:
        st.info("這個月沒有資料")
        return

    # 摘要
    total = detail_df["TWD"].sum()
    pos_sum = detail_df.loc[detail_df["TWD"] >= 0, "TWD"].sum()
    neg_sum = detail_df.loc[detail_df["TWD"] < 0, "TWD"].sum()

    s1, s2, s3 = st.columns(3)
    s1.metric("總計", f"NT$ {total:,.0f}")
    s2.metric("正資產", f"NT$ {pos_sum:,.0f}")
    s3.metric("負債", f"NT$ {neg_sum:,.0f}", delta_color="off")

    # 表格(負數紅色)
    show_df = detail_df[
        ["section_name", "類別", "currency", "current_value", "exchange_rate", "TWD"]
    ].rename(
        columns={
            "section_name": "分區",
            "currency": "幣別",
            "current_value": "原幣金額",
            "exchange_rate": "匯率",
            "TWD": "台幣金額",
        }
    ).sort_values(["分區", "類別"])

    st.dataframe(
        show_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "原幣金額": st.column_config.NumberColumn(format="%.2f"),
            "匯率": st.column_config.NumberColumn(format="%.2f"),
            "台幣金額": st.column_config.NumberColumn(format="%d"),
        },
    )


# 在 tab 中執行該函式
with tab_monthly:
    _render_tab_monthly()
with tab_chart:
    _render_tab_chart()


# =====================================================================
#  Tab 3:共同資產
# =====================================================================
def _render_tab_combined():
    st.caption(
        "把幾個人允許的資產合在一起算總額,適合追蹤家庭/伴侶/合夥的共同資產。"
        "私人類別、以及你沒被分享的『指定』類別不會出現在這裡。"
    )

    name_map_c = user_id_to_name_map()
    all_users_c = get_all_users()

    # ===== 1. 選擇要納入的使用者 =====
    user_id_options = [u["id"] for u in all_users_c]
    selected_user_ids = st.multiselect(
        "包含的使用者(可多選)",
        options=user_id_options,
        default=[me["id"]],
        format_func=lambda uid: name_map_c.get(uid, uid[:8])
        + (" (我)" if uid == me["id"] else ""),
        key="combined_users",
    )
    if not selected_user_ids:
        st.info("👆 至少選一個使用者")
        return

    # ===== 2. 取出對選擇者可見的所有類別 =====
    try:
        cats_q = (
            get_supabase()
            .table("asset_categories")
            .select("*")
            .in_("user_id", selected_user_ids)
            .eq("is_active", True)
            .order("user_id")
            .order("display_order")
            .execute()
        )
        visible_cats = cats_q.data or []
    except Exception as e:
        st.error(f"讀取類別失敗:{e}")
        visible_cats = []

    if not visible_cats:
        st.info("沒有可看到的類別(對方可能還沒建立或全部設為私人)")
        return

    # ===== 3. 多選要納入的類別(預設全選) =====
    VIS_ICON_MAP = {"private": "🔒", "public": "🌐", "shared": "👥"}
    cat_label_map = {}
    for cat in visible_cats:
        owner = name_map_c.get(cat["user_id"], cat["user_id"][:8])
        vis = cat.get("visibility") or ("public" if cat.get("is_public") else "private")
        vis_icon = VIS_ICON_MAP.get(vis, "")
        if cat["user_id"] == me["id"]:
            vis_icon = ""
        label = f"{owner}・{SECTION_ICONS[cat['section']]} {cat['name']} {vis_icon}".strip()
        cat_label_map[cat["id"]] = label

    selected_cat_ids = st.multiselect(
        "包含的類別(預設全部,可取消勾選不想納入合計的)",
        options=list(cat_label_map.keys()),
        default=list(cat_label_map.keys()),
        format_func=lambda cid: cat_label_map[cid],
        key="combined_cats",
    )
    if not selected_cat_ids:
        st.info("👆 至少選一個類別")
        return

    # ===== 4. 取所有可見的月度資料 =====
    try:
        all_q = (
            get_supabase()
            .table("monthly_assets")
            .select("*, asset_categories(name, section, has_cost_value)")
            .in_("user_id", selected_user_ids)
            .in_("category_id", selected_cat_ids)
            .order("year")
            .order("month")
            .execute()
        )
        all_records = all_q.data or []
    except Exception as e:
        st.error(f"讀取資產失敗:{e}")
        all_records = []

    if not all_records:
        st.warning("這些使用者 / 類別還沒有任何資料")
        return

    # ===== 5. 整理 dataframe =====
    df = pd.DataFrame(all_records)
    df["transaction_date"] = pd.to_datetime(
        df.apply(lambda r: f"{r['year']:04d}-{r['month']:02d}-01", axis=1)
    )
    df["年月"] = df["transaction_date"].dt.strftime("%Y-%m")
    df["TWD"] = df.apply(
        lambda r: to_twd(r["current_value"], r["currency"], r["exchange_rate"]),
        axis=1,
    )
    df["cost_TWD"] = df.apply(
        lambda r: to_twd(r.get("cost") or 0, r["currency"], r["exchange_rate"])
        if (r["asset_categories"] or {}).get("has_cost_value")
        else 0,
        axis=1,
    )
    df["使用者"] = df["user_id"].map(lambda x: name_map_c.get(x, x[:8]))
    df["分區"] = df["asset_categories"].apply(lambda c: c["section"] if c else "other")
    df["分區名"] = df["分區"].map(SECTION_NAMES)
    df["類別"] = df["asset_categories"].apply(lambda c: c["name"] if c else "?")

    # ===== 6. 時間範圍快選 =====
    range_options = {
        "近 3 個月": 3,
        "近 6 個月": 6,
        "近 12 個月": 12,
        "今年": "ytd",
        "全部": "all",
    }
    chart_range = st.radio(
        "範圍",
        list(range_options.keys()),
        index=2,
        horizontal=True,
        key="combined_range",
    )

    range_val = range_options[chart_range]
    today_dt = pd.Timestamp.today().to_period("M").to_timestamp()
    if range_val == "ytd":
        start_dt = pd.Timestamp(today_dt.year, 1, 1)
        df_ranged = df[df["transaction_date"] >= start_dt]
    elif range_val == "all":
        df_ranged = df
    else:
        start_dt = today_dt - pd.DateOffset(months=range_val - 1)
        df_ranged = df[df["transaction_date"] >= start_dt]

    if df_ranged.empty:
        st.warning(f"在範圍「{chart_range}」內沒有資料")
        return

    # ===== 7. KPI 摘要卡 =====
    st.markdown("### 💎 共同資產摘要")
    monthly_total = df_ranged.groupby("年月")["TWD"].sum().sort_index()

    latest_total = monthly_total.iloc[-1]
    first_total = monthly_total.iloc[0] if len(monthly_total) > 0 else 0
    change = latest_total - first_total
    avg_change = (
        change / max(len(monthly_total) - 1, 1)
        if len(monthly_total) > 1
        else 0
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        f"最新 ({monthly_total.index[-1]})",
        f"NT$ {latest_total:,.0f}",
    )
    k2.metric(
        "區間變化",
        f"NT$ {change:+,.0f}",
        delta=f"{(change / abs(first_total) * 100):+.1f}%"
        if first_total != 0 else None,
    )
    k3.metric("平均月增", f"NT$ {avg_change:+,.0f}")
    k4.metric(
        "最高 / 最低",
        f"{monthly_total.idxmax()}",
        delta=f"低點 {monthly_total.idxmin()}",
        delta_color="off",
    )

    # 投資成本/損益(如果有)
    has_inv = (df_ranged["cost_TWD"] != 0).any()
    if has_inv:
        latest_ym = monthly_total.index[-1]
        latest_df = df_ranged[df_ranged["年月"] == latest_ym]
        total_cost = latest_df["cost_TWD"].sum()
        total_inv_value = latest_df.loc[latest_df["cost_TWD"] != 0, "TWD"].sum()
        pnl = total_inv_value - total_cost

        i1, i2, i3 = st.columns(3)
        i1.metric("投資成本(本月)", f"NT$ {total_cost:,.0f}")
        i2.metric("投資現值(本月)", f"NT$ {total_inv_value:,.0f}")
        i3.metric(
            "未實現損益",
            f"NT$ {pnl:+,.0f}",
            delta=f"{pnl / total_cost * 100:+.1f}%" if total_cost > 0 else None,
        )

    st.divider()

    # ===== 8. 共同資產走勢(粗合計 + 細各人) =====
    st.markdown("### 📈 共同資產走勢")
    per_user_line = (
        df_ranged.groupby(["年月", "使用者"])["TWD"].sum().reset_index()
    )

    fig_trend = go.Figure()
    # 各人線(虛線、半透明)
    for user in per_user_line["使用者"].unique():
        sub = per_user_line[per_user_line["使用者"] == user]
        fig_trend.add_trace(
            go.Scatter(
                x=sub["年月"],
                y=sub["TWD"],
                mode="lines+markers",
                name=user,
                line=dict(width=2, dash="dot"),
                opacity=0.6,
            )
        )
    # 共同合計(粗線)
    fig_trend.add_trace(
        go.Scatter(
            x=monthly_total.index,
            y=monthly_total.values,
            mode="lines+markers",
            name="共同合計",
            line=dict(width=4, color="#3b82f6"),
        )
    )
    fig_trend.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
    fig_trend.update_layout(height=400, hovermode="x unified")
    st.plotly_chart(fig_trend, use_container_width=True)

    # ===== 9. 每月變化 bar =====
    st.markdown("### 📊 每月變化")
    diff = monthly_total.diff().dropna()
    if len(diff) > 0:
        diff_df = diff.reset_index()
        diff_df.columns = ["年月", "變化"]
        fig_diff = go.Figure()
        fig_diff.add_trace(
            go.Bar(
                x=diff_df["年月"],
                y=diff_df["變化"],
                marker_color=[
                    "#10b981" if v >= 0 else "#ef4444" for v in diff_df["變化"]
                ],
                text=diff_df["變化"].apply(lambda v: f"{v:+,.0f}"),
                textposition="outside",
            )
        )
        fig_diff.update_layout(
            height=320, hovermode="x unified",
            yaxis_title="台幣變化", showlegend=False,
        )
        st.plotly_chart(fig_diff, use_container_width=True)
    else:
        st.caption("(只有一個月的資料,還沒辦法算月差)")

    # ===== 10. 各人占比走勢(堆疊面積) =====
    if df_ranged["使用者"].nunique() > 1:
        st.markdown("### 👥 各人占比走勢")
        # 注意:堆疊面積對負數會詭異,僅用正資產部分繪製
        positive_df = df_ranged[df_ranged["TWD"] > 0].copy()
        if not positive_df.empty:
            user_stack = (
                positive_df.groupby(["年月", "使用者"])["TWD"]
                .sum()
                .reset_index()
            )
            fig_stack = px.area(
                user_stack,
                x="年月",
                y="TWD",
                color="使用者",
            )
            fig_stack.update_layout(
                height=350, hovermode="x unified", legend_title_text=""
            )
            st.plotly_chart(fig_stack, use_container_width=True)
            st.caption("ℹ️ 此圖只計入正資產,負債(負數)不參與堆疊。")

    st.divider()

    # ===== 11. 月份明細 =====
    st.markdown("### 📋 月份明細")
    available_ym = sorted(df["年月"].unique(), reverse=True)
    selected_ym = st.selectbox(
        "選擇月份",
        available_ym,
        index=0,
        key="combined_detail_ym",
    )

    detail_df = df[df["年月"] == selected_ym].copy()
    if detail_df.empty:
        st.info("這個月沒有資料")
        return

    # 摘要
    total = detail_df["TWD"].sum()
    pos_sum = detail_df.loc[detail_df["TWD"] >= 0, "TWD"].sum()
    neg_sum = detail_df.loc[detail_df["TWD"] < 0, "TWD"].sum()

    s1, s2, s3 = st.columns(3)
    s1.metric(f"{selected_ym} 共同總計", f"NT$ {total:,.0f}")
    s2.metric("正資產", f"NT$ {pos_sum:,.0f}")
    s3.metric("負債", f"NT$ {neg_sum:,.0f}", delta_color="off")

    # 各人小計(本月)
    st.markdown("#### 👥 各人小計")
    per_user_detail = (
        detail_df.groupby("使用者")["TWD"].sum().reset_index().sort_values(
            "TWD", ascending=False
        )
    )
    user_cols = st.columns(max(len(per_user_detail), 1))
    for i, (_, row) in enumerate(per_user_detail.iterrows()):
        pct = row["TWD"] / total * 100 if total != 0 else 0
        user_cols[i].metric(
            row["使用者"],
            f"NT$ {row['TWD']:,.0f}",
            delta=f"{pct:.0f}%" if total != 0 else None,
            delta_color="off",
        )

    # 兩個圓餅
    st.markdown("#### 🥧 占比圖")
    pie_col1, pie_col2 = st.columns(2)

    with pie_col1:
        st.caption("依分區")
        per_section = detail_df.loc[detail_df["TWD"] > 0].groupby("分區名")["TWD"].sum().reset_index()
        if not per_section.empty:
            fig_sec = px.pie(
                per_section,
                values="TWD",
                names="分區名",
                hole=0.4,
                color="分區名",
                color_discrete_map={
                    "帳戶資產": "#3b82f6",
                    "投資帳戶": "#10b981",
                    "其他項目": "#f59e0b",
                },
            )
            fig_sec.update_traces(textposition="inside", textinfo="percent+label")
            fig_sec.update_layout(height=320, showlegend=False)
            st.plotly_chart(fig_sec, use_container_width=True)
        else:
            st.caption("(本月沒有正資產)")

    with pie_col2:
        st.caption("依使用者")
        per_user_pie = detail_df.loc[detail_df["TWD"] > 0].groupby("使用者")["TWD"].sum().reset_index()
        if not per_user_pie.empty and len(per_user_pie) > 1:
            fig_user = px.pie(per_user_pie, values="TWD", names="使用者", hole=0.4)
            fig_user.update_traces(textposition="inside", textinfo="percent+label")
            fig_user.update_layout(height=320, showlegend=False)
            st.plotly_chart(fig_user, use_container_width=True)
        else:
            st.caption("(只有一個人,不顯示)")

    # 細項表格
    st.markdown("#### 📋 細項")
    show_df = (
        detail_df[["使用者", "分區名", "類別", "currency", "current_value",
                   "exchange_rate", "TWD"]]
        .copy()
        .rename(columns={
            "分區名": "分區",
            "currency": "幣別",
            "current_value": "原幣金額",
            "exchange_rate": "匯率",
            "TWD": "台幣金額",
        })
        .sort_values(["使用者", "分區", "類別"])
    )
    st.dataframe(
        show_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "原幣金額": st.column_config.NumberColumn(format="%.2f"),
            "匯率": st.column_config.NumberColumn(format="%.2f"),
            "台幣金額": st.column_config.NumberColumn(format="%d"),
        },
    )


# 在 tab 中執行該函式
with tab_combined:
    _render_tab_combined()


# =====================================================================
#  Tab 4:匯入匯出
# =====================================================================
with tab_io:
    st.caption(
        "把你的資產資料下載成 CSV 留底,或從 CSV 一次匯入大量資料"
        "(例如把過去半年的記錄一次補進來)"
    )

    # ====== 匯出 ======
    st.markdown("### 📥 匯出 CSV")
    exp_col1, exp_col2, exp_col3 = st.columns([1, 1, 2])
    with exp_col1:
        exp_start_year = st.number_input(
            "起始年", min_value=2000, max_value=2100, value=date.today().year - 1, step=1
        )
        exp_start_month = st.selectbox(
            "起始月", list(range(1, 13)), index=0, format_func=lambda m: f"{m:02d}",
            key="exp_start_month",
        )
    with exp_col2:
        exp_end_year = st.number_input(
            "結束年", min_value=2000, max_value=2100, value=date.today().year, step=1
        )
        exp_end_month = st.selectbox(
            "結束月", list(range(1, 13)), index=11, format_func=lambda m: f"{m:02d}",
            key="exp_end_month",
        )
    with exp_col3:
        exp_only_me = st.checkbox("只匯出自己的資料", value=True)
        st.caption("(取消勾選則含其他人公開的資料)")

    # 用 (year * 100 + month) 把區間轉成數字方便比對
    exp_start_val = exp_start_year * 100 + exp_start_month
    exp_end_val = exp_end_year * 100 + exp_end_month

    if exp_start_val > exp_end_val:
        st.error("起始年月不能晚於結束年月")
    else:
        # 抓資料
        try:
            q = (
                get_supabase()
                .table("monthly_assets")
                .select("*, asset_categories(name, section, has_cost_value)")
                .order("year")
                .order("month")
            )
            if exp_only_me:
                q = q.eq("user_id", me["id"])
            all_rows = q.execute().data or []
        except Exception as e:
            st.error(f"讀取失敗:{e}")
            all_rows = []

        # 按月份範圍篩
        in_range = [
            r for r in all_rows
            if exp_start_val <= r["year"] * 100 + r["month"] <= exp_end_val
        ]

        if in_range:
            name_map_exp = user_id_to_name_map() if not exp_only_me else {}
            # 建構 dataframe
            rows = []
            for r in in_range:
                ac = r.get("asset_categories") or {}
                row = {
                    "year": r["year"],
                    "month": r["month"],
                    "section": ac.get("section", ""),
                    "category_name": ac.get("name", ""),
                    "currency": r.get("currency", "TWD"),
                    "exchange_rate": r.get("exchange_rate", 1),
                    "current_value": r.get("current_value", 0),
                    "cost": r.get("cost") if r.get("cost") is not None else "",
                    "notes": r.get("notes") or "",
                }
                if not exp_only_me:
                    row["owner"] = name_map_exp.get(r["user_id"], r["user_id"][:8])
                rows.append(row)

            export_df = pd.DataFrame(rows)
            # 排好欄位順序
            cols_order = ["year", "month", "section", "category_name", "currency",
                          "exchange_rate", "current_value", "cost", "notes"]
            if not exp_only_me:
                cols_order = ["owner"] + cols_order
            export_df = export_df[cols_order]

            csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")  # utf-8-sig 讓 Excel 開不亂碼

            filename = f"sharedlife_assets_{exp_start_year}{exp_start_month:02d}_{exp_end_year}{exp_end_month:02d}.csv"

            st.download_button(
                label=f"⬇️ 下載 {len(in_range)} 筆資料(CSV)",
                data=csv_bytes,
                file_name=filename,
                mime="text/csv",
                type="primary",
            )

            with st.expander(f"📋 預覽前 10 筆"):
                st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)
        else:
            st.info("這個範圍沒有資料")

    st.divider()

    # ====== 格式說明 ======
    st.markdown("### 📑 CSV 格式說明")

    st.markdown(
        """
**欄位定義**(順序可隨意,只要欄位名稱對得上)

| 欄位 | 必填 | 說明 |
|------|------|------|
| `year` | ✅ | 西元年(整數,例如 `2026`) |
| `month` | ✅ | 月份 1-12(整數) |
| `section` | ✅ | 必須是 `bank` / `investment` / `other` 三選一 |
| `category_name` | ✅ | 類別名稱,要對得上你「管理類別」裡已建立的類別,否則該筆會被跳過 |
| `currency` | ✅ | `TWD` 或 `USD` |
| `exchange_rate` | ✅ | 匯率,TWD 填 `1`,USD 填當月匯率(例如 `31.5`) |
| `current_value` | ✅ | 該幣別的金額(不是 TWD,程式會自己 × 匯率算 TWD) |
| `cost` | ⭕️ | 成本(只有投資帳戶要填,銀行帳戶留空) |
| `notes` | ⭕️ | 備註,可留空 |

**範例:**
```csv
year,month,section,category_name,currency,exchange_rate,current_value,cost,notes
2026,5,bank,國泰,TWD,1,52000,,
2026,5,bank,外幣帳戶,USD,31.5,1000,,主要薪轉戶
2026,5,investment,複委託,USD,31.5,5500,4000,Apple/Tesla
```
        """
    )

    # 範本 CSV 下載
    sample_rows = [
        {"year": 2026, "month": 5, "section": "bank", "category_name": "國泰",
         "currency": "TWD", "exchange_rate": 1, "current_value": 52000, "cost": "", "notes": ""},
        {"year": 2026, "month": 5, "section": "bank", "category_name": "外幣帳戶",
         "currency": "USD", "exchange_rate": 31.5, "current_value": 1000, "cost": "", "notes": "薪轉戶"},
        {"year": 2026, "month": 5, "section": "investment", "category_name": "複委託",
         "currency": "USD", "exchange_rate": 31.5, "current_value": 5500, "cost": 4000, "notes": ""},
    ]
    sample_csv = pd.DataFrame(sample_rows).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 下載範本 CSV",
        data=sample_csv,
        file_name="sharedlife_assets_template.csv",
        mime="text/csv",
    )

    st.divider()

    # ====== 匯入 ======
    st.markdown("### 📤 匯入 CSV")
    st.caption(
        "上傳的 CSV **只會影響自己的資料**,不會動到別人的。"
        "類別名稱必須跟「管理類別」裡的對得起來,對不起來的 row 會被略過。"
    )

    uploaded = st.file_uploader(
        "選擇 CSV 檔(UTF-8 編碼)", type=["csv"], key="csv_upload"
    )

    if uploaded:
        try:
            # 嘗試用幾種編碼讀
            try:
                imp_df = pd.read_csv(uploaded, encoding="utf-8-sig")
            except UnicodeDecodeError:
                uploaded.seek(0)
                imp_df = pd.read_csv(uploaded, encoding="big5")

            # 檢查欄位
            required = ["year", "month", "section", "category_name", "currency",
                        "exchange_rate", "current_value"]
            missing = [c for c in required if c not in imp_df.columns]
            if missing:
                st.error(f"CSV 缺欄位:{missing}")
            else:
                # 補上 optional 欄位
                if "cost" not in imp_df.columns:
                    imp_df["cost"] = None
                if "notes" not in imp_df.columns:
                    imp_df["notes"] = None

                # 把目前自己的所有類別查出來(用來對 category_name)
                my_cats = (
                    get_supabase()
                    .table("asset_categories")
                    .select("id, name, section")
                    .eq("user_id", me["id"])
                    .execute()
                    .data
                ) or []
                # (section, name) → cat_id 對照表
                cat_lookup = {
                    (c["section"], c["name"]): c["id"] for c in my_cats
                }

                # 逐筆驗證
                ok_rows = []
                skip_rows = []
                for idx, row in imp_df.iterrows():
                    section = str(row["section"]).strip()
                    name = str(row["category_name"]).strip()

                    # 必填驗證
                    if section not in ("bank", "investment", "other"):
                        skip_rows.append((idx + 2, name, f"section 不是 bank/investment/other:'{section}'"))
                        continue
                    if (section, name) not in cat_lookup:
                        skip_rows.append((idx + 2, name, f"類別不存在於『{SECTION_NAMES[section]}』(請先在管理類別新增)"))
                        continue

                    currency = str(row["currency"]).strip().upper()
                    if currency not in ("TWD", "USD"):
                        skip_rows.append((idx + 2, name, f"currency 不是 TWD/USD:'{currency}'"))
                        continue

                    try:
                        year = int(row["year"])
                        month = int(row["month"])
                        if not (1 <= month <= 12):
                            raise ValueError("month 不在 1-12")
                    except (ValueError, TypeError) as e:
                        skip_rows.append((idx + 2, name, f"year/month 格式錯:{e}"))
                        continue

                    cost_val = row.get("cost")
                    if pd.isna(cost_val) or cost_val == "":
                        cost_val = None
                    else:
                        try:
                            cost_val = float(cost_val)
                        except ValueError:
                            cost_val = None

                    ok_rows.append({
                        "user_id": me["id"],
                        "category_id": cat_lookup[(section, name)],
                        "year": year,
                        "month": month,
                        "currency": currency,
                        "exchange_rate": float(row["exchange_rate"]) if pd.notna(row["exchange_rate"]) else 1.0,
                        "current_value": float(row["current_value"]),
                        "cost": cost_val,
                        "notes": (str(row["notes"]) if pd.notna(row.get("notes")) and str(row["notes"]) != "" else None),
                    })

                # 顯示驗證結果
                c1, c2 = st.columns(2)
                c1.metric("✅ 可匯入", len(ok_rows))
                c2.metric("⏭️ 略過", len(skip_rows))

                if skip_rows:
                    with st.expander(f"⚠️ {len(skip_rows)} 筆被略過(展開看原因)"):
                        sk_df = pd.DataFrame(skip_rows, columns=["CSV 行號", "類別", "原因"])
                        st.dataframe(sk_df, use_container_width=True, hide_index=True)

                if ok_rows:
                    with st.expander(f"📋 預覽要匯入的 {len(ok_rows)} 筆"):
                        preview_df = pd.DataFrame(ok_rows)
                        st.dataframe(preview_df, use_container_width=True, hide_index=True)

                    # 衝突處理選項
                    mode = st.radio(
                        "如果某 (年, 月, 類別) 已經有資料,要怎麼處理?",
                        options=["upsert", "skip", "replace_month"],
                        format_func=lambda m: {
                            "upsert": "🔄 覆蓋(用 CSV 的數字蓋掉舊的)",
                            "skip": "⏭️ 跳過(保留資料庫舊的)",
                            "replace_month": "🗑️ 整月清空再寫入(會刪掉 CSV 沒包到的類別)",
                        }[m],
                        index=0,
                    )

                    if st.button(
                        f"🚀 確定匯入 {len(ok_rows)} 筆",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            client = get_supabase()
                            inserted = 0
                            updated = 0
                            skipped_existing = 0

                            if mode == "replace_month":
                                # 把要寫入的 (year, month) 找出來,先 delete
                                ym_set = {(r["year"], r["month"]) for r in ok_rows}
                                for y, m in ym_set:
                                    client.table("monthly_assets").delete().eq(
                                        "user_id", me["id"]
                                    ).eq("year", y).eq("month", m).execute()
                                # 再批次 insert
                                client.table("monthly_assets").insert(ok_rows).execute()
                                inserted = len(ok_rows)
                            else:
                                # upsert / skip 模式:逐筆檢查
                                for r in ok_rows:
                                    exist_q = (
                                        client.table("monthly_assets")
                                        .select("id")
                                        .eq("user_id", me["id"])
                                        .eq("category_id", r["category_id"])
                                        .eq("year", r["year"])
                                        .eq("month", r["month"])
                                        .execute()
                                    )
                                    if exist_q.data:
                                        if mode == "skip":
                                            skipped_existing += 1
                                            continue
                                        # upsert: 改既有
                                        client.table("monthly_assets").update(
                                            {k: v for k, v in r.items() if k != "user_id"}
                                        ).eq("id", exist_q.data[0]["id"]).execute()
                                        updated += 1
                                    else:
                                        client.table("monthly_assets").insert(r).execute()
                                        inserted += 1

                            msg = f"✅ 完成! 新增 {inserted} 筆,更新 {updated} 筆"
                            if skipped_existing:
                                msg += f",跳過 {skipped_existing} 筆已存在"
                            st.success(msg)
                        except Exception as e:
                            st.error(f"匯入失敗:{e}")

        except Exception as e:
            st.error(f"讀檔失敗:{e}")


# =====================================================================
#  Tab 5:管理類別
# =====================================================================
with tab_manage:
    st.subheader("我的類別清單")
    st.caption(
        "🔒 私人 = 只有自己看得到 / 🌐 公開 = 所有登入者都看得到 / 👥 指定 = 只給特定使用者"
    )
    categories = get_my_categories()

    # ---------- 抓所有類別的分享名單(批次,避免 N+1) ----------
    shares_by_cat = {}  # cat_id -> [user_id, ...]
    if categories:
        try:
            cat_ids = [c["id"] for c in categories]
            shares_data = (
                get_supabase()
                .table("asset_category_shares")
                .select("category_id, shared_with_user_id")
                .in_("category_id", cat_ids)
                .execute()
                .data
            ) or []
            for s in shares_data:
                shares_by_cat.setdefault(s["category_id"], []).append(
                    s["shared_with_user_id"]
                )
        except Exception:
            pass

    # 取所有 user 用於分享名單(排除自己)
    name_map_mgr = user_id_to_name_map()
    shareable_users = [
        u for u in get_all_users() if u["id"] != me["id"]
    ]
    shareable_user_ids = [u["id"] for u in shareable_users]

    # Visibility 選項
    VISIBILITY_OPTIONS = [
        ("private", "🔒 私人"),
        ("public", "🌐 公開"),
        ("shared", "👥 指定"),
    ]
    VIS_VALUES = [v[0] for v in VISIBILITY_OPTIONS]
    VIS_LABELS = dict(VISIBILITY_OPTIONS)

    if not categories:
        st.info("還沒有任何類別")
        if st.button("📋 一鍵建立預設模板", type="primary"):
            install_default_template()
    else:
        st.caption("👇 直接點欄位修改,改完按 Tab 或點外面就會自動儲存")

        # ---------- 通用 update helper ----------
        def _update_cat_field(cat_id, field, key):
            new_val = st.session_state[key]
            try:
                # 名稱欄要去頭尾空白且不能空
                if field == "name":
                    new_val = (new_val or "").strip()
                    if not new_val:
                        st.toast("名稱不能空白", icon="⚠️")
                        return
                # visibility 變更時也同步舊欄位 is_public,確保相容
                update_payload = {field: new_val}
                if field == "visibility":
                    update_payload["is_public"] = (new_val == "public")
                get_supabase().table("asset_categories").update(
                    update_payload
                ).eq("id", cat_id).execute()
                st.toast("已更新", icon="✅")
            except Exception as e:
                st.error(f"更新失敗:{e}")

        # ---------- 分享名單 update helper ----------
        def _update_shares(cat_id, key):
            new_user_ids = st.session_state[key] or []
            try:
                client = get_supabase()
                # 先把這個 category 既有的分享全清掉
                client.table("asset_category_shares").delete().eq(
                    "category_id", cat_id
                ).execute()
                # 寫入新名單
                if new_user_ids:
                    rows = [
                        {"category_id": cat_id, "shared_with_user_id": uid}
                        for uid in new_user_ids
                    ]
                    client.table("asset_category_shares").insert(rows).execute()
                st.toast(
                    f"已更新分享名單({len(new_user_ids)} 人)" if new_user_ids
                    else "已清空分享名單",
                    icon="✅",
                )
            except Exception as e:
                st.error(f"更新分享名單失敗:{e}")

        # 表頭
        h = st.columns([1.2, 2, 0.9, 0.9, 0.7, 1.1, 0.5])
        h[0].markdown("**分區**")
        h[1].markdown("**名稱**")
        h[2].markdown("**幣別**")
        h[3].markdown("**有成本**")
        h[4].markdown("**順序**")
        h[5].markdown("**可見性**")
        h[6].markdown("")

        for cat in categories:
            cid = cat["id"]
            cols = st.columns([1.2, 2, 0.9, 0.9, 0.7, 1.1, 0.5])

            # ----- 分區(可改) -----
            sec_key = f"sec_{cid}"
            cols[0].selectbox(
                "分區",
                SECTION_ORDER,
                index=SECTION_ORDER.index(cat["section"]),
                format_func=lambda s: f"{SECTION_ICONS[s]} {SECTION_NAMES[s]}",
                key=sec_key,
                on_change=_update_cat_field,
                args=(cid, "section", sec_key),
                label_visibility="collapsed",
            )

            # ----- 名稱(可改) -----
            name_key = f"name_{cid}"
            cols[1].text_input(
                "名稱",
                value=cat["name"],
                key=name_key,
                on_change=_update_cat_field,
                args=(cid, "name", name_key),
                label_visibility="collapsed",
            )

            # ----- 幣別(可改) -----
            curr_key = f"curr_{cid}"
            cols[2].selectbox(
                "幣別",
                ["TWD", "USD"],
                index=0 if cat["default_currency"] == "TWD" else 1,
                key=curr_key,
                on_change=_update_cat_field,
                args=(cid, "default_currency", curr_key),
                label_visibility="collapsed",
            )

            # ----- 有成本(可改) -----
            cost_key = f"cost_{cid}"
            cols[3].checkbox(
                "成本",
                value=cat["has_cost_value"],
                key=cost_key,
                on_change=_update_cat_field,
                args=(cid, "has_cost_value", cost_key),
                label_visibility="collapsed",
            )

            # ----- 順序(可改) -----
            ord_key = f"ord_{cid}"
            cols[4].number_input(
                "順序",
                min_value=0,
                max_value=99,
                value=int(cat["display_order"]),
                step=1,
                key=ord_key,
                on_change=_update_cat_field,
                args=(cid, "display_order", ord_key),
                label_visibility="collapsed",
            )

            # ----- 可見性(三態下拉) -----
            vis_key = f"vis_{cid}"
            current_vis = cat.get("visibility") or (
                "public" if cat.get("is_public", True) else "private"
            )
            if current_vis not in VIS_VALUES:
                current_vis = "public"
            cols[5].selectbox(
                "可見性",
                VIS_VALUES,
                index=VIS_VALUES.index(current_vis),
                format_func=lambda v: VIS_LABELS[v],
                key=vis_key,
                on_change=_update_cat_field,
                args=(cid, "visibility", vis_key),
                label_visibility="collapsed",
            )

            # ----- 刪除(二次確認) -----
            confirm_del_key = f"confirm_del_cat_{cid}"
            if st.session_state.get(confirm_del_key):
                if cols[6].button("✓", key=f"yes_del_{cid}", help="確認刪除", type="primary"):
                    try:
                        get_supabase().table("asset_categories").delete().eq(
                            "id", cid
                        ).execute()
                        st.session_state.pop(confirm_del_key, None)
                        st.toast("已刪除", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"刪除失敗:{e}")
            else:
                if cols[6].button("🗑️", key=f"del_cat_{cid}", help="刪除(連同所有記錄)"):
                    st.session_state[confirm_del_key] = True
                    st.rerun()

            # ----- 分享名單第二行(只在 visibility=shared 顯示) -----
            if current_vis == "shared":
                share_key = f"share_{cid}"
                if not shareable_user_ids:
                    st.caption("⚠️ 還沒有其他使用者註冊,沒人可以選")
                else:
                    sub_cols = st.columns([2, 8, 0.5])
                    sub_cols[0].markdown("&nbsp;&nbsp;&nbsp;└ **分享給**:")
                    sub_cols[1].multiselect(
                        "分享給",
                        options=shareable_user_ids,
                        default=[
                            uid for uid in shares_by_cat.get(cid, [])
                            if uid in shareable_user_ids
                        ],
                        format_func=lambda uid: name_map_mgr.get(uid, uid[:8]),
                        key=share_key,
                        on_change=_update_shares,
                        args=(cid, share_key),
                        label_visibility="collapsed",
                        placeholder="選擇要分享的使用者...",
                    )

    st.markdown("---")

    # 「補建缺漏的預設類別」按鈕(對舊使用者很實用)
    with st.expander("📋 補建預設模板裡缺少的類別", expanded=False):
        st.caption(
            "如果你之前已經建過模板,但預設模板有更新(例如新增了「其他項目」區的"
            "保險現值、現金、悠遊卡、不動產、車輛、應收款),按這個按鈕只會補上"
            "你還沒建過的,不會動到你已有的類別。"
        )
        if st.button("🔍 檢查並補建缺漏"):
            install_missing_defaults()

    st.markdown("---")
    st.subheader("➕ 新增類別")
    with st.form("add_category", clear_on_submit=True):
        cols = st.columns(6)
        section = cols[0].selectbox(
            "分區", SECTION_ORDER, format_func=lambda s: SECTION_NAMES[s]
        )
        name = cols[1].text_input("名稱", placeholder="例如:玉山")
        currency = cols[2].selectbox("預設幣別", ["TWD", "USD"])
        has_cost = cols[3].checkbox("有成本/現值", value=False)
        order = cols[4].number_input("顯示順序", min_value=0, max_value=99, value=99, step=1)
        new_vis = cols[5].selectbox(
            "可見性",
            VIS_VALUES,
            index=1,  # 預設 public
            format_func=lambda v: VIS_LABELS[v],
            help="新增後可在上方清單調整,並設定『指定』模式的分享名單",
        )

        if st.form_submit_button("新增", type="primary"):
            if not name.strip():
                st.error("請填名稱")
            else:
                try:
                    get_supabase().table("asset_categories").insert(
                        {
                            "user_id": me["id"],
                            "section": section,
                            "name": name.strip(),
                            "default_currency": currency,
                            "has_cost_value": has_cost,
                            "display_order": order,
                            "is_active": True,
                            "visibility": new_vis,
                            "is_public": (new_vis == "public"),  # 同步舊欄位
                        }
                    ).execute()
                    if new_vis == "shared":
                        st.success("已新增,記得到上方清單設定分享名單!")
                    else:
                        st.success("已新增")
                    st.rerun()
                except Exception as e:
                    st.error(f"新增失敗:{e}")
