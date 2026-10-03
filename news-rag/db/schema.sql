-- News RAG Chatbot schema
-- Run with: psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}/$POSTGRES_DB" -f db/schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY,
    source TEXT,
    title TEXT,
    date DATE,
    url TEXT UNIQUE,
    category TEXT,
    drive_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Scraped, not-yet-cleaned articles (pipeline/scraper.py writes here directly).
CREATE TABLE IF NOT EXISTS raw_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    published TIMESTAMPTZ,
    source TEXT,
    topic_category TEXT,
    sub_area TEXT,
    search_query TEXT,
    keyword TEXT,
    language TEXT DEFAULT 'en',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Cleaned articles, one per raw_articles row (pipeline/cleaner.py writes here).
-- A raw article with no matching clean_articles.raw_id is still "uncleaned".
CREATE TABLE IF NOT EXISTS clean_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_id UUID UNIQUE REFERENCES raw_articles(id),
    url TEXT,
    title TEXT,
    content TEXT,
    published TIMESTAMPTZ,
    source TEXT,
    topic_category TEXT,
    sub_area TEXT,
    keyword TEXT,
    language TEXT DEFAULT 'en',
    drive_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- di schema.sql, ganti bagian chunks jadi:
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id UUID PRIMARY KEY,
    article_id UUID REFERENCES clean_articles(id),
    chunk_index INT,
    chunk_text TEXT,
    keyword TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(session_id),
    role TEXT CHECK (role IN ('user', 'assistant')),
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON chunks(article_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_raw_articles_topic_category ON raw_articles(topic_category);
CREATE INDEX IF NOT EXISTS idx_raw_articles_sub_area ON raw_articles(sub_area);
CREATE INDEX IF NOT EXISTS idx_raw_articles_keyword ON raw_articles(keyword);
CREATE INDEX IF NOT EXISTS idx_clean_articles_topic_category ON clean_articles(topic_category);
CREATE INDEX IF NOT EXISTS idx_clean_articles_sub_area ON clean_articles(sub_area);
CREATE INDEX IF NOT EXISTS idx_clean_articles_keyword ON clean_articles(keyword);
CREATE INDEX IF NOT EXISTS idx_clean_articles_drive_url ON clean_articles(drive_url) WHERE drive_url IS NULL;
