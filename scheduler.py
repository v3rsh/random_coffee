import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import async_session_maker
from services.meeting_service import create_meetings_for_users

logger = logging.getLogger(__name__)


async def create_weekly_meetings():
    """
    Задача по еженедельному формированию пар пользователей.
    """
    logger.info("Запуск задачи по формированию пар")
    
    async with async_session_maker() as session:
        try:
            meetings = await create_meetings_for_users(session)
            logger.info(f"Создано {len(meetings)} пар для встреч")
            
            # Здесь будет вызов функции для отправки уведомлений
            await notify_users_about_meetings(session, meetings)
            
        except Exception as e:
            logger.error(f"Ошибка при формировании пар: {e}")


async def notify_users_about_meetings(session: AsyncSession, meetings):
    """
    Отправка уведомлений пользователям о созданных встречах.
    Эта функция будет реализована в handlers.py
    """
    from handlers.notifications import send_meeting_notifications
    
    try:
        await send_meeting_notifications(session, meetings)
        logger.info("Уведомления отправлены всем пользователям")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {e}")


async def check_for_pending_feedbacks():
    """
    Задача по проверке и отправке напоминаний о фидбеке.
    """
    logger.info("Запуск задачи по проверке необходимости фидбека")
    
    async with async_session_maker() as session:
        try:
            # Эта функция будет реализована в handlers.py
            from handlers.notifications import send_feedback_reminders
            await send_feedback_reminders(session)
            logger.info("Напоминания о фидбеке отправлены")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний о фидбеке: {e}")


def setup_scheduler():
    """
    Настройка и запуск планировщика задач.
    """
    scheduler = AsyncIOScheduler()
    
    # Формирование пар каждый понедельник в 8:00 утра
    scheduler.add_job(
        create_weekly_meetings,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="create_weekly_meetings",
        replace_existing=True
    )
    
    # Проверка необходимости фидбека каждый день в 12:00
    scheduler.add_job(
        check_for_pending_feedbacks,
        trigger=CronTrigger(hour=12, minute=0),
        id="check_feedbacks",
        replace_existing=True
    )
    
    # Запуск планировщика
    scheduler.start()
    logger.info("Планировщик задач запущен")
    
    return scheduler 