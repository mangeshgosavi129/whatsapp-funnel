"""
Alembic environment configuration.

Loads DATABASE_URL from .env.dev and registers pgvector/TSVECTOR types
so that autogenerate correctly handles all model columns.
"""

import os
from pathlib import Path
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Load .env.dev (same logic as server/config.py) ───────────────
env_path = Path(__file__).resolve().parent.parent / ".env.dev"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# ── Alembic Config ───────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from environment
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", ""))

# Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import models so autogenerate can see them ───────────────────
from server.database import Base          # noqa: E402
import server.models                      # noqa: E402, F401  — side-effect import

target_metadata = Base.metadata

# ── Register custom column types for pgvector + tsvector ─────────
from alembic import op as _              # noqa: E402, F401
from pgvector.sqlalchemy import Vector   # noqa: E402
from sqlalchemy.dialects.postgresql import TSVECTOR  # noqa: E402


def render_item(type_, obj, autogen_context):
    """Custom renderer so autogenerate emits correct code for
    Vector and TSVECTOR columns."""
    if type_ == "type":
        if isinstance(obj, Vector):
            autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
            return f"Vector({obj.dim})"
        # TSVECTOR is already importable from the dialect but needs
        # an explicit import line in generated migrations.
        if isinstance(obj, TSVECTOR):
            autogen_context.imports.add(
                "from sqlalchemy.dialects.postgresql import TSVECTOR"
            )
            return "TSVECTOR()"
    # Return False to use the default rendering for everything else
    return False


# ── Offline mode ─────────────────────────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ──────────────────────────────────────────────────
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
