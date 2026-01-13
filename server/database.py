from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from server.config import config

# =========================================================
# DATABASE SETUP
# =========================================================
engine = create_engine(
    config.DATABASE_URL,
    pool_size=10,        # per Uvicorn worker
    max_overflow=5,      # temporary burst capacity
    pool_pre_ping=True,  # detect dead connections
    pool_recycle=1800,   # avoid stale connections
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
