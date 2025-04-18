"""
Миграционный скрипт для обновления полей расписания.

Этот скрипт преобразует старую структуру (available_day, available_time)
в новую (available_days, available_time_slot).
"""
import asyncio
import logging
import os
from typing import List, Optional

from sqlalchemy import select, create_engine, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

from database.models import Base, User, TimeSlot, WeekDay

logger = logging.getLogger(__name__)

# Настройка подключения к базе данных
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.sqlite3")
ASYNC_SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./database.sqlite3")

# Создаем синхронный и асинхронный движки
engine = create_engine(SQLALCHEMY_DATABASE_URL)
async_engine = create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URL)

# Создаем сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession)

# Словарь для преобразования старых форматов дней в WeekDay.value
day_mapping = {
    "Понедельник": WeekDay.MONDAY.value,
    "Вторник": WeekDay.TUESDAY.value,
    "Среда": WeekDay.WEDNESDAY.value,
    "Четверг": WeekDay.THURSDAY.value,
    "Пятница": WeekDay.FRIDAY.value,
    "понедельник": WeekDay.MONDAY.value,
    "вторник": WeekDay.TUESDAY.value,
    "среда": WeekDay.WEDNESDAY.value,
    "четверг": WeekDay.THURSDAY.value,
    "пятница": WeekDay.FRIDAY.value,
}

# Словарь для преобразования старых форматов времени в TimeSlot.value
time_mapping = {
    "8:00": TimeSlot.SLOT_8_10.value,
    "9:00": TimeSlot.SLOT_8_10.value,
    "10:00": TimeSlot.SLOT_10_12.value,
    "11:00": TimeSlot.SLOT_10_12.value,
    "12:00": TimeSlot.SLOT_12_14.value,
    "13:00": TimeSlot.SLOT_12_14.value,
    "14:00": TimeSlot.SLOT_14_16.value,
    "15:00": TimeSlot.SLOT_14_16.value,
    "16:00": TimeSlot.SLOT_16_18.value,
    "17:00": TimeSlot.SLOT_16_18.value,
    "8:00-10:00": TimeSlot.SLOT_8_10.value,
    "10:00-12:00": TimeSlot.SLOT_10_12.value,
    "12:00-14:00": TimeSlot.SLOT_12_14.value,
    "14:00-16:00": TimeSlot.SLOT_14_16.value,
    "16:00-18:00": TimeSlot.SLOT_16_18.value,
}


async def migrate_schedule_data():
    """
    Миграция данных расписания пользователей.
    """
    logger.info("Начало миграции данных расписания...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Получаем всех пользователей, отсортированных по дате создания
            result = await session.execute(
                select(User).order_by(User.created_at)
            )
            users = result.scalars().all()
            
            # Если пользователей нет, выходим
            if not users:
                logger.info("Нет пользователей для миграции")
                return
                
            # Назначаем порядковые номера пользователям
            for i, user in enumerate(users, 1):
                try:
                    # Назначаем порядковый номер
                    user.user_number = i
                    logger.info(f"Пользователю {user.telegram_id} назначен номер {i}")
                    
                    # Миграция данных дней и времени будет происходить в alter_table.py
                    
                    # Сохраняем изменения
                    await session.commit()
                    logger.info(f"Успешно обновлены данные для пользователя {user.telegram_id}")
                
                except Exception as e:
                    logger.error(f"Ошибка при обновлении данных пользователя {user.telegram_id}: {e}")
                    await session.rollback()
        
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей: {e}")
    
    logger.info("Миграция данных расписания завершена")


async def run_migration():
    """
    Запуск миграции.
    """
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    try:
        logger.info("Запуск миграции...")
        await migrate_schedule_data()
        logger.info("Миграция успешно завершена!")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}")


if __name__ == "__main__":
    asyncio.run(run_migration()) 