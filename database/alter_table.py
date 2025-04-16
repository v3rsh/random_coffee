"""
Скрипт для изменения структуры таблицы users.
Добавляет новые колонки и переименовывает старые.
"""
import asyncio
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

# Путь к файлу базы данных
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.sqlite3")

def alter_users_table():
    """
    Изменяет структуру таблицы users, добавляя новые колонки и переименовывая старые.
    """
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Проверяем существующие колонки
        cursor.execute("PRAGMA table_info(users)")
        columns = {column[1] for column in cursor.fetchall()}
        
        # Проверяем и добавляем колонку user_number, если её нет
        if "user_number" not in columns:
            logger.info("Добавление колонки user_number в таблицу users")
            cursor.execute("ALTER TABLE users ADD COLUMN user_number INTEGER")
        
        # Проверяем наличие старых колонок
        if "available_day" in columns and "available_days" not in columns:
            logger.info("Переименование колонки available_day в available_days")
            # SQLite не поддерживает прямое переименование колонок, используем обходной путь
            cursor.execute("ALTER TABLE users ADD COLUMN available_days TEXT")
            cursor.execute("UPDATE users SET available_days = available_day")
        
        if "available_time" in columns and "available_time_slot" not in columns:
            logger.info("Добавление колонки available_time_slot")
            cursor.execute("ALTER TABLE users ADD COLUMN available_time_slot TEXT")
            cursor.execute("UPDATE users SET available_time_slot = available_time")
        
        # Проверяем и добавляем колонки для рабочих часов
        if "work_hours_start" not in columns:
            logger.info("Добавление колонки work_hours_start в таблицу users")
            cursor.execute("ALTER TABLE users ADD COLUMN work_hours_start TEXT")
        
        if "work_hours_end" not in columns:
            logger.info("Добавление колонки work_hours_end в таблицу users")
            cursor.execute("ALTER TABLE users ADD COLUMN work_hours_end TEXT")
        
        # Сохраняем изменения
        conn.commit()
        logger.info("Структура таблицы users успешно обновлена")
        
    except Exception as e:
        logger.error(f"Ошибка при изменении структуры таблицы: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """
    Главная функция скрипта.
    """
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    logger.info("Начало обновления структуры базы данных...")
    alter_users_table()
    logger.info("Обновление структуры базы данных завершено")

if __name__ == "__main__":
    main() 