import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, async_scoped_session
from sqlalchemy.orm import sessionmaker

from database.models import Base

# Получаем URL базы данных из переменных окружения
# По умолчанию используем SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./database.sqlite3")

# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    # Следующие параметры важны для SQLite
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    # Общие настройки для пула соединений
    pool_pre_ping=True,
    pool_recycle=3600
)

# Создаем фабрику сессий
async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


def get_session():
    """
    Возвращает фабрику сессий.
    """
    return async_session_maker


async def init_db():
    """
    Инициализация базы данных (создание всех таблиц).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 