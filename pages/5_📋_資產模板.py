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


def to_twd(amount, currency, rate):
    """把任意幣別轉成 TWD。"""
    if amount is None:
        return 0.0
    if currency == "USD":
        return float(amount) * float(rate or 0)
    return float(amount)


# ====== 四個 Tab ======
tab_monthly, tab_chart, tab_combined, tab_manage = st.tabs(
    ["📅 本月資產", "📈 資產走勢", "🤝 共同資產", "⚙️ 管理類別"]
)


# =====================================================================
#  Tab 1:本月資產
# =====================================================================
with tab_monthly:
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
        st.stop()

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
                    min_value=0.0,
                    step=100.0,
                    value=default_cost,
                    key=f"{base_key}_cost",
                    label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
                )
                current_value = cols[3].number_input(
                    "現值",
                    min_value=0.0,
                    step=100.0,
                    value=default_value,
                    key=f"{base_key}_value",
                    label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
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
                cols[5].markdown(
                    f"NT${value_twd:,.0f}<br>"
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
                    min_value=0.0,
                    step=100.0,
                    value=default_value,
                    key=f"{base_key}_value",
                    label_visibility="visible" if cat == cats_in_section[0] else "collapsed",
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


# =====================================================================
#  Tab 2:資產走勢
# =====================================================================
with tab_chart:
    name_map = user_id_to_name_map()
    all_users = get_all_users()
    name_to_id = {(u["display_name"] or u["id"][:8]): u["id"] for u in all_users}

    c1, c2 = st.columns([1, 2])
    with c1:
        view_options = ["我自己", "所有人"] + list(name_to_id.keys())
        view_user = st.selectbox("看誰的資產", view_options, key="chart_user")

    # 取資料
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
        st.stop()

    # 整理 dataframe
    df = pd.DataFrame(records)
    df["年月"] = df.apply(lambda r: f"{r['year']:04d}-{r['month']:02d}", axis=1)
    df["TWD"] = df.apply(
        lambda r: to_twd(r["current_value"], r["currency"], r["exchange_rate"]),
        axis=1,
    )
    df["section"] = df["asset_categories"].apply(lambda c: c["section"] if c else "other")
    df["section_name"] = df["section"].map(SECTION_NAMES)

    # ---------- 總資產走勢線圖 ----------
    st.subheader("💎 總資產走勢")
    if view_user == "所有人":
        # 用 user 分組
        df["使用者"] = df["user_id"].map(lambda x: name_map.get(x, x[:8]))
        total_by_month = (
            df.groupby(["年月", "使用者"])["TWD"].sum().reset_index()
        )
        fig = px.line(
            total_by_month, x="年月", y="TWD", color="使用者", markers=True
        )
    else:
        total_by_month = df.groupby("年月")["TWD"].sum().reset_index()
        fig = px.line(total_by_month, x="年月", y="TWD", markers=True)
        fig.update_traces(line_color="#3b82f6")
    fig.update_layout(height=400, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # ---------- 分區堆疊面積圖 ----------
    st.subheader("📊 資產組成(依分區)")
    if view_user != "所有人":
        section_by_month = (
            df.groupby(["年月", "section_name"])["TWD"].sum().reset_index()
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
        fig2.update_layout(height=400, hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.caption("(看「所有人」時不顯示分區圖,請選特定使用者)")

    # ---------- 投資帳戶損益走勢 ----------
    inv_df = df[df["section"] == "investment"].copy()
    if not inv_df.empty and view_user != "所有人":
        inv_df["cost_twd"] = inv_df.apply(
            lambda r: to_twd(r.get("cost") or 0, r["currency"], r["exchange_rate"]),
            axis=1,
        )
        inv_df["損益"] = inv_df["TWD"] - inv_df["cost_twd"]
        pnl_by_month = inv_df.groupby("年月")[["TWD", "cost_twd", "損益"]].sum().reset_index()
        st.subheader("📈 投資損益走勢")
        fig3 = go.Figure()
        fig3.add_trace(
            go.Bar(
                x=pnl_by_month["年月"],
                y=pnl_by_month["損益"],
                name="損益",
                marker_color=[
                    "#10b981" if v >= 0 else "#ef4444" for v in pnl_by_month["損益"]
                ],
            )
        )
        fig3.update_layout(height=350, hovermode="x unified")
        st.plotly_chart(fig3, use_container_width=True)

    # ---------- 最新一筆明細 ----------
    if view_user != "所有人":
        latest_ym = df["年月"].max()
        st.subheader(f"📋 {latest_ym} 明細")
        latest_df = df[df["年月"] == latest_ym].copy()
        latest_df["類別"] = latest_df["asset_categories"].apply(
            lambda c: c["name"] if c else "?"
        )
        show_df = latest_df[["section_name", "類別", "currency", "current_value", "exchange_rate", "TWD"]].rename(
            columns={
                "section_name": "分區",
                "currency": "幣別",
                "current_value": "原幣金額",
                "exchange_rate": "匯率",
                "TWD": "台幣金額",
            }
        )
        st.dataframe(show_df, use_container_width=True, hide_index=True)


# =====================================================================
#  Tab 3:共同資產
# =====================================================================
with tab_combined:
    st.caption(
        "把幾個人的公開資產合在一起算總額,適合追蹤家庭/伴侶/合夥的共同資產。"
        "私人類別不會出現在這裡。"
    )

    name_map_c = user_id_to_name_map()
    all_users_c = get_all_users()

    # ---------- 1. 選擇要納入的使用者 ----------
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
        st.stop()

    # ---------- 2. 月份 ----------
    today_c = date.today()
    cy, cm = st.columns(2)
    with cy:
        c_year = st.selectbox(
            "年份",
            list(range(today_c.year - 5, today_c.year + 2)),
            index=5,
            key="combined_year",
        )
    with cm:
        c_month = st.selectbox(
            "月份",
            list(range(1, 13)),
            index=today_c.month - 1,
            format_func=lambda m: f"{m:02d} 月",
            key="combined_month",
        )

    # ---------- 3. 取出對選擇者可見的所有類別 ----------
    # RLS 會自動過濾(只回傳自己的 + 別人公開的)
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
        st.stop()

    # ---------- 4. 多選要納入的類別(預設全選) ----------
    cat_label_map = {}
    for cat in visible_cats:
        owner = name_map_c.get(cat["user_id"], cat["user_id"][:8])
        privacy = "🔒" if not cat.get("is_public", True) else ""
        label = f"{owner}・{SECTION_ICONS[cat['section']]} {cat['name']} {privacy}".strip()
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
        st.stop()

    # ---------- 5. 取出該月份的記錄 ----------
    try:
        ma_q = (
            get_supabase()
            .table("monthly_assets")
            .select("*, asset_categories(name, section, has_cost_value)")
            .in_("user_id", selected_user_ids)
            .in_("category_id", selected_cat_ids)
            .eq("year", c_year)
            .eq("month", c_month)
            .execute()
        )
        ma_records = ma_q.data or []
    except Exception as e:
        st.error(f"讀取資產失敗:{e}")
        ma_records = []

    if not ma_records:
        st.warning(f"{c_year}/{c_month:02d} 這幾位使用者還沒輸入資料")
        st.stop()

    # ---------- 6. 整理 + 顯示 ----------
    df = pd.DataFrame(ma_records)
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

    # 大標總額
    grand_combined = df["TWD"].sum()
    total_cost = df["cost_TWD"].sum()
    st.markdown("### 💎 共同總資產")
    cols = st.columns(3)
    cols[0].metric(f"{c_year}/{c_month:02d} 總額", f"NT$ {grand_combined:,.0f}")
    if total_cost > 0:
        cols[1].metric("投資成本合計", f"NT$ {total_cost:,.0f}")
        pnl = df["TWD"].where(df["cost_TWD"] > 0, 0).sum() - total_cost
        cols[2].metric(
            "投資未實現損益",
            f"NT$ {pnl:+,.0f}",
            delta=f"{pnl/total_cost*100:+.1f}%" if total_cost > 0 else None,
        )

    st.divider()

    # 各人小計
    st.markdown("### 👥 各人小計")
    per_user = df.groupby("使用者")["TWD"].sum().reset_index().sort_values("TWD", ascending=False)
    user_cols = st.columns(len(per_user))
    for i, (_, row) in enumerate(per_user.iterrows()):
        pct = row["TWD"] / grand_combined * 100 if grand_combined > 0 else 0
        user_cols[i].metric(
            row["使用者"],
            f"NT$ {row['TWD']:,.0f}",
            delta=f"{pct:.0f}%",
            delta_color="off",
        )

    # 兩個圖排在一起
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("### 📊 依分區")
        per_section = df.groupby("分區名")["TWD"].sum().reset_index()
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
        fig_sec.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig_sec, use_container_width=True)

    with chart_col2:
        st.markdown("### 👥 各人占比")
        fig_user = px.pie(per_user, values="TWD", names="使用者", hole=0.4)
        fig_user.update_traces(textposition="inside", textinfo="percent+label")
        fig_user.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig_user, use_container_width=True)

    # 細項
    st.markdown("### 📋 細項")
    detail = (
        df[["使用者", "分區名", "類別", "currency", "current_value", "exchange_rate", "TWD"]]
        .copy()
        .rename(
            columns={
                "分區名": "分區",
                "currency": "幣別",
                "current_value": "原幣金額",
                "exchange_rate": "匯率",
                "TWD": "台幣金額",
            }
        )
        .sort_values(["使用者", "分區", "類別"])
    )
    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True,
        column_config={
            "原幣金額": st.column_config.NumberColumn(format="%.2f"),
            "匯率": st.column_config.NumberColumn(format="%.2f"),
            "台幣金額": st.column_config.NumberColumn(format="%d"),
        },
    )

    # ---------- 7. 共同走勢圖(歷月) ----------
    st.divider()
    st.markdown("### 📈 共同資產走勢")

    try:
        all_ma_q = (
            get_supabase()
            .table("monthly_assets")
            .select("year, month, user_id, currency, exchange_rate, current_value")
            .in_("user_id", selected_user_ids)
            .in_("category_id", selected_cat_ids)
            .order("year")
            .order("month")
            .execute()
        )
        history = all_ma_q.data or []
    except Exception as e:
        st.error(f"讀取走勢失敗:{e}")
        history = []

    if history:
        hdf = pd.DataFrame(history)
        hdf["TWD"] = hdf.apply(
            lambda r: to_twd(r["current_value"], r["currency"], r["exchange_rate"]),
            axis=1,
        )
        hdf["年月"] = hdf.apply(
            lambda r: f"{r['year']:04d}-{r['month']:02d}", axis=1
        )
        hdf["使用者"] = hdf["user_id"].map(lambda x: name_map_c.get(x, x[:8]))

        # 整體合計線
        total_line = hdf.groupby("年月")["TWD"].sum().reset_index()
        # 各人線
        per_user_line = (
            hdf.groupby(["年月", "使用者"])["TWD"].sum().reset_index()
        )

        fig_trend = go.Figure()
        # 各人(較淡)
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
        # 合計(粗線)
        fig_trend.add_trace(
            go.Scatter(
                x=total_line["年月"],
                y=total_line["TWD"],
                mode="lines+markers",
                name="共同合計",
                line=dict(width=4, color="#3b82f6"),
            )
        )
        fig_trend.update_layout(height=400, hovermode="x unified")
        st.plotly_chart(fig_trend, use_container_width=True)


# =====================================================================
#  Tab 4:管理類別
# =====================================================================
with tab_manage:
    st.subheader("我的類別清單")
    st.caption(
        "🔒 私人 = 只有自己看得到 / 🌐 公開 = 朋友也能在『共同資產』和『資產走勢』看到"
    )
    categories = get_my_categories()

    if not categories:
        st.info("還沒有任何類別")
        if st.button("📋 一鍵建立預設模板", type="primary"):
            install_default_template()
    else:
        # 表頭
        h = st.columns([1, 1.6, 0.8, 0.8, 0.7, 1, 0.6])
        h[0].markdown("**分區**")
        h[1].markdown("**名稱**")
        h[2].markdown("**幣別**")
        h[3].markdown("**有成本**")
        h[4].markdown("**順序**")
        h[5].markdown("**公開**")
        h[6].markdown("")

        for cat in categories:
            cols = st.columns([1, 1.6, 0.8, 0.8, 0.7, 1, 0.6])
            cols[0].text(SECTION_ICONS[cat["section"]] + " " + SECTION_NAMES[cat["section"]])
            cols[1].text(cat["name"])
            cols[2].text(cat["default_currency"])
            cols[3].text("✓" if cat["has_cost_value"] else "—")
            cols[4].text(str(cat["display_order"]))

            # 公開/私人 toggle
            toggle_key = f"pub_{cat['id']}"

            def _on_pub_change(cat_id=cat["id"], key=toggle_key):
                new_val = st.session_state[key]
                try:
                    get_supabase().table("asset_categories").update(
                        {"is_public": new_val}
                    ).eq("id", cat_id).execute()
                    st.toast(
                        f"已改為{'🌐 公開' if new_val else '🔒 私人'}",
                        icon="✅",
                    )
                except Exception as e:
                    st.error(f"更新失敗:{e}")

            cols[5].toggle(
                "公開",
                value=cat.get("is_public", True),
                key=toggle_key,
                on_change=_on_pub_change,
                label_visibility="collapsed",
            )

            if cols[6].button("🗑️", key=f"del_cat_{cat['id']}", help="刪除(連同記錄)"):
                try:
                    get_supabase().table("asset_categories").delete().eq(
                        "id", cat["id"]
                    ).execute()
                    st.toast("已刪除", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"刪除失敗:{e}")

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
        is_pub = cols[5].checkbox("公開", value=True, help="關掉變私人(只有自己看得到)")

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
                            "is_public": is_pub,
                        }
                    ).execute()
                    st.success("已新增")
                    st.rerun()
                except Exception as e:
                    st.error(f"新增失敗:{e}")
