"""
app/database.py — Async database session management.

Creates an async SQLAlchemy engine + session factory.  The ``get_db``
dependency is injected into FastAPI routes that need database access.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import get_settings

settings = get_settings()

# ── Async engine (connection pool to PostgreSQL) ──
engine = create_async_engine(
    settings.sqlalchemy_database_url,
    connect_args=settings.sqlalchemy_connect_args,
    echo=False,          # Set True for SQL statement logging during debug
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
)

# ── Session factory — produces AsyncSession instances ──
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Declarative base for ORM models ──
Base = declarative_base()


async def init_db() -> None:
    """Create all tables and apply lightweight migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # ── Lightweight column migrations (no Alembic needed) ──
        # Add audio_language column if it doesn't exist yet
        await conn.execute(
            __import__("sqlalchemy").text(
                "ALTER TABLE moderation_records_v2 "
                "ADD COLUMN IF NOT EXISTS audio_language VARCHAR(10)"
            )
        )


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency — yields a database session per request."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
