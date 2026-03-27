-- Supabase: 누락된 agent_decisions / agent_performance 테이블 생성
-- Supabase Dashboard > SQL Editor에서 실행

create table if not exists public.agent_decisions (
  id             bigserial primary key,
  created_at     timestamptz not null default now(),
  agent_name     text,
  agent_team     text,
  market         text not null,
  decision_type  text,
  decision       text,
  action         text not null,
  confidence     double precision,
  reasoning      text,
  context        jsonb not null default '{}'::jsonb,
  result         text,
  constraint chk_agent_decisions_market
    check (market in ('btc', 'kr', 'us')),
  constraint chk_agent_decisions_confidence
    check (confidence is null or (confidence >= 0.0 and confidence <= 100.0))
);

create index if not exists idx_agent_decisions_created_at
  on public.agent_decisions (created_at desc);

create index if not exists idx_agent_decisions_market_created_at
  on public.agent_decisions (market, created_at desc);

create index if not exists idx_agent_decisions_agent_market_created_at
  on public.agent_decisions (agent_name, market, created_at desc);

alter table public.agent_decisions enable row level security;

drop policy if exists "service_role_only_agent_decisions" on public.agent_decisions;

create policy "service_role_only_agent_decisions"
  on public.agent_decisions
  for all
  to service_role
  using (true)
  with check (true);


create table if not exists public.agent_performance (
  id                bigserial primary key,
  created_at        timestamptz not null default now(),
  period_start      date,
  period_end        date not null,
  agent_name        text not null,
  market            text not null,
  total_trades      integer,
  win_rate          double precision,
  total_pnl_pct     double precision,
  sharpe_ratio      double precision,
  max_drawdown      double precision,
  total_signals     integer,
  correct_signals   integer,
  accuracy          double precision,
  pnl_contribution  double precision,
  avg_confidence    double precision,
  veto_count        integer,
  conflict_count    integer,
  constraint uq_agent_performance_period_agent_market
    unique (period_end, agent_name, market),
  constraint chk_agent_performance_market
    check (market in ('btc', 'kr', 'us'))
);

create index if not exists idx_agent_performance_created_at
  on public.agent_performance (created_at desc);

create index if not exists idx_agent_performance_period_end
  on public.agent_performance (period_end desc);

create index if not exists idx_agent_performance_agent_market_period_end
  on public.agent_performance (agent_name, market, period_end desc);

alter table public.agent_performance enable row level security;

drop policy if exists "service_role_only_agent_performance" on public.agent_performance;

create policy "service_role_only_agent_performance"
  on public.agent_performance
  for all
  to service_role
  using (true)
  with check (true);
