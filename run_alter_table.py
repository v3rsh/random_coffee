#!/usr/bin/env python3
"""
Скрипт для запуска обновления схемы таблицы users в базе данных.
"""
import logging
import sys
from database.alter_table import main as alter_table_main

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Запуск обновления схемы базы данных...")
        alter_table_main()
        logger.info("Схема базы данных успешно обновлена!")
    except Exception as e:
        logger.error(f"Ошибка при обновлении схемы базы данных: {e}", exc_info=True)
        sys.exit(1) 