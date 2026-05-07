"""
我的日誌:新增 / 編輯 / 刪除 自己的日誌
"""
import streamlit as st
from datetime import date
from utils import get_supabase, get_current_user, require_login, render_sidebar


st.set_page_config(page_title="我的日誌", page_icon="📔", layout="wide")

require_login()
render_sidebar()
user = get_current_user()

st.title("📔 我的日誌")


# ---------- 處理「編輯模式」 ----------
edit_id = st.session_state.get("editing_journal_id")
existing = None
if edit_id:
    try:
        result = (
            get_supabase()
            .table("journal_entries")
            .select("*")
            .eq("id", edit_id)
            .execute()
        )
        if result.data:
            existing = result.data[0]
            # 確認這篇是不是自己的
            if existing["user_id"] != user["id"]:
                existing = None
                st.session_state.pop("editing_journal_id", None)
    except Exception:
        existing = None


# ---------- 新增 / 編輯 表單 ----------
form_title = "✏️ 編輯日誌" if existing else "➕ 寫一篇日誌"
with st.expander(form_title, expanded=True):
    with st.form("journal_form", clear_on_submit=not existing):
        entry_date = st.date_input(
            "日期",
            value=date.fromisoformat(existing["entry_date"]) if existing else date.today(),
        )
        title = st.text_input(
            "標題(可選)", value=existing["title"] if existing and existing["title"] else ""
        )
        content = st.text_area(
            "內容",
            value=existing["content"] if existing else "",
            height=200,
            placeholder="今天發生了什麼事?",
        )

        col1, col2 = st.columns([1, 5])
        with col1:
            submit = st.form_submit_button(
                "更新" if existing else "新增", type="primary"
            )
        with col2:
            if existing:
                cancel = st.form_submit_button("取消編輯")
                if cancel:
                    st.session_state.pop("editing_journal_id", None)
                    st.rerun()

        if submit:
            if not content.strip():
                st.error("內容不能空白")
            else:
                try:
                    payload = {
                        "user_id": user["id"],
                        "title": title.strip() or None,
                        "content": content.strip(),
                        "entry_date": entry_date.isoformat(),
                    }
                    if existing:
                        get_supabase().table("journal_entries").update(payload).eq(
                            "id", existing["id"]
                        ).execute()
                        st.session_state.pop("editing_journal_id", None)
                        st.success("已更新 ✅")
                    else:
                        get_supabase().table("journal_entries").insert(payload).execute()
                        st.success("已新增 ✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"儲存失敗:{e}")


st.divider()


# ---------- 列表 ----------
st.subheader("我的日誌")

try:
    result = (
        get_supabase()
        .table("journal_entries")
        .select("*")
        .eq("user_id", user["id"])
        .order("entry_date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    entries = result.data or []
except Exception as e:
    st.error(f"讀取失敗:{e}")
    entries = []

if entries:
    for entry in entries:
        title = entry.get("title") or "(無標題)"
        with st.expander(f"📅 **{entry['entry_date']}** — {title}"):
            st.markdown(entry["content"])
            st.markdown("---")
            c1, c2, _ = st.columns([1, 1, 5])
            if c1.button("✏️ 編輯", key=f"edit_{entry['id']}"):
                st.session_state.editing_journal_id = entry["id"]
                st.rerun()
            if c2.button("🗑️ 刪除", key=f"del_journal_{entry['id']}"):
                try:
                    get_supabase().table("journal_entries").delete().eq(
                        "id", entry["id"]
                    ).execute()
                    st.toast("已刪除", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"刪除失敗:{e}")
else:
    st.info("還沒有日誌,寫下第一篇吧!")
