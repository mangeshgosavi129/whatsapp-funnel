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
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
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

    inspector_before = inspect(engine)
    existing_tables = inspector_before.get_table_names()

    Base.metadata.create_all(bind=engine)

    inspector_after = inspect(engine)  # ✅ IMPORTANT: new inspector instance
    updated_tables = inspector_after.get_table_names()

    new_tables = set(updated_tables) - set(existing_tables)

    if new_tables:
        print(f"✅ Created new tables: {sorted(new_tables)}")
    else:
        print(f"ℹ️ No new tables created. Tables now: {updated_tables}")