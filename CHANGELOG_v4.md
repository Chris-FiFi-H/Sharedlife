# 📦 v4 更新 — 細粒度可見性(指定分享給特定使用者)

## 新功能:三態可見性

每個資產類別可獨立設成:

| 模式 | 圖示 | 誰能看 |
|------|------|--------|
| 私人 | 🔒 | 只有自己 |
| 公開 | 🌐 | 所有登入的使用者 |
| **指定**(新) | 👥 | 自己 + 你勾選的特定使用者 |

可見性會自動套用到:
- 「📈 資產走勢」(別人看不到的就不會出現)
- 「🤝 共同資產」(別人看不到的就不會被加進合計)

## 修改的檔案

```
sharedlife_v4/
├── utils.py                            ← 修 auth 競爭(管理類別空白問題)
├── supabase_schema_v4.sql              ← 新 SQL,需要在 Supabase 跑
└── pages/
    └── 5_📋_資產模板.py                ← 三態 UI + 分享名單管理
```

## 部署步驟

### 1. 跑 Supabase SQL
- Dashboard → SQL Editor → New query → 整份貼上 `supabase_schema_v4.sql` → Run

### 2. 推 code(直接覆蓋是最快的)
```cmd
cd C:\git\Sharedlife
copy /Y "%USERPROFILE%\Downloads\sharedlife_v4\utils.py" .
copy /Y "%USERPROFILE%\Downloads\sharedlife_v4\pages\5_📋_資產模板.py" "pages\"
copy /Y "%USERPROFILE%\Downloads\sharedlife_v4\supabase_schema_v4.sql" .
git add -A
git commit -m "feat: 細粒度可見性 + auth 競爭修復"
git push origin master
```

或開 PR:
```cmd
git checkout -b feature/visibility-shared
git am < %USERPROFILE%\Downloads\visibility_shared.patch
git push -u origin feature/visibility-shared
```

## 套用後試試

1. 進「⚙️ 管理類別」
2. 找一個類別 → 「可見性」欄位點下去 → 選 **👥 指定**
3. 下方會多出一行 **└ 分享給** + 多選使用者下拉
4. 勾選想分享的使用者 → 自動存,跳「已更新分享名單」

## 重要細節

- **既有資料自動遷移**:跑完 SQL,你之前 `is_public=true` 的全變成 `public`,`is_public=false` 變成 `private`
- **沒有 anything 會變不見**,你和朋友之前看得到的還是看得到
- **只是新增了「指定」這個選項**,讓你能更精確地控制誰看得到什麼
- 共同資產計算的範圍跟著 RLS 走,看不到的就不會被加進去 — 沒額外設定要做
