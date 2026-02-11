"""
Debug script to list distinct stage values in DB.
"""
import os
import sys
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal

def check_stages():
    db = SessionLocal()
    try:
        print("Checking distinct stages in 'conversations' table...")
        result = db.execute(text("SELECT DISTINCT stage FROM conversations"))
        stages = [row[0] for row in result]
        print(f"Conversation stages found: {stages}")

        print("\nChecking distinct conversation_stage in 'leads' table...")
        result = db.execute(text("SELECT DISTINCT conversation_stage FROM leads"))
        lead_stages = [row[0] for row in result]
        print(f"Lead conversation_stages found: {lead_stages}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_stages()
