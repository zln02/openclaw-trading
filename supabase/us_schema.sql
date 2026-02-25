-- Supabase: 미국 주식 모멘텀 파이프라인용 스키마

-- 상위 모멘텀 종목 스냅샷 저장 테이블
create table if not exists public.us_momentum_signals (
  id          bigserial primary key,
  run_date    date        not null,
  symbol      text        not null,
  score       numeric     not null,
  ret_5d      numeric,
  ret_20d     numeric,
  vol_ratio   numeric,
  near_high   numeric,
  created_at  timestamptz not null default now()
);

create index if not exists idx_us_momentum_signals_run_date
  on public.us_momentum_signals (run_date desc);

create index if not exists idx_us_momentum_signals_symbol_date
  on public.us_momentum_signals (symbol, run_date desc);

-- 미국 주식 매매 기록 테이블
create table if not exists public.us_trade_executions (
  id            bigserial primary key,
  trade_type    text        not null,  -- 'BUY' or 'SELL'
  symbol        text        not null,
  quantity      numeric     not null,
  price         numeric     not null,
  reason        text,
  score         numeric,
  result        text        not null default 'OPEN',  -- 'OPEN', 'CLOSED'
  highest_price numeric,
  exit_price    numeric,
  exit_reason   text,
  created_at    timestamptz not null default now()
);

create index if not exists idx_us_trade_executions_result
  on public.us_trade_executions (result);

create index if not exists idx_us_trade_executions_symbol
  on public.us_trade_executions (symbol, created_at desc);

