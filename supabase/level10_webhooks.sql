create table if not exists public.webhooks (
    id text primary key,
    url text not null,
    events jsonb not null default '[]'::jsonb,
    secret_hash text not null,
    created_at timestamptz not null default now(),
    active boolean not null default true
);

create index if not exists idx_webhooks_active on public.webhooks (active, created_at desc);
