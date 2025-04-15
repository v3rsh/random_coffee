import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_, or_

from app import bot
from database.db import get_session
from database.models import User, Meeting
from handlers.notifications import send_meeting_reminder, send_feedback_request, send_reactivation_reminder
from services.meeting_service import create_meeting, get_pending_feedback_meetings

logger = logging.getLogger(__name__)


async def weekly_pairing_job():
    """
    Еженедельная задача по созданию пар пользователей.
    """
    logger.info("Запущена еженедельная задача по созданию пар")
    
    async for session in get_session():
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


async def check_meetings_job():
    """
    Задача по проверке предстоящих встреч и отправке напоминаний.
    """
    logger.info("Запущена задача проверки предстоящих встреч")
    
    async for session in get_session():
        try:
            # Получаем встречи, которые состоятся в ближайший час
            now = datetime.now()
            one_hour_later = now + timedelta(hours=1)
            
            query = select(Meeting).where(
                and_(
                    Meeting.meeting_date >= now,
                    Meeting.meeting_date <= one_hour_later,
                    Meeting.is_completed == False
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


async def check_feedback_job():
    """
    Задача по проверке прошедших встреч и отправке запросов на фидбек.
    """
    logger.info("Запущена задача проверки фидбека")
    
    async for session in get_session():
        try:
            # Получаем встречи, которые завершились вчера
            yesterday = datetime.now() - timedelta(days=1)
            today = datetime.now()
            
            query = select(Meeting).where(
                and_(
                    Meeting.meeting_date >= yesterday,
                    Meeting.meeting_date <= today,
                    Meeting.is_completed == False
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


async def reactivation_reminder_job():
    """
    Задача по отправке напоминаний неактивным пользователям.
    """
    logger.info("Запущена задача напоминания неактивным пользователям")
    
    async for session in get_session():
        try:
            await send_reactivation_reminder(bot, session)
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний: {e}", exc_info=True)


async def create_pairs(session, users):
    """
    Создает пары пользователей на основе их интересов и предыдущих встреч.
    
    :param session: Сессия базы данных
    :param users: Список активных пользователей
    :return: Список пар (кортежей пользователей)
    """
    import random
    from collections import defaultdict
    
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
            
            # Находим общие интересы
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
                f"Подразделение: {user2.department}, {user2.role}\n"
                f"Формат встреч: {user2.meeting_format.value if user2.meeting_format else 'Не указан'}\n\n"
                f"Напиши собеседнику напрямую, чтобы договориться о встрече: @{user2.username}"
            )
            
            # Формируем сообщение для второго пользователя
            message2 = (
                f"🎉 Хорошие новости! Мы нашли тебе собеседника для неслучайной встречи!\n\n"
                f"*Твой собеседник: {user1.full_name}*\n"
                f"Подразделение: {user1.department}, {user1.role}\n"
                f"Формат встреч: {user1.meeting_format.value if user1.meeting_format else 'Не указан'}\n\n"
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


def setup_scheduler():
    """
    Настраивает и запускает планировщик задач.
    
    :return: Экземпляр планировщика
    """
    scheduler = AsyncIOScheduler()
    
    # Еженедельное создание пар (каждый понедельник в 9:00)
    scheduler.add_job(
        weekly_pairing_job,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_pairing",
        replace_existing=True
    )
    
    # Проверка предстоящих встреч каждый час
    scheduler.add_job(
        check_meetings_job,
        CronTrigger(minute=0),  # Каждый час в :00 минут
        id="check_meetings",
        replace_existing=True
    )
    
    # Проверка фидбека каждый день в 10:00
    scheduler.add_job(
        check_feedback_job,
        CronTrigger(hour=10, minute=0),
        id="check_feedback",
        replace_existing=True
    )
    
    # Отправка напоминаний неактивным пользователям (каждую пятницу в 12:00)
    scheduler.add_job(
        reactivation_reminder_job,
        CronTrigger(day_of_week="fri", hour=12, minute=0),
        id="reactivation_reminder",
        replace_existing=True
    )
    
    # Запускаем планировщик
    scheduler.start()
    logger.info("Планировщик задач запущен")
    
    return scheduler 