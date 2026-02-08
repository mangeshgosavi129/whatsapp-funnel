-- Migration to support Gemini Embeddings (768 dimensions)

-- 1. Drop existing index on embedding (dependant on dimension)
DROP INDEX IF EXISTS knowledge_embedding_idx;

-- 2. Alter column type
-- Note: This will fail if there is existing data with 1536 dims. 
-- Since this is dev, we can truncate or cast. 
-- Valid casting from 1536 to 768 is not trivial/possible generally.
-- We will TRUNCATE the table for this migration to start fresh with Gemini.
TRUNCATE TABLE knowledge_items;

ALTER TABLE knowledge_items 
ALTER COLUMN embedding TYPE vector(768);

-- 3. Recreate Index
CREATE INDEX knowledge_embedding_idx ON knowledge_items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
