import sys
import os

# Add the project root to sys.path to import server modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from server.database import engine

def migrate():
    print("Running migration for templates table...")
    with engine.connect() as conn:
        # Add category column
        try:
            conn.execute(text("ALTER TABLE templates ADD COLUMN category VARCHAR(50)"))
            print("Added category column")
        except Exception as e:
            print(f"Category column might already exist: {e}")
            conn.rollback()

        # Add language column
        try:
            conn.execute(text("ALTER TABLE templates ADD COLUMN language VARCHAR(20)"))
            print("Added language column")
        except Exception as e:
            print(f"Language column might already exist: {e}")
            conn.rollback()

        # Add components column
        try:
            conn.execute(text("ALTER TABLE templates ADD COLUMN components JSON"))
            print("Added components column")
        except Exception as e:
            print(f"Components column might already exist: {e}")
            conn.rollback()

        # Make content nullable
        try:
            conn.execute(text("ALTER TABLE templates ALTER COLUMN content DROP NOT NULL"))
            print("Made content column nullable")
        except Exception as e:
            print(f"Failed to modify content column: {e}")
            conn.rollback()
            
        conn.commit()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
