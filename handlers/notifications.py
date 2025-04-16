from datetime import datetime, timedelta
from typing import List
import logging

from aiogram import Bot, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from database.models import Meeting, User, TopicType
from keyboards import get_topic_name, get_topic_emoji, create_rating_keyboard
from services.meeting_service import get_meeting, get_pending_feedback_meetings
from services.user_service import get_user
from services.test_mode_service import is_test_mode_active, get_accelerated_date, get_real_date

# Создаем роутер для уведомлений
notifications_router = Router()
logger = logging.getLogger(__name__)


async def send_meeting_notifications(session: AsyncSession, meetings: List[Meeting]):
    """
    Отправляет уведомления пользователям о созданных встречах.
    
    Args:
        session: Сессия базы данных
        meetings: Список встреч для отправки уведомлений
    """
    from app import bot  # Импортируем бота здесь, чтобы избежать цикличного импорта
    
    for meeting in meetings:
        # Получаем пользователей
        user1 = await get_user(session, meeting.user1_id)
        user2 = await get_user(session, meeting.user2_id)
        
        if not user1 or not user2:
            continue
        
        # Общие интересы
        common_topics = set(topic.value for topic in user1.topics) & set(topic.value for topic in user2.topics)
        
        # Формируем сообщение для первого пользователя
        message_for_user1 = generate_meeting_message(user2, common_topics)
        # Формируем сообщение для второго пользователя
        message_for_user2 = generate_meeting_message(user1, common_topics)
        
        # Создаем клавиатуру для связи
        kb_for_user1 = get_contact_keyboard(user2)
        kb_for_user2 = get_contact_keyboard(user1)
        
        # Отправляем уведомления
        try:
            await bot.send_message(
                chat_id=user1.telegram_id,
                text=message_for_user1,
                reply_markup=kb_for_user1,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления пользователю {user1.telegram_id}: {e}")
        
        try:
            await bot.send_message(
                chat_id=user2.telegram_id,
                text=message_for_user2,
                reply_markup=kb_for_user2,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления пользователю {user2.telegram_id}: {e}")


def generate_meeting_message(partner: User, common_topics) -> str:
    """
    Генерирует текст сообщения о встрече с партнером.
    
    Args:
        partner: Партнер для встречи
        common_topics: Общие интересы
    
    Returns:
        Текст сообщения
    """
    # Форматируем общие интересы
    topics_str = ""
    if common_topics:
        topics_str = "\n".join([
            f"• {get_topic_emoji(TopicType(topic))} {get_topic_name(TopicType(topic))}"
            for topic in common_topics
        ])
    else:
        # Если нет общих интересов, берем интересы партнера
        topics_str = "\n".join([
            f"• {get_topic_emoji(topic)} {get_topic_name(topic)}"
            for topic in partner.topics
        ])
    
    # Форматируем рабочие часы
    work_hours = partner.work_hours_start
    if partner.work_hours_end:
        work_hours += f" - {partner.work_hours_end}"
    
    # Форматируем формат встречи
    meeting_format = {
        "offline": "Оффлайн 🏢",
        "online": "Онлайн 💻",
        "any": "Любой 🔄"
    }.get(partner.meeting_format.value, "Не указан")
    
    # Собираем сообщение
    message = (
        f"🎉 *Найден собеседник для Random Coffee!*\n\n"
        f"👤 *Имя:* {partner.full_name}\n"
    )
    
    # Добавляем отдел, если он указан
    if partner.department:
        message += f"🏢 *Отдел/роль:* {partner.department}\n"
    
    # Добавляем рабочие часы, если они указаны
    if work_hours:
        message += f"🕒 *Удобное время:* {work_hours}\n"
    
    # Добавляем формат встречи
    message += f"🤝 *Предпочитаемый формат встречи:* {meeting_format}\n\n"
    
    # Добавляем общие интересы
    message += f"📌 *Интересующие темы:*\n{topics_str}\n\n"
    
    # Добавляем призыв к действию
    message += (
        "Свяжитесь с вашим собеседником, чтобы договориться о времени встречи. "
        "Приятного общения! ☕"
    )
    
    return message


def get_contact_keyboard(user: User) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для связи с пользователем.
    
    Args:
        user: Пользователь, с которым нужно связаться
    
    Returns:
        Клавиатура с кнопками связи
    """
    kb = InlineKeyboardBuilder()
    
    # Добавляем кнопку для связи, если есть username
    if user.username:
        kb.add(InlineKeyboardButton(
            text="📱 Написать собеседнику",
            url=f"https://t.me/{user.username}"
        ))
    
    return kb.as_markup()


async def send_feedback_reminders(session: AsyncSession):
    """
    Отправляет напоминания о необходимости оставить фидбек после встречи.
    
    Args:
        session: Сессия базы данных
    """
    from app import bot  # Импортируем бота здесь, чтобы избежать цикличного импорта
    
    # Получаем список активных пользователей
    from services.user_service import get_active_users
    users = await get_active_users(session)
    
    for user in users:
        # Получаем встречи, требующие фидбека
        pending_feedback_meetings = await get_pending_feedback_meetings(session, user.telegram_id)
        
        # Отправляем напоминание, если есть встречи без фидбека
        for meeting in pending_feedback_meetings:
            # Определяем партнера
            partner_id = meeting.user2_id if meeting.user1_id == user.telegram_id else meeting.user1_id
            partner = await get_user(session, partner_id)
            
            if not partner:
                continue
            
            # Формируем сообщение
            message = (
                f"👋 Привет! Как прошла ваша встреча с {partner.full_name}?\n\n"
                f"Пожалуйста, оставьте небольшой фидбек, чтобы мы могли улучшать сервис Random Coffee."
            )
            
            # Создаем клавиатуру для фидбека
            kb = InlineKeyboardBuilder()
            kb.add(InlineKeyboardButton(
                text="📝 Оставить фидбек",
                callback_data=f"feedback:{meeting.id}:{partner.telegram_id}"
            ))
            
            # Отправляем напоминание
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    reply_markup=kb.as_markup()
                )
            except Exception as e:
                print(f"Ошибка при отправке напоминания о фидбеке пользователю {user.telegram_id}: {e}") 


async def send_meeting_reminder(bot: Bot, session: AsyncSession, meeting_id: int):
    """
    Отправляет напоминание о предстоящей встрече.
    
    Args:
        bot: Бот для отправки сообщений
        session: Сессия базы данных
        meeting_id: ID встречи
    """
    # Получаем встречу
    meeting = await get_meeting(session, meeting_id)
    if not meeting or not meeting.scheduled_date:
        return
    
    # Проверяем, что встреча еще не прошла и не отменена
    current_time = datetime.now()
    if is_test_mode_active():
        current_time = get_accelerated_date(current_time)
    
    if meeting.is_completed or meeting.is_cancelled or meeting.scheduled_date < current_time:
        return
    
    # Находим разницу между текущим временем и временем встречи
    time_diff = meeting.scheduled_date - current_time
    
    # Если до встречи больше 1 часа, не отправляем напоминание
    if time_diff > timedelta(hours=1):
        return
    
    # Получаем участников встречи
    user1 = await get_user(session, meeting.user1_id)
    user2 = await get_user(session, meeting.user2_id)
    
    if not user1 or not user2:
        return
    
    # Формируем сообщение напоминания
    message = (
        f"⏰ *Напоминание о встрече*\n\n"
        f"Ваша встреча с {user2.full_name} запланирована на сегодня в {meeting.scheduled_date.strftime('%H:%M')}.\n\n"
        f"Не забудьте присоединиться и хорошо провести время! ☕"
    )
    
    # Отправляем напоминание первому пользователю
    try:
        await bot.send_message(
            chat_id=user1.telegram_id,
            text=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания пользователю {user1.telegram_id}: {e}")
    
    # Формируем сообщение для второго пользователя
    message = (
        f"⏰ *Напоминание о встрече*\n\n"
        f"Ваша встреча с {user1.full_name} запланирована на сегодня в {meeting.scheduled_date.strftime('%H:%M')}.\n\n"
        f"Не забудьте присоединиться и хорошо провести время! ☕"
    )
    
    # Отправляем напоминание второму пользователю
    try:
        await bot.send_message(
            chat_id=user2.telegram_id,
            text=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания пользователю {user2.telegram_id}: {e}")
    
    # Обновляем статус напоминания
    meeting.reminder_sent = True
    await session.commit()


async def send_feedback_request(bot: Bot, session: AsyncSession, meeting_id: int):
    """
    Отправляет запрос на предоставление фидбека после встречи.
    
    Args:
        bot: Бот для отправки сообщений
        session: Сессия базы данных
        meeting_id: ID встречи
    """
    # Получаем встречу
    meeting = await get_meeting(session, meeting_id)
    if not meeting or not meeting.scheduled_date:
        return
    
    # Проверяем, что встреча прошла и не отменена
    current_time = datetime.now()
    if is_test_mode_active():
        current_time = get_accelerated_date(current_time)
    
    if meeting.is_cancelled or meeting.scheduled_date > current_time:
        return
    
    # Проверяем, что запрос на фидбек еще не был отправлен
    if meeting.feedback_requested:
        return
    
    # Получаем участников встречи
    user1 = await get_user(session, meeting.user1_id)
    user2 = await get_user(session, meeting.user2_id)
    
    if not user1 or not user2:
        return
    
    # Формируем сообщение для первого пользователя
    message = (
        f"👋 Привет, {user1.full_name}!\n\n"
        f"Как прошла твоя встреча с {user2.full_name}? "
        f"Пожалуйста, оцени встречу, чтобы помочь нам улучшить Random Coffee!"
    )
    
    # Создаем клавиатуру для оценки
    keyboard = create_rating_keyboard(meeting.id, user2.telegram_id)
    
    # Отправляем запрос на фидбек первому пользователю
    try:
        await bot.send_message(
            chat_id=user1.telegram_id,
            text=message,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса фидбека пользователю {user1.telegram_id}: {e}")
    
    # Формируем сообщение для второго пользователя
    message = (
        f"👋 Привет, {user2.full_name}!\n\n"
        f"Как прошла твоя встреча с {user1.full_name}? "
        f"Пожалуйста, оцени встречу, чтобы помочь нам улучшить Random Coffee!"
    )
    
    # Создаем клавиатуру для оценки
    keyboard = create_rating_keyboard(meeting.id, user1.telegram_id)
    
    # Отправляем запрос на фидбек второму пользователю
    try:
        await bot.send_message(
            chat_id=user2.telegram_id,
            text=message,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса фидбека пользователю {user2.telegram_id}: {e}")
    
    # Обновляем статус запроса фидбека
    meeting.feedback_requested = True
    meeting.is_completed = True
    await session.commit()


async def send_reactivation_reminder(bot: Bot, session: AsyncSession):
    """
    Отправляет напоминания неактивным пользователям, предлагая вернуться в программу.
    
    Args:
        bot: Бот для отправки сообщений
        session: Сессия базы данных
    """
    # Получаем всех зарегистрированных, но неактивных пользователей
    query = select(User).where(
        and_(
            User.registration_complete == True,
            User.is_active == False
        )
    )
    
    result = await session.execute(query)
    inactive_users = result.scalars().all()
    
    # Если тестовый режим активен, добавляем уведомление об этом
    test_mode_notice = ""
    if is_test_mode_active():
        test_mode_notice = "\n\n🧪 *ТЕСТОВЫЙ РЕЖИМ АКТИВЕН*\nВстречи происходят в ускоренном темпе!"
    
    # Формируем сообщение
    message = (
        f"👋 Привет! Давно не виделись в Random Coffee!\n\n"
        f"Мы заметили, что вы некоторое время не участвуете в наших встречах. "
        f"Сейчас отличное время, чтобы вернуться и познакомиться с новыми коллегами!\n\n"
        f"Хотите снова участвовать в случайных встречах?{test_mode_notice}"
    )
    
    # Создаем клавиатуру
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(
        text="✅ Активировать участие",
        callback_data="reactivate"
    ))
    kb.add(InlineKeyboardButton(
        text="❌ Нет, спасибо",
        callback_data="decline_reactivation"
    ))
    
    # Отправляем сообщения
    for user in inactive_users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания пользователю {user.telegram_id}: {e}")
            continue 