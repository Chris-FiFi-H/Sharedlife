-- =====================================================================
-- 記帳日誌 App - Supabase Schema v2(資產模板功能)
-- 在 Supabase Dashboard → SQL Editor 整份貼上,點 RUN 執行
-- 注意:這份是「追加」用,不會動到既有的 transactions / journal_entries
-- =====================================================================

-- ============ 1. 資產類別(每個 user 自己的模板) ============
create table if not exists public.asset_categories (
  id bigint primary key generated always as identity,
  user_id uuid references auth.users on delete cascade not null,
  section text not null check (section in ('bank', 'investment', 'other')),
  name text not null,
  has_cost_value boolean default false,           -- 是否有「成本/現值」(投資帳戶用)
  default_currency text default 'TWD' check (default_currency in ('TWD', 'USD')),
  display_order int default 0,
  is_active boolean default true,
  created_at timestamptz default now()
);

create index if not exists idx_asset_cat_user on asset_categories (user_id);

-- ============ 2. 月度資產記錄 ============
create table if not exists public.monthly_assets (
  id bigint primary key generated always as identity,
  user_id uuid references auth.users on delete cascade not null,
  category_id bigint references asset_categories on delete cascade not null,
  year int not null,
  month int not null check (month between 1 and 12),
  -- 該月使用的幣別與匯率
  currency text default 'TWD' check (currency in ('TWD', 'USD')),
  exchange_rate numeric default 1,
  -- 用「原幣別」儲存的金額,顯示時再 * 匯率
  current_value numeric not null default 0,       -- 現值(原幣別)
  cost numeric,                                    -- 成本(原幣別,投資帳戶用)
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (user_id, category_id, year, month)
);

create index if not exists idx_ma_user_ym on monthly_assets (user_id, year, month);
create index if not exists idx_ma_category on monthly_assets (category_id);


-- =====================================================================
-- Row Level Security 設定
-- 跟既有規則一致:登入者都能看,只能改自己的
-- =====================================================================

alter table asset_categories enable row level security;
alter table monthly_assets   enable row level security;

-- ===== asset_categories =====
drop policy if exists "read_all_asset_cat"   on asset_categories;
drop policy if exists "insert_own_asset_cat" on asset_categories;
drop policy if exists "update_own_asset_cat" on asset_categories;
drop policy if exists "delete_own_asset_cat" on asset_categories;

create policy "read_all_asset_cat"
  on asset_categories for select to authenticated using (true);

create policy "insert_own_asset_cat"
  on asset_categories for insert to authenticated with check (auth.uid() = user_id);

create policy "update_own_asset_cat"
  on asset_categories for update to authenticated using (auth.uid() = user_id);

create policy "delete_own_asset_cat"
  on asset_categories for delete to authenticated using (auth.uid() = user_id);

-- ===== monthly_assets =====
drop policy if exists "read_all_ma"   on monthly_assets;
drop policy if exists "insert_own_ma" on monthly_assets;
drop policy if exists "update_own_ma" on monthly_assets;
drop policy if exists "delete_own_ma" on monthly_assets;

create policy "read_all_ma"
  on monthly_assets for select to authenticated using (true);

create policy "insert_own_ma"
  on monthly_assets for insert to authenticated with check (auth.uid() = user_id);

create policy "update_own_ma"
  on monthly_assets for update to authenticated using (auth.uid() = user_id);

create policy "delete_own_ma"
  on monthly_assets for delete to authenticated using (auth.uid() = user_id);
