import asyncio
import logging
import os
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.strategy import FSMStrategy
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_db, get_session, SQLiteStorage
from handlers import registration_router, feedback_router, common_router, admin_router, pairing_router
from scheduler import setup_scheduler

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Создаем экземпляр бота
bot = Bot(token=os.getenv("BOT_TOKEN"))

# ID администратора
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")


# Middleware для внедрения сессии базы данных
class DbSessionMiddleware:
    """
    Middleware для внедрения сессии базы данных в апдейты.
    """
    def __init__(self, session_maker):
        self.session_maker = session_maker
    
    async def __call__(self, handler, event, data):
        # Создаем новую сессию для каждого запроса
        session = self.session_maker()
        data["session"] = session
        
        try:
            return await handler(event, data)
        finally:
            await session.close()


async def main():
    """
    Основная функция запуска бота.
    """
    logger.info("Starting bot...")
    
    # Инициализация базы данных
    await init_db()
    logger.info("Database initialized")
    
    # Создаем хранилище состояний (SQLite)
    storage = SQLiteStorage()
    
    # Создаем диспетчер
    dp = Dispatcher(storage=storage, fsm_strategy=FSMStrategy.USER_IN_CHAT)
    
    # Регистрируем middleware
    session_maker = get_session()
    dp.update.middleware(DbSessionMiddleware(session_maker))
    
    # Регистрируем роутеры
    dp.include_router(registration_router)
    dp.include_router(feedback_router)
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(pairing_router)
    
    # Запускаем планировщик задач
    scheduler = setup_scheduler(bot)
    
    # Запускаем поллинг
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True) 