
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv(".env.dev")

# Import knowledge service components
from llm.knowledge import _get_doc_embedder, _process_vector, EMBEDDING_DIM

def test_end_to_end_gemini():
    print("🧪 Testing End-to-End Gemini Embedding (with MRL)...")
    
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        print("❌ SKIPPED: No GOOGLE_API_KEY found.")
        return

    try:
        # 1. Get Embedder
        embedder = _get_doc_embedder()
        print(f"🔹 Model: {embedder.model}")
        
        # 2. Embed Query
        text = "This is a test of the Matryoshka Representation Learning adaptation."
        print("🔹 Requesting embedding...")
        raw_vec = embedder.embed_query(text)
        print(f"🔸 Raw Vector Length: {len(raw_vec)}")
        
        # 3. Process
        processed_vec = _process_vector(raw_vec, EMBEDDING_DIM)
        print(f"🔹 Processed Vector Length: {len(processed_vec)}")
        
        # 4. Assert
        if len(processed_vec) != 768:
             print(f"❌ FAILED: Expected 768, got {len(processed_vec)}")
             sys.exit(1)
             
        if len(raw_vec) == 768:
            print("ℹ️  Note: API returned 768 directly (Efficiency win!).")
        else:
            print("ℹ️  Note: API returned larger vector, sliced locally.")
            
        print("✅ End-to-End Verification Successful!")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_end_to_end_gemini()
