import asyncio
import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot
from sqlalchemy import select, and_, or_

from database.db import get_session
from database.models import User, Meeting
from handlers.notifications import send_meeting_reminder, send_feedback_request, send_reactivation_reminder
from services.meeting_service import create_meeting, get_pending_feedback_meetings
from services.test_mode_service import is_test_mode_active
from collections import defaultdict
import random

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения экземпляра планировщика
_scheduler = None


async def weekly_pairing_job():
    """
    Еженедельная задача по созданию пар пользователей.
    """
    logger.info("Запущена еженедельная задача по созданию пар")
    
    session = get_session()()
    try:
        # Получаем всех активных пользователей
        query = select(User).where(
            User.is_active == True,
            User.registration_complete == True
        )
        result = await session.execute(query)
        active_users = result.scalars().all()
        
        # Создаем пары только если есть хотя бы 2 пользователя
        if len(active_users) < 2:
            logger.info("Недостаточно активных пользователей для создания пар")
            return
        
        # Создаем пары и отправляем уведомления
        paired_users = await create_pairs(session, active_users)
        logger.info(f"Создано {len(paired_users) // 2} пар")
        
        # Отправляем уведомления
        await send_pairing_notifications(paired_users)
        
    except Exception as e:
        logger.error(f"Ошибка при создании пар: {e}", exc_info=True)
    finally:
        await session.close()


async def check_meetings_job():
    """
    Задача по проверке предстоящих встреч и отправке напоминаний.
    """
    logger.info("Запущена задача проверки предстоящих встреч")
    
    session = get_session()()
    try:
        # Получаем встречи, которые состоятся в ближайший час
        now = datetime.now()
        one_hour_later = now + timedelta(hours=1)
        
        # Учитываем тестовый режим, если он активен
        if is_test_mode_active():
            from services.test_mode_service import get_accelerated_date
            now = get_accelerated_date(now)
            one_hour_later = get_accelerated_date(one_hour_later)
        
        query = select(Meeting).where(
            and_(
                Meeting.scheduled_date >= now,
                Meeting.scheduled_date <= one_hour_later,
                Meeting.is_completed == False,
                Meeting.is_cancelled == False
            )
        )
        
        result = await session.execute(query)
        upcoming_meetings = result.scalars().all()
        
        # Отправляем напоминания
        for meeting in upcoming_meetings:
            await send_meeting_reminder(bot, session, meeting.id)
        
        logger.info(f"Отправлены напоминания для {len(upcoming_meetings)} встреч")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке встреч: {e}", exc_info=True)
    finally:
        await session.close()


async def check_feedback_job():
    """
    Задача по проверке прошедших встреч и отправке запросов на фидбек.
    """
    logger.info("Запущена задача проверки фидбека")
    
    session = get_session()()
    try:
        # Получаем встречи, которые завершились недавно
        yesterday = datetime.now() - timedelta(days=1)
        today = datetime.now()
        
        # Учитываем тестовый режим, если он активен
        if is_test_mode_active():
            from services.test_mode_service import get_accelerated_date
            yesterday = get_accelerated_date(yesterday)
            today = get_accelerated_date(today)
        
        query = select(Meeting).where(
            and_(
                Meeting.scheduled_date >= yesterday,
                Meeting.scheduled_date <= today,
                Meeting.is_completed == False,
                Meeting.is_cancelled == False,
                Meeting.feedback_requested == False
            )
        )
        
        result = await session.execute(query)
        completed_meetings = result.scalars().all()
        
        # Отправляем запросы на фидбек
        for meeting in completed_meetings:
            await send_feedback_request(bot, session, meeting.id)
        
        logger.info(f"Отправлены запросы фидбека для {len(completed_meetings)} встреч")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке фидбека: {e}", exc_info=True)
    finally:
        await session.close()


async def reactivation_reminder_job():
    """
    Задача по отправке напоминаний неактивным пользователям.
    """
    logger.info("Запущена задача напоминания неактивным пользователям")
    
    session = get_session()()
    try:
        await send_reactivation_reminder(bot, session)
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминаний: {e}", exc_info=True)
    finally:
        await session.close()


