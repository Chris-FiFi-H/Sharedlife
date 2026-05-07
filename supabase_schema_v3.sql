-- =====================================================================
-- 記帳日誌 App - Supabase Schema v3(資產類別公開/私人)
-- 在 Supabase Dashboard → SQL Editor 整份貼上,點 RUN 執行
-- 這份是「升級」用,跑過 v2 之後再跑這份
-- =====================================================================

-- ============ 1. 加 is_public 欄位 ============
-- 預設 true,維持既有「所有人都看得到」的行為
alter table public.asset_categories
  add column if not exists is_public boolean default true;

-- ============ 2. 重做讀取 RLS 規則 ============
-- 規則:可以看自己的全部 + 其他人「公開」的類別

-- ----- asset_categories 改 -----
drop policy if exists "read_all_asset_cat"        on asset_categories;
drop policy if exists "read_own_or_public_asset_cat" on asset_categories;

create policy "read_own_or_public_asset_cat"
  on asset_categories for select to authenticated
  using (
    auth.uid() = user_id
    OR is_public = true
  );

-- ----- monthly_assets 改 -----
-- 月度記錄的可見性跟著它的類別走
drop policy if exists "read_all_ma"        on monthly_assets;
drop policy if exists "read_own_or_public_ma" on monthly_assets;

create policy "read_own_or_public_ma"
  on monthly_assets for select to authenticated
  using (
    auth.uid() = user_id
    OR exists (
      select 1
      from public.asset_categories ac
      where ac.id = monthly_assets.category_id
        and ac.is_public = true
    )
  );

-- =====================================================================
-- 完成。新建立的類別預設是「公開」,可以在 App 的「管理類別」分頁切換。
-- =====================================================================
