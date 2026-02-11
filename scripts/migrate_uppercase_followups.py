"""
Migration script to convert UPPERCASE 'FOLLOWUP' stage values to 'greeting'.
Targets both 'conversations' and 'leads' tables.

Usage:
    python scripts/migrate_uppercase_followups.py
"""
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal
from sqlalchemy import text


def migrate_uppercase_followups():
    """Convert UPPERCASE followup stage values to 'greeting'."""
    db = SessionLocal()
    
    try:
        # Include both uppercase and lowercase variants just in case
        followup_stages = [
            "FOLLOWUP", "FOLLOWUP_10M", "FOLLOWUP_3H", "FOLLOWUP_6H",
            "followup", "followup_10m", "followup_3h", "followup_6h"
        ]
        
        # 1. Migrate Conversations
        print("Checking conversations...")
        result = db.execute(
            text("SELECT COUNT(*) FROM conversations WHERE CAST(stage AS TEXT) IN :stages"),
            {"stages": tuple(followup_stages)}
        )
        count = result.scalar()
        
        if count > 0:
            print(f"Found {count} conversations with followup stages. Migrating to 'GREETING'...")
            db.execute(
                text("UPDATE conversations SET stage = 'GREETING' WHERE CAST(stage AS TEXT) IN :stages"),
                {"stages": tuple(followup_stages)}
            )
            print("✅ conversations migrated.")
        else:
            print("No conversations to migrate.")

        # 2. Migrate Leads
        print("Checking leads...")
        result = db.execute(
            text("SELECT COUNT(*) FROM leads WHERE CAST(conversation_stage AS TEXT) IN :stages"),
            {"stages": tuple(followup_stages)}
        )
        count = result.scalar()
        
        if count > 0:
            print(f"Found {count} leads with followup stages. Migrating to 'GREETING'...")
            db.execute(
                text("UPDATE leads SET conversation_stage = 'GREETING' WHERE CAST(conversation_stage AS TEXT) IN :stages"),
                {"stages": tuple(followup_stages)}
            )
            print("✅ leads migrated.")
        else:
            print("No leads to migrate.")
        
        db.commit()
        print("Combined migration complete.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_uppercase_followups()
