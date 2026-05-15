-- ═══════════════════════════════════════════════════
--  FF | Factcheck-Finger — Supabase 테이블 스키마
--  Supabase 대시보드 → SQL Editor 에서 실행하세요
-- ═══════════════════════════════════════════════════

-- 분석된 기사 저장
CREATE TABLE IF NOT EXISTS articles (
  id                   UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  url                  TEXT DEFAULT '',
  domain               TEXT DEFAULT '',
  title                TEXT NOT NULL,
  trust_score          INTEGER DEFAULT 0,
  grade                TEXT DEFAULT '',
  w5_score             INTEGER DEFAULT 0,
  kw_score             INTEGER DEFAULT 0,
  cb_score             INTEGER DEFAULT 0,
  summary              TEXT DEFAULT '',
  terms                TEXT DEFAULT '[]',
  economic_indicators  TEXT DEFAULT '[]',
  fact_claims          TEXT DEFAULT '[]',
  similar_keywords     TEXT DEFAULT '[]',
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- 출처별 신뢰도 통계
CREATE TABLE IF NOT EXISTS sources (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  domain           TEXT UNIQUE NOT NULL,
  name             TEXT DEFAULT '',
  article_count    INTEGER DEFAULT 0,
  avg_trust_score  NUMERIC DEFAULT 0,
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 (빠른 조회용)
CREATE INDEX IF NOT EXISTS idx_articles_domain     ON articles(domain);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_score      ON articles(trust_score);
CREATE INDEX IF NOT EXISTS idx_sources_domain      ON sources(domain);

-- 네이버 뉴스 검색 캐시
CREATE TABLE IF NOT EXISTS news_cache (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  url         TEXT UNIQUE NOT NULL,
  title       TEXT DEFAULT '',
  description TEXT DEFAULT '',
  source      TEXT DEFAULT '',
  pub_date    TEXT DEFAULT '',
  query       TEXT DEFAULT '',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_cache_query  ON news_cache(query);
CREATE INDEX IF NOT EXISTS idx_news_cache_source ON news_cache(source);

ALTER TABLE news_cache DISABLE ROW LEVEL SECURITY;

-- news_cache에 confirmed_count 추가 (여러 언론사에서 확인된 횟수)
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS confirmed_count INTEGER DEFAULT 1;
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS keywords TEXT DEFAULT '';

-- ── pgvector 활성화 ──────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ── news_cache에 육하원칙 + 임베딩 컬럼 추가 ────────────
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS w5h_data   JSONB DEFAULT '{}';
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS embeddings JSONB DEFAULT '{}';

-- 임베딩 벡터 검색용 인덱스 (나중에 pgvector로 고도화 가능)
CREATE INDEX IF NOT EXISTS idx_news_cache_w5h ON news_cache USING GIN (w5h_data);
