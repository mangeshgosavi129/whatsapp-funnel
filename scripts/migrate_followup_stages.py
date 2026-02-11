"""
One-time data migration script to convert existing followup stage values
to their appropriate sales funnel stage.

Run this script once after deploying the code changes that remove
FOLLOWUP, FOLLOWUP_10M, FOLLOWUP_3H, FOLLOWUP_6H from ConversationStage.

Usage:
    python scripts/migrate_followup_stages.py
"""
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal
from server.models import Conversation
from sqlalchemy import text


def migrate_followup_stages():
    """Convert all followup stage values to 'greeting' (safe fallback)."""
    db = SessionLocal()
    
    try:
        followup_stages = ["followup", "followup_10m", "followup_3h", "followup_6h"]
        
        # Count affected rows first
        result = db.execute(
            text("SELECT COUNT(*) FROM conversations WHERE stage IN :stages"),
            {"stages": tuple(followup_stages)}
        )
        count = result.scalar()
        
        if count == 0:
            print("No conversations with followup stages found. Nothing to migrate.")
            return
        
        print(f"Found {count} conversations with followup stages. Migrating to 'greeting'...")
        
        # Update all followup stages to 'greeting'
        db.execute(
            text("UPDATE conversations SET stage = 'greeting' WHERE stage IN :stages"),
            {"stages": tuple(followup_stages)}
        )
        
        db.commit()
        print(f"✅ Successfully migrated {count} conversations from followup stages to 'greeting'.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_followup_stages()
