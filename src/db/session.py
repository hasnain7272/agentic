"""
Database Session Management - Async SQLAlchemy Session

Provides async database session factory and dependency for FastAPI.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool

from src.config.settings import get_settings
from src.db.models import Base


class DatabaseManager:
    """Manages database engine and session lifecycle."""
    
    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
    
    def initialize(self) -> None:
        """Initialize engine and session factory."""
        settings = get_settings()
        
        self._engine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            poolclass=NullPool if "sqlite" in settings.database_url else None,
            pool_pre_ping=True,
        )
        
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    
    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self.initialize()
        return self._engine
    
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            self.initialize()
        return self._session_factory
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session with automatic cleanup."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def create_tables(self) -> None:
        """Create all tables - use for init/testing."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self) -> None:
        """Drop all tables - use for testing."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def close(self) -> None:
        """Close engine connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global instance
db_manager = DatabaseManager()


# FastAPI dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session."""
    async with db_manager.session() as session:
        yield session


# Initialize on import (for backwards compatibility)
def init_db() -> None:
    """Initialize database - call on startup."""
    db_manager.initialize()