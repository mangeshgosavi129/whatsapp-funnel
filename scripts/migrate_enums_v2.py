import sys
import os

# Add the project root to sys.path to import server modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from server.database import engine

def migrate_enums_fix():
    print("Running migration for templatestatus enum (uppercase fix)...")
    
    # Adding both lowercase and uppercase to be safe, 
    # though the error shows uppercase 'DRAFT' is being sent.
    new_values = ["DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "draft", "submitted", "approved", "rejected"]
    
    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    
    with autocommit_engine.connect() as conn:
        for val in new_values:
            try:
                conn.execute(text(f"ALTER TYPE templatestatus ADD VALUE '{val}'"))
                print(f"Added value '{val}' to templatestatus enum")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"Value '{val}' already exists or case-insensitive conflict")
                else:
                    print(f"Failed to add '{val}': {e}")

    print("Enum migration (uppercase fix) complete!")

if __name__ == "__main__":
    migrate_enums_fix()
