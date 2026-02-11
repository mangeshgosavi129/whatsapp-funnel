"""
Robust migration script to clean up invalid conversation stages.
Maps all variants of 'followup' stages to 'greeting'.
"""
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal
from sqlalchemy import text

def fix_all_stages():
    db = SessionLocal()
    try:
        # Valid stages from Enum
        from server.enums import ConversationStage
        valid_stages = [s.value for s in ConversationStage]
        target_fallback = "greeting"
        
        print(f"Valid stages in code: {valid_stages}")
        
        # 1. Standardize case for all existing stages
        print("Standardizing all stages to lowercase...")
        # Note: We must cast back to ::conversationstage for PostgreSQL native enums
        db.execute(text("UPDATE conversations SET stage = CAST(LOWER(CAST(stage AS TEXT)) AS conversationstage) WHERE stage IS NOT NULL"))
        db.execute(text("UPDATE leads SET conversation_stage = CAST(LOWER(CAST(conversation_stage AS TEXT)) AS conversationstage) WHERE conversation_stage IS NOT NULL"))
        db.commit()

        # 2. Identify and fix any stages that are STILL not valid (legacy stages)
        print("Mapping all invalid/legacy stages to 'greeting'...")
        db.execute(
            text("UPDATE conversations SET stage = CAST(:target AS conversationstage) WHERE CAST(stage AS TEXT) NOT IN :valid OR stage IS NULL"),
            {"target": target_fallback, "valid": tuple(valid_stages)}
        )
        db.execute(
            text("UPDATE leads SET conversation_stage = CAST(:target AS conversationstage) WHERE CAST(conversation_stage AS TEXT) NOT IN :valid OR conversation_stage IS NULL"),
            {"target": target_fallback, "valid": tuple(valid_stages)}
        )

        db.commit()
        print("✅ Production-grade standardization complete.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    fix_all_stages()
