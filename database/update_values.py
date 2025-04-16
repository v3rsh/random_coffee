"""
Скрипт для обновления значений в новых колонках таблицы users.
"""
import logging
import os
import sqlite3
from database.models import WeekDay, TimeSlot

logger = logging.getLogger(__name__)

# Путь к файлу базы данных
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.sqlite3")

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

def update_values():
    """
    Обновляет значения в новых колонках таблицы users согласно маппингам.
    """
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Получаем всех пользователей
        cursor.execute("SELECT telegram_id, available_days, available_time_slot, available_day, available_time FROM users")
        users = cursor.fetchall()
        
        for user in users:
            telegram_id, available_days, available_time_slot, available_day, available_time = user
            
            # Обрабатываем дни недели
            if available_day and not available_days:
                day_value = available_day.strip()
                days_list = []
                
                if day_value in day_mapping:
                    days_list.append(day_mapping[day_value])
                else:
                    # Если не найдено точное соответствие, пробуем несколько дней разделенных запятой
                    for day in day_value.split(','):
                        day = day.strip()
                        if day in day_mapping:
                            days_list.append(day_mapping[day])
                
                if days_list:
                    days_str = ",".join(days_list)
                    cursor.execute("UPDATE users SET available_days = ? WHERE telegram_id = ?", (days_str, telegram_id))
                    logger.info(f"Обновлены дни для пользователя {telegram_id}: {days_str}")
            
            # Обрабатываем временные слоты
            if available_time and not available_time_slot:
                time_value = available_time.strip()
                
                if time_value in time_mapping:
                    time_slot = time_mapping[time_value]
                    cursor.execute("UPDATE users SET available_time_slot = ? WHERE telegram_id = ?", (time_slot, telegram_id))
                    logger.info(f"Обновлен временной слот для пользователя {telegram_id}: {time_slot}")
                else:
                    # Пробуем найти ближайшее соответствие
                    for key, value in time_mapping.items():
                        if key in time_value:
                            cursor.execute("UPDATE users SET available_time_slot = ? WHERE telegram_id = ?", (value, telegram_id))
                            logger.info(f"Обновлен временной слот для пользователя {telegram_id}: {value}")
                            break
        
        # Сохраняем изменения
        conn.commit()
        logger.info("Значения в таблице users успешно обновлены")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении значений: {e}")
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
    
    logger.info("Начало обновления значений в таблице users...")
    update_values()
    logger.info("Обновление значений в таблице users завершено")

if __name__ == "__main__":
    main() 