async def create_pairs(session, users):
    """
    Создает пары пользователей на основе их интересов и предыдущих встреч.
    
    :param session: Сессия базы данных
    :param users: Список активных пользователей
    :return: Список пар (кортежей пользователей)
    """
    # Предварительно загружаем интересы всех пользователей для избежания lazy loading
    for user in users:
        # Явно загружаем interests для каждого пользователя
        await session.refresh(user, ["interests"])
    
    # Словарь для хранения последних партнеров каждого пользователя
    recent_partners = defaultdict(set)
    
    # Получаем последние встречи для каждого пользователя
    for user in users:
        # Получаем последние встречи (до 5)
        meetings_query = select(Meeting).where(
            or_(
                Meeting.user1_id == user.telegram_id,
                Meeting.user2_id == user.telegram_id
            )
        ).order_by(Meeting.created_at.desc()).limit(5)
        
        meetings_result = await session.execute(meetings_query)
        recent_meetings = meetings_result.scalars().all()
        
        # Добавляем партнеров в множество
        for meeting in recent_meetings:
            if meeting.user1_id == user.telegram_id:
                recent_partners[user.telegram_id].add(meeting.user2_id)
            else:
                recent_partners[user.telegram_id].add(meeting.user1_id)
    
    # Создаем копию списка пользователей для работы
    available_users = users.copy()
    random.shuffle(available_users)
    
    paired_users = []
    
    # Проходим по всем пользователям и пытаемся найти подходящую пару
    while len(available_users) >= 2:
        user = available_users.pop(0)
        
        # Формируем список потенциальных партнеров
        potential_partners = []
        
        for potential_partner in available_users:
            # Проверяем, был ли партнер недавно
            if potential_partner.telegram_id in recent_partners[user.telegram_id]:
                continue
            
            # Проверяем форматы встреч
            if (user.meeting_format and potential_partner.meeting_format and
                user.meeting_format != potential_partner.meeting_format and
                user.meeting_format.value != "Не важно" and 
                potential_partner.meeting_format.value != "Не важно"):
                continue
            
            # Находим общие интересы (теперь interests уже загружены)
            common_interests = set(interest.id for interest in user.interests) & set(interest.id for interest in potential_partner.interests)
            
            # Добавляем пользователя с весом по количеству общих интересов
            potential_partners.append((potential_partner, len(common_interests)))
        
        # Если есть потенциальные партнеры, выбираем по общим интересам
        if potential_partners:
            # Сортируем по количеству общих интересов (от большего к меньшему)
            potential_partners.sort(key=lambda x: x[1], reverse=True)
            
            # Берем первые 3 или все, если их меньше
            top_partners = potential_partners[:min(3, len(potential_partners))]
            
            # Случайно выбираем одного из топ-партнеров
            selected_partner, _ = random.choice(top_partners)
            
            # Удаляем выбранного партнера из доступных
            available_users.remove(selected_partner)
            
            # Добавляем пару в результат
            paired_users.extend([user, selected_partner])
            
            # Создаем встречу в базе данных
            await create_meeting(session, user.telegram_id, selected_partner.telegram_id)
        
    return paired_users


async def send_pairing_notifications(paired_users):
    """
    Отправляет уведомления о созданных парах.
    
    :param paired_users: Список пользователей, разбитых на пары
    """
    # Проходим по парам и отправляем уведомления
    for i in range(0, len(paired_users), 2):
        if i + 1 < len(paired_users):
            user1 = paired_users[i]
            user2 = paired_users[i + 1]
            
            # Формируем сообщение для первого пользователя
            message1 = (
                f"🎉 Хорошие новости! Мы нашли тебе собеседника для неслучайной встречи!\n\n"
                f"*Твой собеседник: {user2.full_name}*\n"
                f"№{user2.user_number}\n"
                f"Подразделение: {user2.department}, {user2.role}\n"
                f"Формат встреч: {user2.meeting_format.value if user2.meeting_format else 'Не указан'}\n"
                f"Доступные дни: {format_weekdays(user2.available_days)}\n"
                f"Удобное время: {user2.available_time_slot}\n\n"
                f"Напиши собеседнику напрямую, чтобы договориться о встрече: @{user2.username}"
            )
            
            # Формируем сообщение для второго пользователя
            message2 = (
                f"🎉 Хорошие новости! Мы нашли тебе собеседника для неслучайной встречи!\n\n"
                f"*Твой собеседник: {user1.full_name}*\n"
                f"№{user1.user_number}\n"
                f"Подразделение: {user1.department}, {user1.role}\n"
                f"Формат встреч: {user1.meeting_format.value if user1.meeting_format else 'Не указан'}\n"
                f"Доступные дни: {format_weekdays(user1.available_days)}\n"
                f"Удобное время: {user1.available_time_slot}\n\n"
                f"Напиши собеседнику напрямую, чтобы договориться о встрече: @{user1.username}"
            )
            
            # Отправляем сообщения
            try:
                await bot.send_message(user1.telegram_id, message1, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user1.telegram_id}: {e}")
            
            try:
                await bot.send_message(user2.telegram_id, message2, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user2.telegram_id}: {e}")


