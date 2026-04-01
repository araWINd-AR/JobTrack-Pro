-- Run this in Supabase SQL Editor

create table if not exists public.app_users (
  id bigint generated always as identity primary key,
  full_name text not null default 'User',
  email text not null unique,
  password_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.jobs (
  id bigint generated always as identity primary key,
  user_id bigint not null references public.app_users(id) on delete cascade,
  company text not null,
  role text not null,
  status text not null default 'Applied',
  location text,
  applied_date date,
  due_date date,
  follow_up_date date,
  priority text,
  job_source text,
  salary text,
  work_mode text,
  resume_version text,
  interview_notes text,
  rejection_reason text,
  jd_text text,
  link text,
  notes text,
  resume_filename text,
  created_at timestamptz not null default now()
);

create index if not exists jobs_user_id_idx on public.jobs(user_id);
create index if not exists jobs_due_date_idx on public.jobs(due_date);

alter table public.app_users enable row level security;
alter table public.jobs enable row level security;

-- No anon/auth policies are needed for this Flask version because the backend uses
-- the service_role key server-side only. Do not expose the service_role key in the browser.
