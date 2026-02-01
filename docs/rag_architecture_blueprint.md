# RAG Architecture Blueprint & Implementation Guide

> [!NOTE]
> This document is designed to be handed to an AI agent or Senior Engineer to implement the RAG system from scratch. It contains deep context about the existing codebase (`whatsapp-funnel`) to ensure seamless integration.

## 1. System Overview

The current system is a **WhatsApp Sales Chatbot** running on a FastAPI backend (`server/`) with a separate background worker (`whatsapp_worker/`) processing messages via SQS.

The LLM logic resides in `whatsapp_worker/llm/`. It uses a 4-step pipeline:
1.  **Analyze**: Understands intent/sentiment/risks (Output `need_kb` flag).
2.  **Decide**: Heuristic + LLM logic to choose action.
3.  **Generate**: Writes the response.
4.  **Summarize**: Updates context.

**The Goal**: Inject a **Retrieval** step between `Analyze` and `Decide` to provide ground-truth business knowledge when `analysis.need_kb.required` is true.

---

## 2. Infrastructure Specification

To maintain simplicity and reduce infra overhead, we will use **PostgreSQL with `pgvector`** rather than a separate vector DB.

### 2.1 Database Models (`server/models_rag.py`)

Create a new file `server/models_rag.py` to keep RAG models isolated.

```python
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from server.database import Base
import uuid

class KnowledgeBase(Base):
    """Represents a source document (e.g. 'Pricing PDF', 'Website FAQ')."""
    __tablename__ = "knowledge_bases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False) # 'file', 'url', 'text'
    status = Column(String(50), default="active")
    
    chunks = relationship("DocumentChunk", back_populates="knowledge_base", cascade="all, delete-orphan")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DocumentChunk(Base):
    """A semantic chunk of a document."""
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # OpenAI text-embedding-3-small dimension
    
    metadata = Column(JSONB, nullable=True) # e.g. {"page": 1, "section": "Pricing"}
    
    # For Hybrid Search (Keyword matching)
    # Note: Requires a TSVECTOR index in migration
    
    knowledge_base = relationship("KnowledgeBase", back_populates="chunks")
```

### 2.2 Migrations
*   Enable `vector` extension (`CREATE EXTENSION IF NOT EXISTS vector;`).
*   Create tables.
*   Add HNSW index on `embedding` for fast similarity search.
*   Add GIN index on `content` (as `tsvector`) for keyword search.

---

## 3. The Retrieval Pipeline (`rag/`)

Create a new top-level package `rag/` in the root (or inside `server/`, but root is cleaner for shared utils).

### 3.1 Embeddings & Re-ranking (`rag/encoder.py`)

Using OpenAI for embeddings (consistency/reliability) and a Cross-Encoder for high-precision re-ranking.

```python
# rag/encoder.py
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI text-embedding-3-small."""
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding
```

### 3.2 The Retriever (`rag/retriever.py`)

Implement **Hybrid Search** + **Re-ranking**.

```python
# rag/retriever.py
from sqlalchemy import text
from rag.encoder import get_embedding

def search_knowledge_base(session, query: str, org_id: str, limit=5) -> list[str]:
    """
    1. Retrieve candidates via Vector Similarity (Cosine Distance).
    2. (Optional) Retrieve candidates via Keyword Match.
    3. Re-rank results (if using Cross-Encoder).
    """
    embedding = get_embedding(query)
    
    # PGVector Query using <=> operator (Cosine Distance)
    sql = text("""
        SELECT content, 1 - (embedding <=> :embedding) as score
        FROM document_chunks
        JOIN knowledge_bases on document_chunks.knowledge_base_id = knowledge_bases.id
        WHERE knowledge_bases.organization_id = :org_id
        ORDER BY embedding <=> :embedding
        LIMIT :limit
    """)
    
    results = session.execute(sql, {
        "embedding": str(embedding), 
        "org_id": org_id, 
        "limit": limit
    }).fetchall()
    
    # Filter by score threshold (e.g. > 0.75)
    return [r.content for r in results if r.score > 0.75]
```

---

## 4. Integration with LLM Pipeline

### 4.1 Update Orchestrator (`llm/pipeline.py`)

Modify `run_pipeline` to check the `need_kb` flag from Step 1.

```python
# llm/pipeline.py

# ... inside run_pipeline ...

# Step 1: ANALYZE
analysis, _, _ = run_analyze(context)

# [NEW] Retrieval Step
kb_context = []
if analysis.need_kb.required:
    from server.database import SessionLocal
    from rag.retriever import search_knowledge_base
    
    logger.info(f"Retrieving knowledge for query: {analysis.need_kb.query}")
    with SessionLocal() as db:
        kb_context = search_knowledge_base(
            db, 
            analysis.need_kb.query, 
            context.organization_id
        )

# Step 2: DECIDE
# Pass kb_context to decide (to know IF we can answer)
decision, _, _ = run_decision(context, analysis, kb_context)

# Step 3: GENERATE
# Pass kb_context to generate (to actually answer)
if decision.action == DecisionAction.SEND_NOW:
    run_generate(context, decision, kb_context)
```

### 4.2 Update Prompts (`llm/prompts.py`)

Modify `GENERATE_USER_TEMPLATE` to accept `context_chunks`.

```python
GENERATE_RETRIEVAL_CONTEXT = """
RETRIEVED KNOWLEDGE:
{context_chunks}

INSTRUCTION: usage of this knowledge is MANDATORY. Do not hallucinate. If the answer is not in the Retrieved Knowledge, say "I'm not sure about that specific detail."
"""
```

Append this block to the User Prompt if `kb_context` is present.

---

## 5. Ingestion Strategy (`rag/ingest.py`)

Do not dump raw text. Use **Semantic Chunking**.

*   **Splitter**: Use headers (`#`, `##`, `###`) to respect document structure.
*   **Overlap**: 50-100 tokens.
*   **Metadata**: Tag each chunk with its source filename and section header.

## Checklist for Implementation Agent

1.  [ ] **Install Dependencies**: `pgvector`, `openai`.
2.  [ ] **Database**: Create `server/models_rag.py` and run Alembic migration.
3.  [ ] **Core Logic**: Implement `rag/encoder.py` and `rag/retriever.py`.
4.  [ ] **Pipeline**: Update `llm/pipeline.py` to call retriever when `analysis.need_kb` is True.
5.  [ ] **Prompts**: Update `DECIDE` and `GENERATE` prompts to ingest retrieved text.
6.  [ ] **Testing**: Create `tests/test_rag.py` to verify ingestion and retrieval accuracy.