def format_weekdays(days_str):
    """
    Форматирует строку с днями недели в удобочитаемый формат
    """
    if not days_str:
        return "Не указаны"
    
    days_list = days_str.split(",")
    days_names = {
        "monday": "Пн",
        "tuesday": "Вт",
        "wednesday": "Ср",
        "thursday": "Чт",
        "friday": "Пт"
    }
    
    return ", ".join([days_names.get(day, day) for day in days_list])


def setup_scheduler(bot=None):
    """
    Настраивает планировщик задач.
    
    :param bot: Экземпляр бота. Если None, будет создан новый.
    :return: Экземпляр планировщика
    """
    global _scheduler
    
    # Если планировщик уже существует, останавливаем его
    if _scheduler is not None:
        _scheduler.shutdown()
    
    # Если bot не передан, создаем его
    if bot is None:
        from dotenv import load_dotenv
        load_dotenv()
        bot = Bot(token=os.getenv("BOT_TOKEN"))
    
    # Сохраняем бота в глобальную переменную для использования в задачах
    globals()["bot"] = bot
    
    _scheduler = AsyncIOScheduler()
    
    if is_test_mode_active():
        # Тестовый режим - более частые интервалы
        logger.info("Настройка планировщика в тестовом режиме")
        
        # Создание пар - каждые 12 минут (1 рабочая неделя = 1 час)
        _scheduler.add_job(
            weekly_pairing_job,
            trigger=IntervalTrigger(minutes=12),
            id="weekly_pairing_test",
            replace_existing=True
        )
        
        # Проверка предстоящих встреч - каждые 2 минуты (1 рабочий день = 12 минут)
        _scheduler.add_job(
            check_meetings_job,
            trigger=IntervalTrigger(minutes=2),
            id="check_meetings_test",
            replace_existing=True
        )
        
        # Проверка фидбека - каждые 12 минут
        _scheduler.add_job(
            check_feedback_job,
            trigger=IntervalTrigger(minutes=12),
            id="check_feedback_test",
            replace_existing=True
        )
        
        # Напоминание неактивным пользователям - каждые 12 минут
        _scheduler.add_job(
            reactivation_reminder_job,
            trigger=IntervalTrigger(minutes=12),
            id="reactivation_reminder_test",
            replace_existing=True
        )
    else:
        # Обычный режим - стандартные интервалы
        logger.info("Настройка планировщика в обычном режиме")
        
        # Еженедельное создание пар (по понедельникам в 10:00)
        _scheduler.add_job(
            weekly_pairing_job,
            trigger=CronTrigger(day_of_week="mon", hour=10, minute=0),
            id="weekly_pairing",
            replace_existing=True
        )
        
        # Проверка предстоящих встреч (каждый час)
        _scheduler.add_job(
            check_meetings_job,
            trigger=CronTrigger(hour="*", minute=0),
            id="check_meetings",
            replace_existing=True
        )
        
        # Проверка фидбека (каждый день в 18:00)
        _scheduler.add_job(
            check_feedback_job,
            trigger=CronTrigger(hour=18, minute=0),
            id="check_feedback",
            replace_existing=True
        )
        
        # Напоминание неактивным пользователям (каждый понедельник в 12:00)
        _scheduler.add_job(
            reactivation_reminder_job,
            trigger=CronTrigger(day_of_week="mon", hour=12, minute=0),
            id="reactivation_reminder",
            replace_existing=True
        )
    
    # Запускаем планировщик
    _scheduler.start()
    return _scheduler


def reconfigure_scheduler():
    """
    Перенастраивает планировщик в соответствии с текущим режимом работы.
    Вызывается при включении/отключении тестового режима.
    """
    logger.info("Перенастройка планировщика")
    return setup_scheduler(bot=globals().get("bot")) 