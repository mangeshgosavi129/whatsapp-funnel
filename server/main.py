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
# AUTO-MIGRATE ON STARTUP
# =========================================================
@app.on_event("startup")
def run_migrations():
    from alembic.config import Config
    from alembic import command
    
    print("🔄 Running database migrations...")
    try:
        # Create Alembic configuration object
        # Assumes alembic.ini is in the root (parent of server/)
        alembic_cfg = Config("alembic.ini")
        
        # Run the migration
        command.upgrade(alembic_cfg, "head")
        print("✅ Database migrations completed successfully.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        # Build might fail if DB isn't ready, but we don't want to crash the app immediately in all cases
        # relying on subsequent health checks or retries
        logger.error(f"Migration failed during startup: {e}")