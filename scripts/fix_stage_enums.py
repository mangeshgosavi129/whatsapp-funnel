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
        
        print(f"Valid stages in code (lowercase): {valid_stages}")
        
        # 1. Standardize case for all existing stages
        print("Standardizing all stages to lowercase...")
        db.execute(text("UPDATE conversations SET stage = LOWER(CAST(stage AS TEXT)) WHERE stage IS NOT NULL"))
        db.execute(text("UPDATE leads SET conversation_stage = LOWER(CAST(conversation_stage AS TEXT)) WHERE conversation_stage IS NOT NULL"))
        db.commit() # Commit this first to ensure LOWER worked

        # 2. Identify and fix any stages that are STILL not valid
        print("Mapping all invalid/legacy stages to 'greeting'...")
        
        # This covers: followup_*, ghosted (uppercase), etc.
        # Everything that isn't exactly in our valid_stages list
        db.execute(
            text("UPDATE conversations SET stage = :target WHERE CAST(stage AS TEXT) NOT IN :valid OR stage IS NULL"),
            {"target": target_fallback, "valid": tuple(valid_stages)}
        )
        db.execute(
            text("UPDATE leads SET conversation_stage = :target WHERE CAST(conversation_stage AS TEXT) NOT IN :valid OR conversation_stage IS NULL"),
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
