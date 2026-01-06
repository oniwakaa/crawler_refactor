-- Migration: Unify User IDs
-- Objective: Enforce user_id foreign keys referencing public.profiles(id) on all user-specific tables.

-- 1. Jobs Table
-- Add user_id column if it doesn't exist
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'jobs' and column_name = 'user_id') then
    alter table public.jobs add column user_id uuid references public.profiles(id) on delete cascade;
  else
    -- If it exists but doesn't have the correct FK or constraint, you might need manual intervention or refined logic.
    -- For now, we assume if it exists, we enforce the FK.
    alter table public.jobs drop constraint if exists jobs_user_id_fkey;
    alter table public.jobs add constraint jobs_user_id_fkey foreign key (user_id) references public.profiles(id) on delete cascade;
  end if;
end $$;

-- Enable RLS on jobs
alter table public.jobs enable row level security;
create policy "Users can view own jobs" on public.jobs for select using (user_id = auth.uid());
create policy "Users can insert own jobs" on public.jobs for insert with check (user_id = auth.uid());
create policy "Users can update own jobs" on public.jobs for update using (user_id = auth.uid());
create policy "Users can delete own jobs" on public.jobs for delete using (user_id = auth.uid());


-- 2. Leads Table
-- Add user_id column
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'leads' and column_name = 'user_id') then
    alter table public.leads add column user_id uuid references public.profiles(id) on delete cascade;
  else
    alter table public.leads drop constraint if exists leads_user_id_fkey;
    alter table public.leads add constraint leads_user_id_fkey foreign key (user_id) references public.profiles(id) on delete cascade;
  end if;
end $$;

-- Enable RLS on leads
alter table public.leads enable row level security;
create policy "Users can view own leads" on public.leads for select using (user_id = auth.uid());
create policy "Users can delete own leads" on public.leads for delete using (user_id = auth.uid());
-- Leads are often inserted by the backend, which might use a service role. 
-- But if authenticated user inserts:
create policy "Users can insert own leads" on public.leads for insert with check (user_id = auth.uid());


-- 3. Conversations Table
-- Modify user_id to reference public.profiles
-- Note: schema.sql said "user_id uuid not null", referencing auth.users loosely. 
-- We now enforce FK to profiles.
alter table public.conversations drop constraint if exists conversations_user_id_fkey;
alter table public.conversations add constraint conversations_user_id_fkey foreign key (user_id) references public.profiles(id) on delete cascade;

-- Enable RLS on conversations
alter table public.conversations enable row level security;
create policy "Users can view own conversations" on public.conversations for select using (user_id = auth.uid());
create policy "Users can insert own conversations" on public.conversations for insert with check (user_id = auth.uid());
create policy "Users can update own conversations" on public.conversations for update using (user_id = auth.uid());
create policy "Users can delete own conversations" on public.conversations for delete using (user_id = auth.uid());


-- 4. Messages Table
-- Add user_id column
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'messages' and column_name = 'user_id') then
    alter table public.messages add column user_id uuid references public.profiles(id) on delete cascade;
  else
    alter table public.messages drop constraint if exists messages_user_id_fkey;
    alter table public.messages add constraint messages_user_id_fkey foreign key (user_id) references public.profiles(id) on delete cascade;
  end if;
end $$;

-- Enable RLS on messages
alter table public.messages enable row level security;
create policy "Users can view own messages" on public.messages for select using (user_id = auth.uid());
create policy "Users can insert own messages" on public.messages for insert with check (user_id = auth.uid());
create policy "Users can delete own messages" on public.messages for delete using (user_id = auth.uid());
