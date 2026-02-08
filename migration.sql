-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the Knowledge Items table
CREATE TABLE IF NOT EXISTS knowledge_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    title VARCHAR NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536), -- Open AI text-embedding-3-small
    search_vector TSVECTOR,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create Indexes for Performance
-- HNSW Index for Vector Search (Cosine Similarity)
CREATE INDEX IF NOT EXISTS idx_knowledge_items_embedding ON knowledge_items USING hnsw (embedding vector_cosine_ops);

-- GIN Index for Keyword Search
CREATE INDEX IF NOT EXISTS idx_knowledge_items_search_vector ON knowledge_items USING gin (search_vector);

-- 4. Create Trigger to Auto-Update Search Vector (Hybrid Search Magic)
-- This ensures 'search_vector' is always in sync with 'content' and 'title'
CREATE OR REPLACE FUNCTION knowledge_items_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.title,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.content,'')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
ON knowledge_items FOR EACH ROW EXECUTE PROCEDURE knowledge_items_search_vector_update();
