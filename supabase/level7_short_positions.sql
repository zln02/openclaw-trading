create table if not exists public.short_positions (
    id uuid primary key default gen_random_uuid(),
    ticker text not null,
    ticker_name text,
    entry_price numeric,
    current_price numeric,
    quantity integer not null default 0,
    side text not null default 'SHORT',
    pnl_pct numeric default 0,
    factor_snapshot jsonb default '{}'::jsonb,
    close_reason text,
    created_at timestamptz not null default now(),
    closed_at timestamptz
);

create index if not exists idx_short_positions_open on public.short_positions (closed_at, created_at desc);
create index if not exists idx_short_positions_ticker on public.short_positions (ticker, created_at desc);
