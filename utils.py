"""
共用工具:Supabase 連線、登入狀態管理、權限檢查、Cookie 持續登入
所有 page 都會 import 這裡的東西
"""
from datetime import datetime, timedelta
import streamlit as st
from supabase import create_client, Client
import extra_streamlit_components as stx


COOKIE_NAME = "sl_refresh"  # sl = sharedlife
COOKIE_DAYS = 30


def get_cookie_manager():
    """
    取得 CookieManager。整個 App 一個就好,但每次 rerun 都重新 fetch cookie。
    用 session_state 而不是 @st.cache_resource(會踩 cached widget 限制)。
    """
    if "_cookie_manager_instance" not in st.session_state:
        st.session_state._cookie_manager_instance = stx.CookieManager(key="sl_cookie_mgr")
    return st.session_state._cookie_manager_instance


def _read_cookie_value(name: str):
    """直接拿單一 cookie 的值,如果還沒 ready 回傳 None。"""
    try:
        return get_cookie_manager().get(name)
    except Exception:
        return None


def save_session_cookie(refresh_token: str):
    """把 refresh token 存到瀏覽器 cookie,30 天內免登入。"""
    if not refresh_token:
        return
    try:
        get_cookie_manager().set(
            COOKIE_NAME,
            refresh_token,
            expires_at=datetime.now() + timedelta(days=COOKIE_DAYS),
            key=f"set_cookie_{datetime.now().timestamp()}",
        )
    except Exception:
        pass


def clear_session_cookie():
    """清除登入 cookie。"""
    try:
        get_cookie_manager().delete(
            COOKIE_NAME,
            key=f"del_cookie_{datetime.now().timestamp()}",
        )
    except Exception:
        pass


def try_auto_login() -> str:
    """
    用 cookie 中的 refresh_token 嘗試自動登入。

    回傳值:
      "logged_in" - 已經登入,不用處理
      "success"   - 自動登入成功(呼叫端應 st.rerun())
      "no_cookie" - 沒有保存的 session 或無效,顯示登入頁
      "waiting"   - cookie 還沒從瀏覽器讀回來,呼叫端應顯示「載入中」或等下一個 rerun
    """
    if get_current_user():
        return "logged_in"

    # 第一次進頁面時 CookieManager 才剛被初始化,瀏覽器 cookie 可能還沒回來。
    # 這時 cookies dict 會是空的 — 但使用者「看起來」就是沒 cookie,跟「真的沒登入過」一樣。
    # 解法:如果是這個 session 第一次嘗試 + cookies 空,先標記、rerun 一次給 cookie 時間到貨。
    cm = get_cookie_manager()
    try:
        cookies = cm.get_all() or {}
    except Exception:
        cookies = {}

    refresh_token = cookies.get(COOKIE_NAME)

    # 還沒拿到任何 cookie:可能是 (a) 還沒從瀏覽器收到,(b) 真的沒登入過
    # 如果這個 session 還沒重試過,給它一次重試的機會
    if not cookies and not st.session_state.get("_cookie_retry_done"):
        st.session_state._cookie_retry_done = True
        return "waiting"

    if not refresh_token:
        return "no_cookie"

    # 真的有 token 了,試著用它登入
    try:
        client = get_supabase()
        response = client.auth.refresh_session(refresh_token)
        if response and response.user and response.session:
            display_name = (
                (response.user.user_metadata or {}).get("display_name")
                or (response.user.email or "").split("@")[0]
            )
            st.session_state.user = {
                "id": response.user.id,
                "email": response.user.email,
                "display_name": display_name,
            }
            st.session_state.auth_session = {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
            }
            # 更新 cookie(refresh_token 可能被輪替了)
            save_session_cookie(response.session.refresh_token)
            return "success"
    except Exception:
        # token 過期或無效,清掉 cookie
        clear_session_cookie()

    return "no_cookie"


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
    """放在每個受保護頁面的最上面。沒登入時先試 cookie,失敗才提示登入。"""
    if get_current_user():
        return

    # 沒登入,先試 cookie 自動登入
    get_cookie_manager()  # 確保 cookie manager 啟動
    auth_result = try_auto_login()

    if auth_result == "success":
        st.rerun()
    elif auth_result == "waiting":
        st.info("⏳ 載入中...")
        import time
        time.sleep(0.3)
        st.rerun()
    else:
        # no_cookie:真的沒登入,提示去首頁
        st.warning("⚠️ 請先到首頁登入")
        st.page_link("app.py", label="← 回到登入頁", icon="🔑")
        st.stop()


def logout():
    """登出並清掉 session_state + cookie。"""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    clear_session_cookie()
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
