"""
app/database.py
Engine async SQLAlchemy + dependency get_db.
Compatible JSONB en PostgreSQL y JSON en SQLite para tests.
"""
from typing import AsyncGenerator
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.postgresql import JSONB
from app.config import get_settings

settings = get_settings()

# ------------------------------
# Función para usar JSONB en PostgreSQL y JSON en SQLite
# ------------------------------
def JSONB_compat():
    if settings.database_url.startswith("sqlite"):
        return sa.JSON  # SQLite usa JSON normal
    else:
        return JSONB  # PostgreSQL usa JSONB
# ------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,   # SQL en consola solo en dev
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,                # reconecta si la conexión cayó
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency de FastAPI — provee una sesión por request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()