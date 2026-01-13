from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.database import engine, Base
from server.routes import router
from sqlalchemy import inspect

# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(title="Whatsapp-Bot")

origins = [
    "http://localhost:8001",
    "http://localhost:5050",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],      # IMPORTANT - allows OPTIONS
    allow_headers=["*"],
)

# Include API Router
app.include_router(router)

# =========================================================
# AUTO-CREATE TABLES ON STARTUP
# =========================================================
@app.on_event("startup")
def init_database():
    print("🔄 Checking database tables...")
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    Base.metadata.create_all(bind=engine)

    new_tables = set(inspector.get_table_names()) - set(existing_tables)
    if new_tables:
        print(f"✅ Created new tables: {new_tables}")
    else:
        print(f"ℹ️ All tables exist: {existing_tables}")
