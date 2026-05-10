"""
首頁:登入 / 註冊
登入後會在 session_state 存使用者資訊,然後可以從左側選單進入其他頁面。
有 cookie 持續登入機制,30 天內免再次輸入密碼。
"""
import streamlit as st
from utils import (
    get_supabase,
    get_current_user,
    logout,
    render_sidebar,
    try_auto_login,
    save_session_cookie,
    save_session_to_url,
    get_cookie_manager,
    ensure_url_has_token,
)


st.set_page_config(
    page_title="記帳日誌",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Cookie manager 必須在這裡初始化(讓 component 開始載入)
get_cookie_manager()

# 嘗試從 cookie 自動登入
if not get_current_user():
    auth_result = try_auto_login()
    if auth_result == "success":
        st.rerun()
    elif auth_result == "waiting":
        # cookie 還沒讀回來,顯示載入中,然後自動 rerun 再試一次
        st.info("⏳ 載入中...")
        import time
        time.sleep(0.3)
        st.rerun()

st.title("💰 記帳日誌")

# ---------- 已登入狀態 ----------
if get_current_user():
    # 確保 URL 上有 token(換頁回首頁時可能被清掉)
    ensure_url_has_token()

    user = get_current_user()
    name = user.get("display_name") or user.get("email", "")
    st.success(f"歡迎回來,{name} 👋")

    st.markdown(
        """
        ### 從左側選單進入功能頁:

        - **💰 我的記帳** — 新增、刪除、查看自己的收支記錄
        - **📔 我的日誌** — 寫下今天發生的事
        - **🌐 公開總覽** — 看所有人的記錄
        - **📊 圖表分析** — 收支視覺化圖表
        - **📋 資產模板** — 每月個人總資產追蹤
        """
    )

    if st.button("登出", type="secondary"):
        logout()
        st.rerun()

    render_sidebar()

# ---------- 未登入狀態:登入 / 註冊 ----------
else:
    st.caption("一個小團體共用的記帳 + 日誌系統")

    tab_login, tab_register = st.tabs(["🔑 登入", "📝 註冊"])

    # ===== 登入 =====
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("密碼", type="password")
            submit = st.form_submit_button("登入", type="primary", use_container_width=True)

            if submit:
                if not email or not password:
                    st.error("請輸入 email 和密碼")
                else:
                    try:
                        client = get_supabase()
                        response = client.auth.sign_in_with_password(
                            {"email": email, "password": password}
                        )
                        # 取顯示名稱:metadata 裡有就用,否則用 email 前綴
                        display_name = (
                            (response.user.user_metadata or {}).get("display_name")
                            or email.split("@")[0]
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
                        # 同時存進 URL + cookie,下次重整免登入
                        # URL 是主力(可靠),cookie 是備援
                        save_session_to_url(response.session.refresh_token)
                        save_session_cookie(response.session.refresh_token)
                        st.success("登入成功!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"登入失敗:{e}")

    # ===== 註冊 =====
    with tab_register:
        with st.form("register_form"):
            display_name = st.text_input(
                "顯示名稱",
                help="會出現在公開頁面,可以是中文或英文,例如「小明」",
            )
            email = st.text_input("Email", key="reg_email")
            password = st.text_input(
                "密碼(至少 6 個字元)",
                type="password",
                key="reg_pw",
            )
            submit = st.form_submit_button("註冊", type="primary", use_container_width=True)

            if submit:
                if not all([display_name, email, password]):
                    st.error("請填寫所有欄位")
                elif len(password) < 6:
                    st.error("密碼至少要 6 個字元")
                else:
                    try:
                        client = get_supabase()
                        response = client.auth.sign_up(
                            {
                                "email": email,
                                "password": password,
                                "options": {"data": {"display_name": display_name}},
                            }
                        )
                        if response.user:
                            st.success("註冊成功!請切到「登入」分頁登入。")
                            st.info(
                                "如果 Supabase 開啟了 email 確認,"
                                "請先到信箱點確認連結再登入。"
                                "(可以在 Supabase Dashboard → Authentication → Providers → Email 把 Confirm email 關掉,適合小團體使用)"
                            )
                    except Exception as e:
                        st.error(f"註冊失敗:{e}")
