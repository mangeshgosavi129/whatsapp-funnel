from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil
import os
import tempfile
from server.dependencies import get_db, get_auth_context
from server.schemas import (
    AuthContext, 
    KnowledgeSearchRequest, 
    KnowledgeItemOut
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
                    title_prefix=title_prefix
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
