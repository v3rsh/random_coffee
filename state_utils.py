#!/usr/bin/env python3
"""
Утилитарный скрипт для работы с хранилищем состояний
"""
import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from aiogram.fsm.storage.base import StorageKey

from database.state_storage import SQLiteStorage
from states import RegistrationStates, FeedbackStates, PairingStates

load_dotenv()

async def list_states(db_path: str = "database.sqlite3"):
    """Показывает список всех состояний"""
    storage = SQLiteStorage(db_path)
    states = await storage.get_all_states()
    
    if not states:
        print("Хранилище пусто")
        return
    
    print(f"Всего записей: {len(states)}")
    for item in states:
        key_parts = item["key"].split(":")
        if len(key_parts) >= 3:
            user_id = key_parts[2]
            state = item["state"]
            data = item["data"]
            print(f"User ID: {user_id}, State: {state}")
            if data:
                print(f"Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
            print("-" * 50)

async def clear_states(user_id: int = None, db_path: str = "database.sqlite3"):
    """Очищает состояния для конкретного пользователя или для всех пользователей"""
    storage = SQLiteStorage(db_path)
    states = await storage.get_all_states()
    
    if not states:
        print("Хранилище уже пусто")
        return
    
    if user_id:
        # Ищем все ключи для указанного пользователя
        user_keys = []
        for item in states:
            key_parts = item["key"].split(":")
            if len(key_parts) >= 3 and key_parts[2] == str(user_id):
                user_keys.append(item["key"])
        
        if not user_keys:
            print(f"Состояний для пользователя {user_id} не найдено")
            return
        
        # Удаляем все найденные ключи
        for key in user_keys:
            # Создаем StorageKey из строки
            bot_id, chat_id, user_id, thread_id = key.split(":")
            storage_key = StorageKey(bot_id=bot_id, chat_id=int(chat_id), 
                                     user_id=int(user_id), thread_id=int(thread_id))
            await storage.reset_all(storage_key)
        
        print(f"Состояния для пользователя {user_id} были очищены")
    else:
        # Очищаем всю таблицу
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            await db.execute("DELETE FROM fsm_storage")
            await db.commit()
        
        print("Все состояния были очищены")

async def main():
    parser = argparse.ArgumentParser(description="Утилиты для работы с хранилищем состояний")
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # Команда list
    list_parser = subparsers.add_parser("list", help="Показать список состояний")
    list_parser.add_argument("--db", help="Путь к базе данных", default="database.sqlite3")
    
    # Команда clear
    clear_parser = subparsers.add_parser("clear", help="Очистить состояния")
    clear_parser.add_argument("--user-id", type=int, help="ID пользователя (если не указан, очищаются все)", default=None)
    clear_parser.add_argument("--db", help="Путь к базе данных", default="database.sqlite3")
    
    args = parser.parse_args()
    
    if args.command == "list":
        await list_states(args.db)
    elif args.command == "clear":
        await clear_states(args.user_id, args.db)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main()) 