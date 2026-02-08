import sys
from sqlalchemy import create_engine, text
from server.config import config

def check_vector():
    try:
        engine = create_engine(config.DATABASE_URL)
        with engine.connect() as conn:
            # Try to cast to vector
            conn.execute(text("SELECT '[1,2,3]'::vector"))
            print("SUCCESS: pgvector is installed and working.")
    except Exception as e:
        print(f"FAILURE: pgvector check failed.\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_vector()
