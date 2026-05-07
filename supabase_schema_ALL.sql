-- =====================================================================
-- 記帳日誌 App - Supabase Schema
-- 在 Supabase Dashboard → SQL Editor 整份貼上,點 RUN 執行
-- =====================================================================

-- ============ 1. 使用者顯示資料 ============
create table if not exists public.profiles (
  id uuid references auth.users on delete cascade primary key,
  display_name text,
  created_at timestamptz default now()
);

-- ============ 2. 記帳資料 ============
create table if not exists public.transactions (
  id bigint primary key generated always as identity,
  user_id uuid references auth.users on delete cascade not null,
  amount numeric not null check (amount > 0),
  type text not null check (type in ('income', 'expense')),
  category text,
  description text,
  transaction_date date not null default current_date,
  created_at timestamptz default now()
);

create index if not exists idx_tx_user on transactions (user_id);
create index if not exists idx_tx_date on transactions (transaction_date);

-- ============ 3. 日誌資料 ============
create table if not exists public.journal_entries (
  id bigint primary key generated always as identity,
  user_id uuid references auth.users on delete cascade not null,
  title text,
  content text not null,
  entry_date date not null default current_date,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_journal_user on journal_entries (user_id);
create index if not exists idx_journal_date on journal_entries (entry_date);

-- ============ 4. 註冊時自動建立 profile ============
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1))
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();


-- =====================================================================
-- Row Level Security (RLS) 權限設定
-- 因為這是給小團體用、所有人都能看彼此記錄的應用,規則如下:
--   讀:任何登入者都能看所有人的資料
--   寫:每個人只能新增/修改/刪除自己的資料
-- =====================================================================

alter table profiles         enable row level security;
alter table transactions     enable row level security;
alter table journal_entries  enable row level security;

-- ===== profiles =====
drop policy if exists "read_all_profiles"   on profiles;
drop policy if exists "update_own_profile"  on profiles;

create policy "read_all_profiles"
  on profiles for select to authenticated using (true);

create policy "update_own_profile"
  on profiles for update to authenticated using (auth.uid() = id);

-- ===== transactions =====
drop policy if exists "read_all_tx"    on transactions;
drop policy if exists "insert_own_tx"  on transactions;
drop policy if exists "update_own_tx"  on transactions;
drop policy if exists "delete_own_tx"  on transactions;

create policy "read_all_tx"
  on transactions for select to authenticated using (true);

create policy "insert_own_tx"
  on transactions for insert to authenticated with check (auth.uid() = user_id);

create policy "update_own_tx"
  on transactions for update to authenticated using (auth.uid() = user_id);

create policy "delete_own_tx"
  on transactions for delete to authenticated using (auth.uid() = user_id);

-- ===== journal_entries =====
drop policy if exists "read_all_journal"    on journal_entries;
drop policy if exists "insert_own_journal"  on journal_entries;
drop policy if exists "update_own_journal"  on journal_entries;
drop policy if exists "delete_own_journal"  on journal_entries;

create policy "read_all_journal"
  on journal_entries for select to authenticated using (true);

create policy "insert_own_journal"
  on journal_entries for insert to authenticated with check (auth.uid() = user_id);

create policy "update_own_journal"
  on journal_entries for update to authenticated using (auth.uid() = user_id);

create policy "delete_own_journal"
  on journal_entries for delete to authenticated using (auth.uid() = user_id);
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
