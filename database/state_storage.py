import json
import logging
from typing import Dict, Any, Optional, cast, List

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

import aiosqlite

logger = logging.getLogger(__name__)

class SQLiteStorage(BaseStorage):
    """
    SQLite хранилище для состояний FSM
    """
    
    def __init__(self, db_path: str = "database.sqlite3"):
        self.db_path = db_path
        
    async def _init_db(self):
        """Инициализирует таблицу для хранения состояний, если она еще не существует"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS fsm_storage (
                    key TEXT PRIMARY KEY,
                    state TEXT NULL,
                    data TEXT NOT NULL
                )
            """)
            await db.commit()
    
    @staticmethod
    def _create_key(key: StorageKey) -> str:
        """Создает строковый ключ из объекта StorageKey"""
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id or 0}"
    
    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        """Устанавливает состояние для ключа"""
        await self._init_db()
        
        str_key = self._create_key(key)
        
        state_str = state.state if isinstance(state, State) else state
        
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем существование записи
            async with db.execute("SELECT 1 FROM fsm_storage WHERE key = ?", (str_key,)) as cursor:
                exists = await cursor.fetchone()
            
            if exists:
                await db.execute(
                    "UPDATE fsm_storage SET state = ? WHERE key = ?",
                    (state_str, str_key)
                )
            else:
                # Получаем текущие данные или создаем пустой словарь
                data = await self.get_data(key) or {}
                await db.execute(
                    "INSERT INTO fsm_storage (key, state, data) VALUES (?, ?, ?)",
                    (str_key, state_str, json.dumps(data))
                )
            
            await db.commit()
    
    async def get_state(self, key: StorageKey) -> Optional[str]:
        """Получает текущее состояние по ключу"""
        await self._init_db()
        
        str_key = self._create_key(key)
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT state FROM fsm_storage WHERE key = ?",
                (str_key,)
            ) as cursor:
                result = await cursor.fetchone()
                
                if result:
                    return result[0]
                return None
    
    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        """Устанавливает данные для ключа"""
        await self._init_db()
        
        str_key = self._create_key(key)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем существование записи
            async with db.execute("SELECT 1 FROM fsm_storage WHERE key = ?", (str_key,)) as cursor:
                exists = await cursor.fetchone()
            
            if exists:
                await db.execute(
                    "UPDATE fsm_storage SET data = ? WHERE key = ?",
                    (json.dumps(data), str_key)
                )
            else:
                await db.execute(
                    "INSERT INTO fsm_storage (key, state, data) VALUES (?, ?, ?)",
                    (str_key, None, json.dumps(data))
                )
            
            await db.commit()
    
    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        """Получает данные по ключу"""
        await self._init_db()
        
        str_key = self._create_key(key)
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data FROM fsm_storage WHERE key = ?",
                (str_key,)
            ) as cursor:
                result = await cursor.fetchone()
                
                if result:
                    return cast(Dict[str, Any], json.loads(result[0]))
                return {}
    
    async def update_data(self, key: StorageKey, data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет данные для ключа"""
        await self._init_db()
        
        current_data = await self.get_data(key)
        current_data.update(data)
        await self.set_data(key, current_data)
        return current_data
    
    async def close(self) -> None:
        """Этот метод вызывается при закрытии хранилища"""
        pass
        
    async def reset_state(self, key: StorageKey) -> None:
        """Сбрасывает состояние для ключа (устанавливает в None)"""
        await self.set_state(key, state=None)
        
    async def reset_data(self, key: StorageKey) -> None:
        """Сбрасывает данные для ключа (устанавливает пустой словарь)"""
        await self.set_data(key, data={})
        
    async def reset_all(self, key: StorageKey) -> None:
        """Сбрасывает и состояние, и данные для ключа"""
        str_key = self._create_key(key)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM fsm_storage WHERE key = ?", (str_key,))
            await db.commit()
            
    async def get_all_states(self) -> List[Dict[str, Any]]:
        """Получает все состояния из хранилища"""
        await self._init_db()
        
        result = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT key, state, data FROM fsm_storage"
            ) as cursor:
                async for key, state, data in cursor:
                    result.append({
                        "key": key,
                        "state": state,
                        "data": json.loads(data)
                    })
        
        return result 