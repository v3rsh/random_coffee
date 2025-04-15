import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from database.models import Base, Interest
from database.interests_data import DEFAULT_INTERESTS
from config import DATABASE_URL

logger = logging.getLogger(__name__)

async def init_db():
    """
    Инициализация базы данных: создание таблиц и заполнение начальными данными
    """
    # Создаем асинхронный движок SQLAlchemy
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # Создаем все таблицы из Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем асинхронную сессию
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Заполняем таблицу интересов
    async with async_session() as session:
        # Проверяем, есть ли уже интересы в базе
        result = await session.execute(select(Interest).limit(1))
        interests_exist = result.scalars().first() is not None
        
        if not interests_exist:
            logger.info("Заполняем таблицу интересов...")
            for interest_data in DEFAULT_INTERESTS:
                interest = Interest(
                    name=interest_data["name"],
                    emoji=interest_data["emoji"]
                )
                session.add(interest)
            await session.commit()
            logger.info(f"Добавлено {len(DEFAULT_INTERESTS)} интересов в базу данных")
        else:
            logger.info("Таблица интересов уже заполнена")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_db()) 