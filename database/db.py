import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from database.models import Base

# Получаем URL базы данных из переменных окружения
# По умолчанию используем SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///database.sqlite3")

# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    # Следующие параметры важны для SQLite
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Создаем фабрику сессий
async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Асинхронный генератор для получения сессии базы данных.
    """
    async with async_session_maker() as session:
        yield session


async def init_db():
    """
    Инициализация базы данных (создание всех таблиц).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 