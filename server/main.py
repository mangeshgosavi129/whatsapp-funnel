from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from server.database import engine, Base
from server.routes import router
from sqlalchemy import inspect
from logging_config import setup_logging
import time
import logging

logger = logging.getLogger("server")

# Configure logging
setup_logging()

# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(title="Whatsapp-Bot")

origins = [
    "https://wabot-sigma.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],      # IMPORTANT - allows OPTIONS
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log details
    log_msg = f"{request.method} {request.url.path} - Status: {response.status_code} - Time: {duration:.3f}s"
    
    if 200 <= response.status_code < 400:
        logger.info(log_msg)
    elif 400 <= response.status_code < 500:
        logger.warning(log_msg)
    else:
        logger.error(log_msg)
        
    return response


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