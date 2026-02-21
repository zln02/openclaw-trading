-- 기존 테이블 삭제
DROP TABLE IF EXISTS stock_data;
DROP TABLE IF EXISTS stock_financials;
DROP TABLE IF EXISTS stock_ohlcv;
DROP TABLE IF EXISTS stock_reports;

-- daily_ohlcv 테이블
CREATE TABLE daily_ohlcv (
    stock_code VARCHAR(10),
    date DATE,
    open_price FLOAT,
    high_price FLOAT,
    low_price FLOAT,
    close_price FLOAT,
    volume BIGINT,
    PRIMARY KEY (stock_code, date)
);

-- intraday_ohlcv 테이블
CREATE TABLE intraday_ohlcv (
    stock_code VARCHAR(10),
    timestamp TIMESTAMP,
    open_price FLOAT,
    high_price FLOAT,
    low_price FLOAT,
    close_price FLOAT,
    volume BIGINT,
    PRIMARY KEY (stock_code, timestamp)
);

-- top50_stocks 테이블
CREATE TABLE top50_stocks (
    stock_code VARCHAR(10),
    stock_name VARCHAR(100),
    volume BIGINT,
    market_cap FLOAT,
    industry VARCHAR(50),
    PRIMARY KEY (stock_code)
);

-- disclosures 테이블
CREATE TABLE disclosures (
    stock_code VARCHAR(10),
    title TEXT,
    date DATE,
    type VARCHAR(50),
    PRIMARY KEY (stock_code, title)
);

-- disclosure_details 테이블
CREATE TABLE disclosure_details (
    disclosure_id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10),
    content TEXT,
    FOREIGN KEY (stock_code) REFERENCES disclosures(stock_code)
);

-- financial_statements 테이블
CREATE TABLE financial_statements (
    stock_code VARCHAR(10),
    revenue FLOAT,
    operating_income FLOAT,
    net_income FLOAT,
    per FLOAT,
    pbr FLOAT,
    roe FLOAT,
    PRIMARY KEY (stock_code)
);

-- trade_executions 테이블
CREATE TABLE trade_executions (
    trade_id SERIAL PRIMARY KEY,
    trade_type VARCHAR(10),
    stock_code VARCHAR(10),
    quantity INT,
    price FLOAT,
    strategy VARCHAR(50),
    reason TEXT,
    result VARCHAR(50)
);

-- trade_snapshots 테이블
CREATE TABLE trade_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    trade_id INT,
    market_state TEXT,
    timestamp TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trade_executions(trade_id)
);

-- data_collection_log 테이블
CREATE TABLE data_collection_log (
    log_id SERIAL PRIMARY KEY,
    status VARCHAR(10),
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- daily_reports 테이블
CREATE TABLE daily_reports (
    report_id SERIAL PRIMARY KEY,
    date DATE,
    return_rate FLOAT,
    win_rate FLOAT,
    trade_count INT
);