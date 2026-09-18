-- Run this in Supabase SQL Editor before setting SUPABASE_PERSIST_RESULTS=true.
create table if not exists public.evaluations (
    id uuid primary key,
    created_at timestamptz not null default now(),
    player_id text not null,
    mode text not null,
    file_count integer not null default 1,
    design_craft_score numeric not null,
    tier_name text not null,
    tier_key text not null,
    tier_icon text,
    website_confidence numeric not null default 0,
    results_json jsonb not null
);

alter table public.evaluations add column if not exists player_id text;
alter table public.evaluations add column if not exists website_confidence numeric not null default 0;
update public.evaluations set player_id = 'legacy' where player_id is null;
alter table public.evaluations alter column player_id set not null;

create index if not exists evaluations_player_created_at_idx
    on public.evaluations (player_id, created_at desc);

alter table public.evaluations enable row level security;