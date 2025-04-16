#!/usr/bin/env python3
"""
Скрипт для выполнения полной миграции базы данных.
"""
import logging
import sys
import time
import asyncio
import os
from sqlalchemy import Column, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import sqlite3
from datetime import datetime

from database.alter_table import main as alter_table_main
from database.update_values import main as update_values_main
from database.migrate_schedule import run_migration as run_user_numbering
from database.models import Base, Meeting
from database.db import DATABASE_URL

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def wait_for_db():
    """
    Ожидает доступности базы данных.
    Полезно при запуске в контейнере, когда база данных может запускаться отдельно.
    """
    db_file = "database.sqlite3"
    max_attempts = 10
    attempt = 0
    
    logger.info(f"Проверка доступности базы данных {db_file}")
    
    while attempt < max_attempts:
        if os.path.exists(db_file):
            logger.info(f"База данных {db_file} доступна")
            return True
        
        attempt += 1
        logger.warning(f"База данных {db_file} не доступна. Попытка {attempt}/{max_attempts}")
        time.sleep(5)
    
    logger.error(f"База данных {db_file} не стала доступна после {max_attempts} попыток")
    return False

async def update_meetings_schema():
    """
    Обновляет схему таблицы meetings, добавляя новые поля для тестового режима.
    """
    # Проверяем существование файла базы данных
    db_file = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    
    if not os.path.exists(db_file):
        logger.error(f"База данных не найдена: {db_file}")
        return
    
    # Открываем соединение с базой данных
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Проверяем наличие таблицы meetings
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='meetings'")
        table_info = cursor.fetchone()
        
        if not table_info:
            logger.error("Таблица meetings не найдена в базе данных")
            return
        
        # Проверяем существование полей is_cancelled, feedback_requested и reminder_sent
        cursor.execute("PRAGMA table_info(meetings)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        changes_made = False
        
        # Проверяем переименование meeting_date на scheduled_date
        if 'meeting_date' in column_names and 'scheduled_date' not in column_names:
            logger.info("Переименование поля meeting_date на scheduled_date")
            cursor.execute("ALTER TABLE meetings RENAME COLUMN meeting_date TO scheduled_date")
            changes_made = True
        
        # Добавляем новые поля, если их нет
        if 'is_cancelled' not in column_names:
            logger.info("Добавление поля is_cancelled")
            cursor.execute("ALTER TABLE meetings ADD COLUMN is_cancelled BOOLEAN DEFAULT 0")
            changes_made = True
        
        if 'feedback_requested' not in column_names:
            logger.info("Добавление поля feedback_requested")
            cursor.execute("ALTER TABLE meetings ADD COLUMN feedback_requested BOOLEAN DEFAULT 0")
            changes_made = True
        
        if 'reminder_sent' not in column_names:
            logger.info("Добавление поля reminder_sent")
            cursor.execute("ALTER TABLE meetings ADD COLUMN reminder_sent BOOLEAN DEFAULT 0")
            changes_made = True
        
        if changes_made:
            conn.commit()
            logger.info("Миграция схемы meetings успешно выполнена")
        else:
            logger.info("Миграция схемы meetings не требуется, все поля уже существуют")
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка при выполнении миграции схемы meetings: {e}", exc_info=True)
    
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        if not wait_for_db():
            sys.exit(1)
        
        alter_table_main()
        update_values_main()
        run_user_numbering()
        
        # Запускаем новую миграцию для тестового режима
        logger.info("Запуск обновления схемы meetings...")
        asyncio.run(update_meetings_schema())
        logger.info("Миграция завершена")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при миграции: {e}", exc_info=True)
        sys.exit(1) 