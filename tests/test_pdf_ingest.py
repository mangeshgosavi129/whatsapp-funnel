
import sys
import os
import uuid
import logging
from unittest.mock import MagicMock, patch
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

# Load Env
load_dotenv(".env.dev")

# Check Keys
google_key = os.getenv("GOOGLE_API_KEY")

# Mocking Setup
# FORCE MOCKS for verifying Logic/DB flow independent of API validity
MOCK_EMBEDDINGS = True
# if not google_key:
#    print("⚠️  No GOOGLE_API_KEY found. Switching to MOCK assertions.")
#    MOCK_EMBEDDINGS = True
if MOCK_EMBEDDINGS:
    print("⚠️  Forcing MOCK assertions for Embeddings to verify pipeline logic.")
    # Ensure key is set so client init doesn't crash before patch
    os.environ["GOOGLE_API_KEY"] = "dummy_key"

from server.database import SessionLocal
# Import AFTER setting dummy key if needed
from llm.knowledge import ingest_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pdf_flow():
    print("🚀 Starting PDF RAG Functional Test...")
    db = SessionLocal()
    org_id = uuid.uuid4()
    
    # SETUP MOCKS if needed
    if MOCK_EMBEDDINGS:
        # Create a mock client that returns random vectors of correct dimension (768 for Gemini text-embedding-004)
        mock_client = MagicMock()
        mock_client.embed_query.return_value = [0.1] * 768 
        
        # Patching needs to happen where the object is imported/used
        # In llm/knowledge.py, we have `embeddings_client` global variable.
        patcher = patch('llm.knowledge.embeddings_client', mock_client)
        patcher.start()
        print("🎭 Mocks activated for embeddings_client (768 dim).")

    try:
        # 1. Setup Test Org
        try:
            db.execute(
                text("INSERT INTO organizations (id, name, is_active, created_at) VALUES (:id, :name, :is_active, now())"),
                {"id": org_id, "name": "PDF Test Org", "is_active": True}
            )
            db.commit()
        except Exception as e:
            print(f"⚠️  Could not create test org: {e}")
            db.rollback()

        # 2. Ingest PDF (Mocked Reader)
        print("📝 Ingesting Mock PDF...")
        
        # We Mock PdfReader because we don't want to rely on a physical file existing
        with patch("llm.knowledge.PdfReader") as MockReader:
            # Setup Mock Page
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "This is a test PDF content.\nIt contains important information about the PDF process."
            
            # Setup Mock Reader instance
            mock_reader_instance = MockReader.return_value
            mock_reader_instance.pages = [mock_page]
            
            # Run Ingestion
            # We pass a dummy path since we mock Reader
            chunks = ingest_pdf("dummy.pdf", org_id, title_prefix="PDF Test")
            print(f"✅ Ingested {chunks} chunks.")
            
            # 3. Verify in DB
            result = db.execute(
                text("SELECT count(*) FROM knowledge_items WHERE organization_id = :id"),
                {"id": org_id}
            ).scalar()
            print(f"📊 DB Count: {result}")
            
            if result > 0:
                print("✅ Validation Successful: Data persisted to DB.")
            else:
                print("❌ Validation Failed: No data in DB.")

    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            db.execute(text("DELETE FROM knowledge_items WHERE organization_id = :id"), {"id": org_id})
            db.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
            db.commit()
            print("🧹 Cleanup complete.")
        except:
            pass
        db.close()

if __name__ == "__main__":
    test_pdf_flow()
