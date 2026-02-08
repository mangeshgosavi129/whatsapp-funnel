import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

print("✅ Starting RAG Import Verification...")

try:
    print("Importing schemas...")
    from llm.schemas import PipelineInput, EyesOutput, BrainOutput
    print("✅ Schemas imported.")

    print("Importing enums...")
    from server.enums import ConversationStage
    print("✅ Enums imported.")

    print("Importing knowledge service...")
    from llm.knowledge import search_knowledge, ingest_knowledge
    print("✅ Knowledge service imported.")

    print("Importing pipeline steps...")
    from llm.steps.eyes import run_eyes
    from llm.steps.brain import run_brain
    from llm.pipeline import run_pipeline
    print("✅ Python files imported.")
    
    print("Importing API routes...")
    from server.routes.knowledge import router as knowledge_router
    print("✅ Knowledge router imported.")

    print("🎉 All RAG modules imported successfully!")

except Exception as e:
    print(f"❌ Import Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
