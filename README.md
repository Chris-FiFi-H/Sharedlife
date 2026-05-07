# 💰 記帳日誌

一個給 2-3 人小團體用的記帳 + 日誌共用 Web App。

**功能**
- 多使用者註冊/登入
- 個人記帳(收入/支出、分類、備註、日期)
- 個人日誌(編輯、刪除)
- 公開頁面看所有人的記錄(可依使用者篩選)
- 圖表分析(時間趨勢、月度比較、分類圓餅、累計結餘、使用者比較)
- 手機版自動適配

**技術組合**
- Python + [Streamlit](https://streamlit.io/)(前端 + 後端邏輯一份檔案搞定)
- [Supabase](https://supabase.com/)(資料庫 + 登入系統)
- [Plotly](https://plotly.com/python/)(互動式圖表)
- 部署平台:[Streamlit Community Cloud](https://share.streamlit.io/) — 全部免費

---

## 一、設定 Supabase(約 10 分鐘)

### 1. 建立 Supabase 專案

1. 到 https://supabase.com/ 註冊(用 GitHub 帳號最快)
2. 點 **"New project"**
3. 填:
   - Project name:隨便取,例如 `accounting-journal`
   - Database password:**點「Generate a password」並把它存起來**(這份不是給 App 用的,但忘了會麻煩)
   - Region:選 **Northeast Asia (Tokyo / Singapore)** 對台灣最快
4. 等大約 1-2 分鐘建立完成

### 2. 建立資料表

1. 在左側選單點 **SQL Editor**(那個 `</>` 圖示)
2. 點 **"New query"**
3. 把整份 `supabase_schema.sql` 的內容複製貼上
4. 右下角點 **"Run"**(或 Ctrl+Enter)
5. 看到下面顯示「Success」就成功了

### 3. 關掉 email 確認(2-3 人小團體建議關)

預設情況下,註冊後 Supabase 會寄確認信,點了才能登入。對小團體來說太麻煩,可以關掉:

1. 左側選單 → **Authentication** → **Providers**
2. 找到 **Email**,點開
3. 把 **"Confirm email"** 切到關閉
4. 點 **Save**

> 之後就可以註冊完直接登入。

### 4. 取得 API 金鑰

1. 左側選單最下面 → **Project Settings** → **API Keys**
2. 你會看到兩個東西需要記下來:
   - **Project URL**:類似 `https://abcdefgh.supabase.co`
   - **anon public** key:很長一串以 `eyJ...` 開頭的字串

> ⚠️ **不要用 service_role key**,那個有完整權限,用了就等於把資料庫全開。一律用 **anon** key。

---

## 二、本地測試(約 5 分鐘)

### 1. 安裝 Python(如果還沒裝)

下載 Python 3.9 或更新版本:https://www.python.org/downloads/

> Windows 安裝時記得勾「Add Python to PATH」

開終端機(Windows 按 `Win+R` 輸入 `cmd`;Mac 開「終端機」),確認:

```bash
python --version
# 應該看到 Python 3.9 以上
```

### 2. 進入專案資料夾、建立虛擬環境

```bash
cd accounting_journal_app

# 建虛擬環境(就是一個獨立的 Python 環境,不會弄髒你電腦的全域環境)
python -m venv venv

# 啟動虛擬環境
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

啟動後你的命令列前面會出現 `(venv)` 字樣。

### 3. 安裝套件

```bash
pip install -r requirements.txt
```

第一次會跑個一兩分鐘,下載 Streamlit、Supabase 等套件。

### 4. 設定 Supabase 金鑰

把 `.streamlit/secrets.toml.example` 複製成 `.streamlit/secrets.toml`:

```bash
# Mac/Linux:
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Windows (PowerShell):
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

打開 `.streamlit/secrets.toml`,填入剛剛從 Supabase 拿到的 URL 和 anon key:

```toml
SUPABASE_URL = "https://abcdefgh.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGc..."
```

### 5. 跑起來

```bash
streamlit run app.py
```

瀏覽器會自動開 `http://localhost:8501`,看到登入頁就成功了!

第一次先點「註冊」建一個帳號,然後登入就可以開始用。

---

## 三、部署到 Streamlit Cloud(免費,約 5 分鐘)

讓你跟朋友從手機就能用。

### 1. 推到 GitHub

如果還沒裝 Git:https://git-scm.com/downloads

```bash
# 在專案資料夾內
git init
git add .
git commit -m "first commit"
```

到 https://github.com 建一個新 repo(可以選 private,不會被別人看到),按照頁面指示推上去:

```bash
git remote add origin https://github.com/你的帳號/repo名字.git
git branch -M main
git push -u origin main
```

> ✅ `secrets.toml` 已經被 `.gitignore` 擋掉,不會被推上去。

### 2. 部署

1. 到 https://share.streamlit.io/
2. 用 GitHub 帳號登入
3. 點 **"New app"**
4. 選你剛剛推的 repo
5. **Main file path** 填 `app.py`
6. 點 **"Advanced settings"**,在 **Secrets** 欄位貼上:

   ```toml
   SUPABASE_URL = "https://abcdefgh.supabase.co"
   SUPABASE_ANON_KEY = "eyJhbGc..."
   ```

7. 點 **"Deploy"**

等個 1-3 分鐘,你會拿到一個網址像 `https://你的-app-名.streamlit.app`,把它傳給你的 2-3 個朋友就能一起用了。

手機開這網址就能用,加到主畫面變成 PWA 體驗也行。

---

## 四、檔案結構說明

```
accounting_journal_app/
├── app.py                        ← 入口檔(登入/註冊)
├── utils.py                      ← 共用函式(Supabase 連線、登入檢查)
├── pages/                        ← Streamlit 自動把這裡的檔案變成左側選單
│   ├── 1_💰_我的記帳.py
│   ├── 2_📔_我的日誌.py
│   ├── 3_🌐_公開總覽.py
│   └── 4_📊_圖表分析.py
├── .streamlit/
│   ├── secrets.toml.example      ← 設定範本
│   └── secrets.toml              ← 你自己的設定(.gitignore 會擋)
├── supabase_schema.sql           ← 資料庫建表 SQL
├── requirements.txt              ← Python 套件清單
├── .gitignore
└── README.md
```

---

## 五、想自己改怎麼做?

幾個常見的客製化:

### 改分類項目
打開 `pages/1_💰_我的記帳.py`,改最上面這兩個 list:

```python
CATEGORIES_EXPENSE = ["飲食", "交通", "娛樂", ...]   # 改這裡
CATEGORIES_INCOME = ["薪水", "獎金", ...]            # 跟這裡
```

### 加新欄位(例如「付款方式」)
1. 到 Supabase SQL Editor 執行:
   ```sql
   alter table transactions add column payment_method text;
   ```
2. 在 `pages/1_💰_我的記帳.py` 的新增表單加一個 `st.selectbox`
3. 在 insert 時把它放進去

### 加新頁面
在 `pages/` 資料夾新增一個檔案,命名格式 `<數字>_<emoji>_<頁面名>.py`,Streamlit 會自動偵測加到左側選單。

---

## 六、常見問題

**Q:登入時跳「Email not confirmed」**
A:Supabase Dashboard → Authentication → Providers → Email,把 **Confirm email** 關掉。

**Q:註冊後在公開頁看不到自己的名字**
A:檢查 `supabase_schema.sql` 是不是有完整跑成功(尤其是最後的 trigger)。可以到 Supabase → Table Editor → profiles 看你的帳號有沒有出現。

**Q:Streamlit Cloud 上跑不起來**
A:檢查兩件事 ——(1) Secrets 有沒有貼對 (2) `requirements.txt` 有沒有推上 GitHub。

**Q:可以從手機用嗎?**
A:可以,Streamlit 預設就響應式設計。直接在手機瀏覽器開網址就好,iOS/Android 都能加到主畫面。

---

## 七、資源限額(都很夠 2-3 人用)

| 服務 | 免費額度 | 你會用到的 |
|------|---------|-----------|
| Supabase | 500 MB 資料庫、50K MAU、5 GB 流量/月 | <1% |
| Streamlit Cloud | 無限 app、1 GB 記憶體、社群 cluster | 完全夠 |

只要不是要做給 1000 個人用,免費用一輩子都不會超過。
