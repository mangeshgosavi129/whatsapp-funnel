import sys
import os

# Add the project root to sys.path to import server modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from server.database import engine

def migrate_enums():
    print("Running migration for templatestatus enum...")
    # SQL to add values to an existing enum. 
    # Note: ALTER TYPE ... ADD VALUE cannot run inside a transaction block in some Postgres versions.
    # We will try to run them independently.
    
    new_values = ["draft", "submitted", "approved", "rejected"]
    
    with engine.connect() as conn:
        # We need to set isolation level to AUTOCOMMIT if we want to run ALTER TYPE ADD VALUE
        conn.detach() # Explicitly detach to ensure clean state if needed, but conn.execution_options(isolation_level="AUTOCOMMIT") is better
        
    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    
    with autocommit_engine.connect() as conn:
        for val in new_values:
            try:
                # PostgreSQL requires single quotes for the value
                conn.execute(text(f"ALTER TYPE templatestatus ADD VALUE '{val}'"))
                print(f"Added value '{val}' to templatestatus enum")
            except Exception as e:
                # If value already exists, Postgres will throw an error
                if "already exists" in str(e).lower():
                    print(f"Value '{val}' already exists in templatestatus enum")
                else:
                    print(f"Failed to add '{val}': {e}")

    print("Enum migration complete!")

if __name__ == "__main__":
    migrate_enums()
