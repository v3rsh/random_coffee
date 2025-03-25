from datetime import datetime, timedelta
from typing import List

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Meeting, User, TopicType
from keyboards import get_topic_name, get_topic_emoji
from services.meeting_service import get_meeting, get_pending_feedback_meetings
from services.user_service import get_user


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