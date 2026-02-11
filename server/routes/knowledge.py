from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil
import os
import uuid
import tempfile
from server.dependencies import get_db, get_auth_context
from server.schemas import (
    AuthContext, 
    KnowledgeSearchRequest, 
    KnowledgeItemOut,
    KnowledgeMetadataOut
)
import llm.knowledge as knowledge_service

router = APIRouter()

@router.post("/ingest")
async def ingest_knowledge(
    file: UploadFile = File(...),
    title_prefix: Optional[str] = Form(""),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Ingest a document (PDF or Markdown) into the RAG system.
    """
    try:
        filename = file.filename.lower()
        chunks_count = 0
        
        if filename.endswith(".pdf"):
            # Save upload to temp file for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
            
            try:
                chunks_count = knowledge_service.ingest_pdf(
                    file_path=tmp_path,
                    organization_id=auth.organization_id,
                    title_prefix=title_prefix,
                    filename=filename
                )
            finally:
                os.remove(tmp_path)
                
        elif filename.endswith(".md") or filename.endswith(".txt"):
            content = (await file.read()).decode("utf-8")
            chunks_count = knowledge_service.ingest_knowledge(
                text_content=content,
                organization_id=auth.organization_id,
                title_prefix=title_prefix
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use .pdf or .md")
            
        return {"success": True, "chunks_created": chunks_count, "file": filename}
    except Exception as e:
        print(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=List[KnowledgeItemOut])
def search_knowledge(
    payload: KnowledgeSearchRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Test endpoint for Hybrid RRF Search.
    """
    try:
        results = knowledge_service.search_knowledge(
            query=payload.query,
            organization_id=auth.organization_id,
            top_k=payload.top_k
        )
        return [
            KnowledgeItemOut(
                id=uuid.UUID(r["id"]) if "id" in r else uuid.UUID("00000000-0000-0000-0000-000000000000"),
                title=r["title"],
                content=r["content"],
                score=r["score"]
            )
            for r in results
        ]
    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[KnowledgeMetadataOut])
def list_knowledge(
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db)
):
    """
    List all knowledge items for the organization.
    """
    try:
        from server.models import KnowledgeItem
        from server.models import KnowledgeItem
        items = db.query(KnowledgeItem).filter(
            KnowledgeItem.organization_id == auth.organization_id
        ).order_by(KnowledgeItem.created_at.desc()).all()
        
        # Group by doc_id (new items) or title (legacy items with same prefix)
        grouped_items = {}
        
        for item in items:
            # Determine grouping key
            doc_id = None
            source = None
            if item.metadata_ and "doc_id" in item.metadata_:
                doc_id = item.metadata_["doc_id"]
                key = f"doc_{doc_id}"
                source = item.metadata_.get("source")
            else:
                # Legacy fallback: use title as key
                # This might group unintended items if titles are identical, 
                # but better than showing 50 chunks.
                key = f"title_{item.title}"

            if key not in grouped_items:
                grouped_items[key] = {
                    "id": item.id, # Use newest item's ID as representative
                    "title": item.title,
                    "created_at": item.created_at,
                    "doc_id": uuid.UUID(doc_id) if doc_id else None,
                    "chunk_count": 0,
                    "source": source
                }
            
            grouped_items[key]["chunk_count"] += 1
            
        return list(grouped_items.values())
    except Exception as e:
        print(f"List error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{item_id}")
def delete_knowledge(
    item_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db)
):
    """
    Delete a specific knowledge item.
    """
    try:
        from server.models import KnowledgeItem
        from server.models import KnowledgeItem
        
        # Check if this item is part of a document
        target_item = db.query(KnowledgeItem).filter(
            KnowledgeItem.id == item_id,
            KnowledgeItem.organization_id == auth.organization_id
        ).first()
        
        if not target_item:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
            
        # If it has a doc_id, delete all items with that doc_id
        if target_item.metadata_ and "doc_id" in target_item.metadata_:
            doc_id = target_item.metadata_["doc_id"]
            # Delete all chunks with this doc_id
            # Fetch all items first to avoid dialect specific JSON operators if possible, 
            # or use python-side filtering if volume is low, but better to use SQL.
            # Using cast for safety with standard SQLAlchemy JSON
            from sqlalchemy import cast, String
            
            # Note: We can't easily use .astext with generic JSON, so we rely on python loop for safety 
            # OR we try the filter. Given chunks are usually < 100, we can fetch all for org and filter IPs?
            # No, that's inefficient.
            # Let's use the explicit cast if we can.
            
            # Alternative: Since we know the doc_id, we can find items where metadata_['doc_id'] == doc_id
            # For Postgres, json_field['key'].astext works if using PG dialect, but we used generic JSON.
            # Let's try to trust the ORM or use a raw SQL delete for this specific condition if needed.
            # But actually, explicit cast is standard:
            
            stmt = db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == auth.organization_id,
                cast(KnowledgeItem.metadata_['doc_id'], String) == f'"{doc_id}"' # JSON stringifies values
            )
            # Wait, cast(json['key'], String) might result in '"value"' (quoted) if strictly JSON.
            # If doc_id was stored as string "uuid", it looks like "uuid" in JSON.
            
            # Use a simpler approach: Iterate and delete. It's robust and volume is low.
            items_to_delete = db.query(KnowledgeItem).filter(
                KnowledgeItem.organization_id == auth.organization_id
            ).all()
            
            for i in items_to_delete:
                if i.metadata_ and i.metadata_.get("doc_id") == doc_id:
                    db.delete(i)
            
        else:
            # Legacy or single item delete
            db.delete(target_item)
            
        db.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
