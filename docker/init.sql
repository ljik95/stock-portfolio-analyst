-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    name        VARCHAR(255),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Portfolios table (one user can have multiple portfolios)
CREATE TABLE IF NOT EXISTS portfolios (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL DEFAULT 'My Portfolio',
    broker      VARCHAR(100) DEFAULT 'robinhood',
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    raw_csv     TEXT,                              -- store original CSV
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Holdings table (individual positions in a portfolio)
CREATE TABLE IF NOT EXISTS holdings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id     UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker           VARCHAR(20) NOT NULL,
    name             VARCHAR(255),
    quantity         NUMERIC(18, 8) NOT NULL,
    average_cost     NUMERIC(18, 4),              -- average buy price
    current_price    NUMERIC(18, 4),
    current_value    NUMERIC(18, 4),
    total_return     NUMERIC(18, 4),
    return_pct       NUMERIC(8, 4),
    sector           VARCHAR(100),
    asset_type       VARCHAR(50) DEFAULT 'stock', -- stock, etf, crypto, option
    purchased_at     DATE,                        -- acquisition date from CSV (nullable)
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Price history cache (to avoid hammering the market data API)
CREATE TABLE IF NOT EXISTS price_history (
    id          BIGSERIAL PRIMARY KEY,
    ticker      VARCHAR(20) NOT NULL,
    date        DATE NOT NULL,
    open        NUMERIC(18, 4),
    high        NUMERIC(18, 4),
    low         NUMERIC(18, 4),
    close       NUMERIC(18, 4),
    volume      BIGINT,
    UNIQUE(ticker, date)
);

-- News articles (cached for RAG)
CREATE TABLE IF NOT EXISTS news_articles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker       VARCHAR(20),
    title        TEXT NOT NULL,
    content      TEXT,
    source       VARCHAR(255),
    published_at TIMESTAMP WITH TIME ZONE,
    url          TEXT,
    embedding    vector(1536),                    -- OpenAI/Anthropic embedding dimension
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chat conversations
CREATE TABLE IF NOT EXISTS conversations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chat messages
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    tool_calls      JSONB,                         -- store LLM tool call metadata
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_holdings_portfolio_id ON holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON holdings(ticker);
CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date ON price_history(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_articles(ticker);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);

-- pgvector index for semantic similarity search on news
CREATE INDEX IF NOT EXISTS idx_news_embedding ON news_articles
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
