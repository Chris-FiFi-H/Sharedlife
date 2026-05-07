"""
共用工具:Supabase 連線、登入狀態管理、權限檢查
所有 page 都會 import 這裡的東西
"""
import streamlit as st
from supabase import create_client, Client


def get_supabase() -> Client:
    """
    取得這個 session 專屬的 Supabase client。
    每個瀏覽器 session 一個 client,登入狀態彼此獨立。
    """
    if "supabase_client" not in st.session_state:
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_ANON_KEY"]
        except (KeyError, FileNotFoundError):
            st.error(
                "❌ 找不到 Supabase 設定\n\n"
                "請複製 `.streamlit/secrets.toml.example` 為 `.streamlit/secrets.toml`,"
                "並填入你的 SUPABASE_URL 與 SUPABASE_ANON_KEY。"
            )
            st.stop()
        st.session_state.supabase_client = create_client(url, key)

    client = st.session_state.supabase_client

    # 如果 session_state 裡有 token 但 client 還沒套用,把它套上去
    auth = st.session_state.get("auth_session")
    if auth:
        try:
            current = client.auth.get_session()
            if current is None or current.access_token != auth["access_token"]:
                client.auth.set_session(auth["access_token"], auth["refresh_token"])
        except Exception:
            pass

    return client


def get_current_user():
    """傳回目前登入使用者的 dict,沒登入則為 None。"""
    return st.session_state.get("user")


def require_login():
    """放在每個受保護頁面的最上面。沒登入就停在這裡。"""
    if not get_current_user():
        st.warning("⚠️ 請先到首頁登入")
        st.page_link("app.py", label="← 回到登入頁", icon="🔑")
        st.stop()


def logout():
    """登出並清掉 session_state 裡所有相關欄位。"""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for key in ("user", "auth_session", "_user_names_cache"):
        st.session_state.pop(key, None)


def get_all_users():
    """取得所有使用者(id + display_name)。"""
    try:
        result = get_supabase().table("profiles").select("id, display_name").execute()
        return result.data or []
    except Exception as e:
        st.error(f"無法取得使用者列表:{e}")
        return []


def user_id_to_name_map():
    """user_id → display_name 的 dict,方便查名字。"""
    return {u["id"]: (u["display_name"] or u["id"][:8]) for u in get_all_users()}


def render_sidebar():
    """側邊欄顯示登入者名稱與登出按鈕,所有頁面共用。"""
    user = get_current_user()
    if not user:
        return
    with st.sidebar:
        st.markdown("---")
        name = user.get("display_name") or user.get("email", "")
        st.markdown(f"👤 **{name}**")
        if st.button("登出", use_container_width=True):
            logout()
            st.switch_page("app.py")
