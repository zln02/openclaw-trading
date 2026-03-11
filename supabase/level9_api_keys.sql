create table if not exists public.api_keys (
    id uuid primary key default gen_random_uuid(),
    key_hash text not null,
    user_email text,
    tier text not null default 'free',
    created_at timestamptz not null default now(),
    last_used_at timestamptz
);

create unique index if not exists idx_api_keys_key_hash on public.api_keys (key_hash);
create index if not exists idx_api_keys_tier on public.api_keys (tier, created_at desc);
