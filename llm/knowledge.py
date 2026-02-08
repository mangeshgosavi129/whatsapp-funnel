import os
import uuid
import math
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, select, func
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pypdf import PdfReader
from server.models import KnowledgeItem
from server.database import SessionLocal

# --- Configuration ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768

# We use two separate embedders for optimal performance as per Gemini docs
# 1. RETRIEVAL_DOCUMENT: For ingesting content
# 2. RETRIEVAL_QUERY: For searching context

_doc_embedder = None
_query_embedder = None

def _get_doc_embedder():
    """Returns embedder optimized for document storage."""
    global _doc_embedder
    if _doc_embedder is None:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GOOGLE_API_KEY is missing.")
        
        _doc_embedder = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=key,
            task_type="retrieval_document"
            # We handle dimensionality manually via MRL (slicing)
        )
    return _doc_embedder

def _get_query_embedder():
    """Returns embedder optimized for search queries."""
    global _query_embedder
    if _query_embedder is None:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GOOGLE_API_KEY is missing.")
            
        _query_embedder = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=key,
            task_type="retrieval_query"
        )
    return _query_embedder

def _process_vector(vec: List[float], target_dim: int = 768) -> List[float]:
    """
    Adapts a vector to the target dimension using Matryoshka Representation Learning (MRL).
    1. Slice to target_dim.
    2. Normalize (L2).
    """
    # 1. Slice
    if len(vec) > target_dim:
        vec = vec[:target_dim]
    
    # 2. Normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        return [x / norm for x in vec]
    return vec

def _save_splits(splits, organization_id: uuid.UUID, title_prefix: str) -> int:
    """Helper to save splits to DB."""
    db = SessionLocal()
    embedder = _get_doc_embedder()
    try:
        count = 0
        contents = [s.page_content for s in splits]
        if not contents:
            return 0
            
        try:
            # Generate Raw Embeddings
            raw_vectors = embedder.embed_documents(contents)
        except Exception as e:
            print(f"Batch embedding failed: {e}")
            raise e

        for i, split in enumerate(splits):
            content = split.page_content
            # Process Vector (Slice + Normalize)
            vector = _process_vector(raw_vectors[i], EMBEDDING_DIM)
            
            # Metadata handling
            meta_header = ""
            if split.metadata:
                meta_header = " > ".join([str(v) for k, v in split.metadata.items() if k != 'source'])
            
            full_title = f"{title_prefix}"
            if meta_header:
                full_title += f" - {meta_header}"
            
            if not full_title:
                full_title = "General Knowledge"
            
            item = KnowledgeItem(
                organization_id=organization_id,
                title=full_title,
                content=content,
                embedding=vector,
                metadata_=split.metadata
            )
            db.add(item)
            count += 1
        
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def ingest_knowledge(text_content: str, organization_id: uuid.UUID, title_prefix: str = "") -> int:
    """
    Ingests a Markdown document.
    """
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    splits = splitter.split_text(text_content)
    
    return _save_splits(splits, organization_id, title_prefix)

def ingest_pdf(file_path: str, organization_id: uuid.UUID, title_prefix: str = "") -> int:
    """
    Ingests a PDF document from a local file path.
    """
    try:
        reader = PdfReader(file_path)
        full_text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract:
                full_text += extract + "\n"
            
        # Recursive Splitter for raw text
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        splits = splitter.create_documents([full_text])
        
        return _save_splits(splits, organization_id, title_prefix)
    except Exception as e:
        print(f"Error ingesting PDF: {e}")
        raise e

def search_knowledge(
    query: str, 
    organization_id: uuid.UUID, 
    top_k: int = 5,
    vector_threshold: float = 0.65,
    keyword_rank_threshold: int = 5
) -> List[Dict]:
    """
    Performs Hybrid Search using RRF.
    """
    db = SessionLocal()
    embedder = _get_query_embedder()
    try:
        # --- 1. Vector Search ---
        raw_query_vector = embedder.embed_query(query)
        query_vector = _process_vector(raw_query_vector, EMBEDDING_DIM)
        
        vector_results = db.execute(
            select(KnowledgeItem, KnowledgeItem.embedding.cosine_distance(query_vector).label("distance"))
            .filter(KnowledgeItem.organization_id == organization_id)
            .order_by(KnowledgeItem.embedding.cosine_distance(query_vector))
            .limit(top_k)
        ).all()
        
        # --- 2. Keyword Search ---
        keyword_results = db.execute(
            select(KnowledgeItem, func.ts_rank_cd(KnowledgeItem.search_vector, func.websearch_to_tsquery('english', query)).label("rank"))
            .filter(KnowledgeItem.organization_id == organization_id)
            .filter(KnowledgeItem.search_vector.op('@@')(func.websearch_to_tsquery('english', query)))
            .order_by(text("rank DESC"))
            .limit(top_k)
        ).all()
        
        # --- 3. RRF Fusion ---
        candidates = {}
        
        for rank, (item, distance) in enumerate(vector_results, start=1):
            if item.id not in candidates:
                candidates[item.id] = {"item": item, "vec_rank": None, "key_rank": None, "vec_sim": 1 - distance}
            candidates[item.id]["vec_rank"] = rank
            
        for rank, (item, score) in enumerate(keyword_results, start=1):
            if item.id not in candidates:
                candidates[item.id] = {"item": item, "vec_rank": None, "key_rank": None, "vec_sim": 0.0}
            candidates[item.id]["key_rank"] = rank

        rrf_k = 60
        final_results = []
        
        for item_id, data in candidates.items():
            vec_part = 1 / (rrf_k + data["vec_rank"]) if data["vec_rank"] else 0
            key_part = 1 / (rrf_k + data["key_rank"]) if data["key_rank"] else 0
            rrf_score = vec_part + key_part
            
            is_strong_semantic = data["vec_sim"] > vector_threshold
            is_strong_keyword = (data["key_rank"] is not None) and (data["key_rank"] <= keyword_rank_threshold)
            
            if is_strong_semantic or is_strong_keyword:
                final_results.append({
                    "id": str(data["item"].id),
                    "content": data["item"].content,
                    "title": data["item"].title,
                    "score": rrf_score,
                    "reason": "semantic" if is_strong_semantic else "keyword"
                })
        
        final_results.sort(key=lambda x: x["score"], reverse=True)
        return final_results

    except Exception as e:
        print(f"Error in search: {e}")
        raise e
    finally:
        db.close()
