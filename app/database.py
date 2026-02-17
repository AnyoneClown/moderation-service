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
    settings.DATABASE_URL,
    echo=False,          # Set True for SQL statement logging during debug
    pool_size=10,
    max_overflow=20,
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
    """Create all tables. Called once during application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency — yields a database session per request."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
