#!/usr/bin/env python3
"""
Скрипт для исправления структуры таблицы meetings.
Добавляет колонку scheduled_date, если она отсутствует.
"""
import logging
import os
import sqlite3
import sys

logger = logging.getLogger(__name__)

# Путь к файлу базы данных
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "database.sqlite3")

def fix_meetings_table():
    """
    Проверяет и добавляет колонку scheduled_date в таблицу meetings, если она отсутствует.
    """
    conn = None
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Проверяем существующие колонки
        cursor.execute("PRAGMA table_info(meetings)")
        columns = {column[1] for column in cursor.fetchall()}
        
        # Проверяем наличие колонки scheduled_date
        if "scheduled_date" not in columns:
            logger.info("Добавление колонки scheduled_date в таблицу meetings")
            cursor.execute("ALTER TABLE meetings ADD COLUMN scheduled_date TIMESTAMP")
            logger.info("Колонка scheduled_date успешно добавлена")
            conn.commit()
        else:
            logger.info("Колонка scheduled_date уже существует в таблице meetings")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при изменении структуры таблицы meetings: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger.info("Начало исправления структуры таблицы meetings...")
    if fix_meetings_table():
        logger.info("Исправление структуры таблицы meetings завершено успешно")
        sys.exit(0)
    else:
        logger.error("Не удалось исправить структуру таблицы meetings")
        sys.exit(1) 