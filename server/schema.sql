-- Jobs Table
create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid, -- Reference to auth.users, can be nullable for anon jobs if needed, but usually required
  query text not null,
  status text not null default 'pending',
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  completed_at timestamp with time zone,
  result_count int default 0,
  error text,
  metadata jsonb
);

-- Leads Table
create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references public.jobs(id),
  name text,
  company text,
  role text,
  email text,
  phone_number text,
  linkedin text,
  company_domain text,
  confidence_score float,
  source_url text,
  metadata jsonb,
  extraction_timestamp timestamp with time zone,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Indexes
create index if not exists idx_leads_job_id on public.leads(job_id);
create index if not exists idx_jobs_created_at on public.jobs(created_at desc);
create index if not exists idx_jobs_user_id on public.jobs(user_id);

-- Conversations Table
create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null, -- references auth.users(id) but kept loose for now to avoid auth schema dependency issues in dev
  title text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Messages Table
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references public.conversations(id) on delete cascade not null,
  role text not null check (role in ('user', 'assistant')),
  content text,
  metadata jsonb,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Add conversation_id to leads
alter table public.leads add column if not exists conversation_id uuid references public.conversations(id);
alter table public.leads add column if not exists phone_number text;
alter table public.leads add column if not exists source_url text;
alter table public.leads add column if not exists extraction_timestamp timestamp with time zone;
create index if not exists idx_messages_conversation_id on public.messages(conversation_id);
create index if not exists idx_conversations_user_id on public.conversations(user_id);
