"""
共用工具:Supabase 連線、登入狀態管理、權限檢查、持續登入
所有 page 都會 import 這裡的東西
"""
from datetime import datetime, timedelta
import streamlit as st
from supabase import create_client, Client
import extra_streamlit_components as stx


COOKIE_NAME = "sl_refresh"  # sl = sharedlife
COOKIE_DAYS = 30
URL_TOKEN_PARAM = "sl"  # URL query param key for refresh token


# =====================================================================
# URL query param 持久化(主力)
# query param 是 URL 的一部分,瀏覽器重整時 100% 會帶過來,沒有時序問題。
# 缺點:URL 會有一段長 token,但對 2-3 人小團體可接受。
# 重要:Supabase 預設啟用 refresh token rotation,每次 refresh 會輪替 token,
# 即便 URL 被人看到,他用一次就被 rotate 掉,原使用者仍能正常 refresh。
# =====================================================================

def save_session_to_url(refresh_token: str):
    """把 refresh token 存進 URL query param。"""
    if refresh_token:
        try:
            st.query_params[URL_TOKEN_PARAM] = refresh_token
        except Exception:
            pass


def get_session_from_url():
    """從 URL query param 讀 refresh token。重整時最可靠。"""
    try:
        return st.query_params.get(URL_TOKEN_PARAM)
    except Exception:
        return None


def clear_session_from_url():
    """登出時清掉 URL 上的 token。"""
    try:
        if URL_TOKEN_PARAM in st.query_params:
            del st.query_params[URL_TOKEN_PARAM]
    except Exception:
        pass


# =====================================================================
# Cookie 持久化(備援,以防 URL 被清掉)
# =====================================================================

def get_cookie_manager():
    """
    取得 CookieManager。整個 App 一個就好。
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
    用 URL query param + cookie 中的 refresh_token 嘗試自動登入。
    優先順序:URL(最可靠)→ cookie(備援)

    回傳值:
      "logged_in" - 已經登入,不用處理
      "success"   - 自動登入成功(呼叫端應 st.rerun())
      "no_cookie" - 沒有保存的 session 或無效,顯示登入頁
      "waiting"   - cookie 還沒從瀏覽器讀回來,呼叫端應顯示「載入中」或等下一個 rerun
    """
    if get_current_user():
        return "logged_in"

    # ===== 第一優先:URL query param =====
    # URL 是 request 的一部分,瀏覽器重整時 100% 帶過來,沒有時序問題
    refresh_token = get_session_from_url()
    source = "url" if refresh_token else None

    # ===== 第二優先:cookie 備援 =====
    if not refresh_token:
        cm = get_cookie_manager()
        try:
            cookies = cm.get_all() or {}
        except Exception:
            cookies = {}

        refresh_token = cookies.get(COOKIE_NAME)
        if refresh_token:
            source = "cookie"
        else:
            # cookie 還沒到貨?給 1 次重試機會
            if not cookies and not st.session_state.get("_cookie_retry_done"):
                st.session_state._cookie_retry_done = True
                return "waiting"

    if not refresh_token:
        return "no_cookie"

    # ===== 真的有 token 了,用它登入 =====
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
            # 同時更新 URL + cookie(refresh_token rotation 了,舊的會失效)
            new_token = response.session.refresh_token
            save_session_to_url(new_token)
            save_session_cookie(new_token)
            return "success"
    except Exception:
        # token 過期或無效,兩邊都清
        clear_session_cookie()
        clear_session_from_url()

    return "no_cookie"


def get_supabase() -> Client:
    """
    取得這個 session 專屬的 Supabase client。
    每個瀏覽器 session 一個 client,登入狀態彼此獨立。

    重點:確保在回傳前 client 的 auth 已經設好,避免「first query 沒帶 JWT
    導致 RLS 過濾掉所有資料」造成的「管理類別空白」現象。
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

    # 確保 auth 已套到 client 上(每次都檢查,而不是只在 token 變動時)
    auth = st.session_state.get("auth_session")
    if auth:
        try:
            current = client.auth.get_session()
            need_set = (
                current is None
                or current.access_token != auth["access_token"]
            )
            if need_set:
                client.auth.set_session(auth["access_token"], auth["refresh_token"])
                # 標記 client 已套 auth 過,讓後續呼叫者可以信任
                st.session_state._auth_applied = True
        except Exception:
            # 如果 set 失敗,也不要 silent 跳過,標記一下
            st.session_state._auth_applied = False

    return client


def is_auth_ready() -> bool:
    """檢查 supabase client 是否已套上 auth(用於除錯/防禦)。"""
    return bool(st.session_state.get("_auth_applied"))


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
    """登出並清掉 session_state + cookie + URL token。"""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    clear_session_cookie()
    clear_session_from_url()
    for key in ("user", "auth_session", "_user_names_cache", "_cookie_retry_done"):
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
