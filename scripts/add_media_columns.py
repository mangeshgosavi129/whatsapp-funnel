"""
Migration: Add media columns to messages table.

Run with: python scripts/add_media_columns.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from server.database import SessionLocal

def migrate():
    db = SessionLocal()
    try:
        # Add media_type column
        db.execute(text("""
            ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS media_type VARCHAR(20) DEFAULT NULL
        """))
        
        # Add media_url column
        db.execute(text("""
            ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS media_url VARCHAR(500) DEFAULT NULL
        """))
        
        # Add media_filename column
        db.execute(text("""
            ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS media_filename VARCHAR(255) DEFAULT NULL
        """))
        
        db.commit()
        print("✅ Migration successful: media_type, media_url, media_filename columns added to messages table")
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
