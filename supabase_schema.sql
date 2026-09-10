-- Run this in Supabase SQL Editor before setting SUPABASE_PERSIST_RESULTS=true.
create table if not exists public.evaluations (
    id uuid primary key,
    created_at timestamptz not null default now(),
    mode text not null,
    file_count integer not null default 1,
    design_craft_score numeric not null,
    tier_name text not null,
    tier_key text not null,
    tier_icon text,
    results_json jsonb not null
);

alter table public.evaluations enable row level security;