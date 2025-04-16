#!/usr/bin/env python3
"""
Скрипт для выполнения полной миграции базы данных.
"""
import logging
import sys
import time

from database.alter_table import main as alter_table_main
from database.update_values import main as update_values_main
from database.migrate_schedule import run_migration as run_user_numbering

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def run_migration():
    """
    Выполняет полную миграцию базы данных:
    1. Изменение структуры таблицы
    2. Обновление значений в новых колонках
    3. Нумерация пользователей
    """
    try:
        # Шаг 1: Изменение структуры таблицы
        logger.info("ЭТАП 1: Изменение структуры таблицы")
        alter_table_main()
        time.sleep(1)  # Небольшая пауза для завершения операций с БД
        
        # Шаг 2: Обновление значений в новых колонках
        logger.info("ЭТАП 2: Обновление значений в новых колонках")
        update_values_main()
        time.sleep(1)  # Небольшая пауза для завершения операций с БД
        
        # Шаг 3: Нумерация пользователей
        logger.info("ЭТАП 3: Назначение порядковых номеров пользователям")
        asyncio.run(run_user_numbering())
        
        logger.info("Миграция успешно завершена")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Добавляем импорт asyncio здесь, чтобы избежать проблем с циклической зависимостью
        import asyncio
        
        logger.info("Запуск полной миграции базы данных...")
        run_migration()
        logger.info("Миграция базы данных успешно завершена!")
    except Exception as e:
        logger.error(f"Критическая ошибка при миграции: {e}", exc_info=True)
        sys.exit(1) 