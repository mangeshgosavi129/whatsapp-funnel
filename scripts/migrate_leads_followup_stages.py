"""
One-time data migration script to convert existing followup stage values
in the LEADS table to their appropriate sales funnel stage.

Run this script to fix 500 errors caused by leads having legacy 'followup' stages
that are no longer in the ConversationStage enum.

Usage:
    python scripts/migrate_leads_followup_stages.py
"""
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal
from server.models import Lead
from sqlalchemy import text


def migrate_leads_followup_stages():
    """Convert all lead conversation_stage values to 'greeting' (safe fallback)."""
    db = SessionLocal()
    
    try:
        followup_stages = ["followup", "followup_10m", "followup_3h", "followup_6h"]
        
        # Count affected rows first (cast to text to avoid enum validation error)
        result = db.execute(
            text("SELECT COUNT(*) FROM leads WHERE CAST(conversation_stage AS TEXT) IN :stages"),
            {"stages": tuple(followup_stages)}
        )
        count = result.scalar()
        
        if count == 0:
            print("No leads with followup stages found. Nothing to migrate.")
            return
        
        print(f"Found {count} leads with followup stages. Migrating to 'greeting'...")
        
        # Update all followup stages to 'greeting'
        db.execute(
            text("UPDATE leads SET conversation_stage = 'greeting' WHERE CAST(conversation_stage AS TEXT) IN :stages"),
            {"stages": tuple(followup_stages)}
        )
        
        db.commit()
        print(f"✅ Successfully migrated {count} leads from followup stages to 'greeting'.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_leads_followup_stages()
