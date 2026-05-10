# 📦 整合更新包 — 資產編輯改進 + Cookie 登入修復

這份是從你**上次成功部署 CSV 匯入匯出**之後到現在的所有改動,合在一起讓你一次套用。

## 修改的檔案(只有 3 個)

```
sharedlife_updates/
├── app.py                          ← Cookie 修復(自動登入時序處理)
├── utils.py                        ← Cookie 修復(等待機制 + 子頁面也支援自動登入)
└── pages/
    └── 5_📋_資產模板.py            ← 資產相關所有改進
```

**沒有 SQL 變更**,Supabase 不用動。

---

## 包含什麼變更

### 1️⃣ 類別管理可即時編輯
- 點分區、名稱、幣別、有成本、順序、公開,都能直接改,改完移開焦點自動存
- 跳 toast 提示「已更新」
- 刪除類別改為**二次確認**(防誤按):點 🗑️ 變成 ✓,再點才真刪

### 2️⃣ 金額/成本欄位改成整數
- 本月資產的「金額」「成本」不再有小數點
- 每按上下箭頭加減 100
- 匯率仍保留小數(31.5 之類)

### 3️⃣ 「其他項目」區加入 6 個預設類別
| 項目 | 說明 |
|------|------|
| 保險現值 | 儲蓄險/投資型保單的解約金 |
| 現金 | 手邊現金 |
| 悠遊卡/iCash | 電子票證餘額 |
| 不動產 | 房屋市值 |
| 車輛 | 車子估值 |
| 應收款 | 別人欠你的錢 |

舊使用者要點「📋 補建預設模板裡缺少的類別」按鈕(在 ⚙️ 管理類別 tab 底下)才會補上。

### 4️⃣ 修復「重整後就要重登入」的 bug
- 原因:Cookie 從瀏覽器送過來需要時間,我之前 code 沒等就直接放棄
- 修復:首次發現 cookie 為空時 → 顯示「⏳ 載入中...」→ 暫停 0.3 秒 → 重新整理 → 成功讀到 cookie → 自動登入
- 順便修復**子頁面重整也能自動登入**(原本子頁面重整會跳「請先到首頁登入」)

> ⚠️ **重要說明**:你的紀錄沒丟。資料存在 Supabase 雲端,登入只是顯示權限而已。重新登入後資料都會在。

---

## 套用方式(任選一種)

### 方式 A:直接覆蓋(最快,推薦)

```cmd
cd C:\git\Sharedlife

:: 把這 3 個檔案放到對的位置
copy /Y "%USERPROFILE%\Downloads\sharedlife_updates\app.py" .
copy /Y "%USERPROFILE%\Downloads\sharedlife_updates\utils.py" .
copy /Y "%USERPROFILE%\Downloads\sharedlife_updates\pages\5_📋_資產模板.py" "pages\"

:: commit + push
git add app.py utils.py pages
git commit -m "feat: 資產類別編輯 + 整數金額 + 其他項目預設 / fix: cookie 自動登入"
git push origin master
```

### 方式 B:Patch(用 git am)

```cmd
cd C:\git\Sharedlife
git checkout master && git pull
git checkout -b feature/asset-and-cookie-updates
git am < %USERPROFILE%\Downloads\all_updates_consolidated.patch
git push -u origin feature/asset-and-cookie-updates
:: 開 PR、Merge
```

### 方式 C:Bundle

```cmd
cd C:\git\Sharedlife
git fetch %USERPROFILE%\Downloads\all_updates_consolidated.bundle ^
  consolidated/asset-and-cookie-updates:feature/asset-and-cookie-updates
git checkout feature/asset-and-cookie-updates
git push -u origin feature/asset-and-cookie-updates
```

---

## 套用完之後

1. Streamlit Cloud 自動 redeploy(1-2 分鐘)
2. 開 App 第一次可能還是要登入(因為現在的 cookie 是壞的舊版本)
3. 登入後 → 重整看看,**應該不再回到登入頁**了
4. 進「⚙️ 管理類別」分頁 → 找到「📋 補建預設模板裡缺少的類別」 → 點「🔍 檢查並補建缺漏」 → 其他項目區會多 6 個類別

---

## 如果重整後還是要重登

跟我說以下三件事:
- 用什麼瀏覽器(Chrome / Safari / Edge / Firefox)
- 是否開了無痕模式
- 是否有用任何擋 cookie 的擴充功能(uBlock / Privacy Badger / Brave 內建)
