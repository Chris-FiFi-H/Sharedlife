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
