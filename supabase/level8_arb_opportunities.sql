create table if not exists public.arb_opportunities (
    id uuid primary key default gen_random_uuid(),
    direction text,
    cex_price numeric,
    dex_price numeric,
    spread_pct numeric,
    gas_cost_usd numeric,
    net_profit_usd numeric,
    executed boolean not null default false,
    tx_hash text,
    created_at timestamptz not null default now()
);

create index if not exists idx_arb_opportunities_created_at on public.arb_opportunities (created_at desc);
create index if not exists idx_arb_opportunities_executed on public.arb_opportunities (executed, created_at desc);
