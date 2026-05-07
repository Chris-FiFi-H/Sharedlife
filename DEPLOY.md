# 📦 Sharedlife 完整最新版部署說明

這份是從 v1 到目前所有功能的最終版本(包含 v2 + v3 + cookie hotfix + CSV 匯入匯出)。

## 包含什麼

```
Sharedlife/
├── .gitignore
├── README.md
├── app.py                                   ← 登入頁 + 自動登入
├── utils.py                                 ← 含 cookie 持續登入(已修 hotfix)
├── requirements.txt                         ← 含 extra-streamlit-components
├── supabase_schema.sql                      ← 第一版資料庫(transactions / journal)
├── supabase_schema_v2.sql                   ← 資產模板表
├── supabase_schema_v3.sql                   ← 公開/私人 + RLS
├── supabase_schema_ALL.sql                  ← 三個合併,新環境一次跑用
├── .streamlit/
│   └── secrets.toml.example                 ← 範本(secrets.toml 你自己填,不要 commit)
└── pages/
    ├── 1_💰_我的記帳.py
    ├── 2_📔_我的日誌.py
    ├── 3_🌐_公開總覽.py
    ├── 4_📊_圖表分析.py
    └── 5_📋_資產模板.py                     ← 含 CSV 匯入匯出、刪除月份等
```

---

## 情境 A:你的 C:\git\Sharedlife 已經有舊版本(local clone),要更新

最常見情境。你已經有 `C:\git\Sharedlife`,想用最新檔案蓋掉。

```cmd
:: 先備份保險(可選)
xcopy C:\git\Sharedlife C:\git\Sharedlife_backup\ /E /I

:: 下載這份 zip 解壓到 C:\git,會出現 C:\git\Sharedlife_new\ 之類
:: 把新版檔案複製進你的 git repo(會覆蓋同名檔)
xcopy C:\git\Sharedlife_new\Sharedlife\* C:\git\Sharedlife\ /E /Y

:: 進到 repo
cd C:\git\Sharedlife

:: 確認狀態
git status
```

如果 `git status` 顯示一堆 modified,正常 — 那就是這次的更新。

接下來開新 branch、commit、push:

```cmd
git checkout -b feature/full-update
git add -A
git commit -m "feat: cookie hotfix + 資產模板 CSV 匯入匯出"
git push -u origin feature/full-update
```

開 GitHub PR、Merge。Streamlit Cloud 會自動部署。

---

## 情境 B:C:\git 是空的,從零開始

```cmd
cd C:\git

:: 直接 git clone 一份(GitHub 上的版本是 master,可能還沒這次的更新)
git clone https://github.com/Chris-FiFi-H/Sharedlife.git
cd Sharedlife
```

然後**把這個 zip 解壓到 C:\git**,你會多一個資料夾(假設叫 `Sharedlife_new`),從那邊複製檔案進去:

```cmd
xcopy C:\git\Sharedlife_new\Sharedlife\* C:\git\Sharedlife\ /E /Y

git status
git checkout -b feature/full-update
git add -A
git commit -m "feat: cookie hotfix + 資產模板 CSV 匯入匯出"
git push -u origin feature/full-update
```

---

## 情境 C:不想跟 git 玩,直接用 GitHub 網頁

下載 zip,解壓後一個一個檔案上傳到 GitHub:

1. 進 https://github.com/Chris-FiFi-H/Sharedlife
2. 上方 branch dropdown → 輸入 `feature/full-update` → Create
3. 在這個分支上,逐一替換有變動的檔案:
   - `utils.py`(cookie hotfix 改的)
   - `pages/5_📋_資產模板.py`(CSV 功能改的)
4. 開 Compare & pull request → Merge

**這次沒有新 SQL 要跑**(SQL 你之前 v2 + v3 已經跑過)。

---

## Streamlit secrets 不會在 zip 裡(故意的)

打開 `.streamlit/secrets.toml.example`,複製成 `secrets.toml` 並填上:

```toml
SUPABASE_URL = "https://你的專案.supabase.co"
SUPABASE_ANON_KEY = "eyJhbG..."
```

> ⚠️ `secrets.toml` 已經在 `.gitignore` 裡,**不會被 git push 上去**(避免外洩)。
>
> Streamlit Cloud 上的 secrets 也是另外設定 — Manage app → Settings → Secrets,跟本地的 `secrets.toml` 沒關係。已經設過就不用再設。

---

## 本地測試(可選)

更新後想在電腦上跑跑看:

```cmd
cd C:\git\Sharedlife

:: 第一次用先建虛擬環境
python -m venv venv
venv\Scripts\activate

:: 裝套件(這次有新加 extra-streamlit-components,記得跑)
pip install -r requirements.txt

:: 跑起來
streamlit run app.py
```

瀏覽器自動開 `http://localhost:8501`。
