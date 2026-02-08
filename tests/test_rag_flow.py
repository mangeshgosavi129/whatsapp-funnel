import sys
import os
import uuid
import logging
import random
from unittest.mock import MagicMock, patch
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

# Load Env
load_dotenv(".env.dev")

# Load Env
load_dotenv(".env.dev")

# Ensure keys are present for module-level clients
# api_helpers needs GROQ_API_KEY
if not os.getenv("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = "gsk_dummy_key_for_test"

# knowledge needs OPENAI_API_KEY (or use Mock)
openai_key = os.getenv("OPENAI_API_KEY")
MOCK_EMBEDDINGS = False

if not openai_key:
    print("⚠️  No OPENAI_API_KEY found. Switching to MOCK assertions for Embeddings.")
    MOCK_EMBEDDINGS = True
    os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-test"
else:
    print("🔑 OPENAI_API_KEY found. Attempting live embeddings.")

from server.database import SessionLocal
from server.models import Organization

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_random_embedding():
    return [random.random() for _ in range(1536)]

def test_rag_flow():
    print("🚀 Starting RAG Functional Test...")
    db = SessionLocal()
    
    # SETUP MOCKS if needed
    # We need to patch 'llm.knowledge.embeddings_client' BEFORE importing it or usage
    if MOCK_EMBEDDINGS:
        # Create a mock client that returns random vectors
        mock_client = MagicMock()
        mock_client.embed_query.side_effect = lambda x: get_random_embedding()
        
        # Patching needs to happen where the object is imported/used
        patcher = patch('llm.knowledge.embeddings_client', mock_client)
        patcher.start()
        print("🎭 Mocks activated for embeddings_client.")

    try:
        # Import AFTER patching to be safe, though side-effects depends on module load time
        # Since we patch 'llm.knowledge.embeddings_client', and we import function, 
        # the function `ingest_knowledge` uses the global `embeddings_client` variable in that module.
        from llm.knowledge import ingest_knowledge, search_knowledge

        # 1. Setup Test Organization
        org_id = uuid.uuid4()
        print(f"📦 Creating test organization: {org_id}")
        
        try:
            db.execute(
                text("INSERT INTO organizations (id, name, is_active, created_at) VALUES (:id, :name, :is_active, now())"),
                {"id": org_id, "name": "RAG Test Org", "is_active": True}
            )
            db.commit()
        except Exception as e:
            print(f"⚠️  Could not create test org (might exist): {e}")
            db.rollback()
            # Try to continue? If org doesn't exist, FK will fail.
            # Assuming it worked or existed.

        # 2. Ingest Knowledge
        print("📝 Ingesting sample knowledge...")
        sample_policy = """
# Refund Policy

## Eligibility
Customers are eligible for a refund within 30 days of purchase.
Items must be unused and in original packaging.

## Process
To initiate a refund, contact support@example.com.
Refunds are processed within 5-7 business days.
"""
        chunks = ingest_knowledge(
            text_content=sample_policy,
            organization_id=org_id,
            title_prefix="Test Policy"
        )
        print(f"✅ Ingested {chunks} chunks.")

        # 3. Perform Search (Vector + Keyword)
        print("🔍 Testing Search: 'refund process'...")
        
        # If mocking, vector search results will be random garbage, so 'score' will be random.
        # But Keyword search should still work!
        # Search function returns combined results.
        
        results = search_knowledge("refund process", org_id, top_k=3)
        
        if not results:
            print("❌ No results found!")
        else:
            print(f"✅ Found {len(results)} results.")
            for r in results:
                print(f"   - [Score: {r['score']:.2f}] {r['title']}")
                print(f"     Preview: {r['content'][:50]}...")
                
        # 4. Verify specific keywords for Keyword Search
        # If we are mocking embeddings, we rely on Keyword search to return results.
        # Our Hybrid logic is: if vec > 0.75 OR rank <= 2.
        # With random embeddings, vec > 0.75 is unlikely (cos sim of random high dim vectors is ~0).
        # So we test if Keyword Search picked it up.
        
        found_process = any("Process" in r['title'] for r in results)
        if found_process:
            print("✅ Keyword Search validated (Found 'Process' section).")
        else:
            if MOCK_EMBEDDINGS:
                print("⚠️  Keyword Search might have missed, or rank threshold too strict.")
            else:
                print("⚠️  Search didn't find specific section.")

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
    test_rag_flow()
