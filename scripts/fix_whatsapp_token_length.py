import sys
import os

# Add the project root to sys.path to import server modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from server.database import engine

def fix_token_length():
    print("Standardizing whatsapp_integrations.access_token to TEXT...")
    
    with engine.connect() as conn:
        try:
            # PostgreSQL command to change column type
            conn.execute(text("ALTER TABLE whatsapp_integrations ALTER COLUMN access_token TYPE TEXT;"))
            conn.commit()
            print("Successfully altered access_token to TEXT")
        except Exception as e:
            print(f"Failed to alter column: {e}")

if __name__ == "__main__":
    fix_token_length()
