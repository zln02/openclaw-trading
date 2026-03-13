create extension if not exists pgcrypto;

create table if not exists agent_decisions (
    id uuid default gen_random_uuid() primary key,
    timestamp timestamptz default now(),
    agent_name text not null,
    market text not null,
    decision_type text not null,
    action text not null,
    confidence double precision,
    reasoning text not null,
    context jsonb,
    result text,
    created_at timestamptz default now()
);

create index if not exists idx_agent_decisions_ts
    on agent_decisions (coalesce(created_at, timestamp) desc);
create index if not exists idx_agent_decisions_agent
    on agent_decisions (agent_name);
create index if not exists idx_agent_decisions_market
    on agent_decisions (market);

create table if not exists agent_performance (
    id uuid default gen_random_uuid() primary key,
    period_start date not null,
    period_end date not null,
    agent_name text not null,
    market text not null,
    total_signals integer default 0,
    correct_signals integer default 0,
    accuracy double precision,
    pnl_contribution double precision,
    avg_confidence double precision,
    veto_count integer default 0,
    conflict_count integer default 0,
    created_at timestamptz default now()
);

create index if not exists idx_agent_performance_period
    on agent_performance (period_start desc, period_end desc);
create index if not exists idx_agent_performance_agent
    on agent_performance (agent_name, market);

create table if not exists circuit_breaker_events (
    id uuid default gen_random_uuid() primary key,
    timestamp timestamptz default now(),
    trigger_level text not null,
    portfolio_drawdown double precision,
    action_taken text not null,
    details jsonb,
    created_at timestamptz default now()
);

create index if not exists idx_circuit_breaker_events_ts
    on circuit_breaker_events (coalesce(created_at, timestamp) desc);

create table if not exists health_snapshots (
    id uuid default gen_random_uuid() primary key,
    timestamp timestamptz default now(),
    component text not null,
    status text not null,
    details jsonb,
    latency_ms integer,
    created_at timestamptz default now()
);

create index if not exists idx_health_snapshots_component_ts
    on health_snapshots (component, coalesce(created_at, timestamp) desc);
