from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Meeting, Feedback
from services.user_service import get_user, get_active_users
from services.meeting_service import get_user_meetings
from services.test_mode_service import activate_test_mode, deactivate_test_mode, get_test_mode_status, is_test_mode_active
from scheduler import reconfigure_scheduler

# Создаем роутер для административных команд
admin_router = Router()


def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    """
    from app import ADMIN_USER_ID
    return str(user_id) == str(ADMIN_USER_ID)


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    """
    Обработчик команды /admin - показывает панель администратора.
    """
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к панели администратора.")
        return
    
    # Получаем статистику
    total_users = await session.scalar(select(func.count(User.telegram_id)))
    active_users = await session.scalar(
        select(func.count(User.telegram_id))
        .where(User.is_active == True)
        .where(User.registration_complete == True)
    )
    total_meetings = await session.scalar(select(func.count(Meeting.id)))
    total_feedback = await session.scalar(select(func.count(Feedback.id)))
    
    # Проверяем статус тестового режима
    test_mode_info = ""
    if is_test_mode_active():
        test_mode_status = get_test_mode_status()
        test_mode_info = f"\n\n🧪 *ТЕСТОВЫЙ РЕЖИМ*\n{test_mode_status}"
    
    # Формируем сообщение со статистикой
    stats_message = (
        "📊 *Статистика Random Coffee*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных пользователей: {active_users}\n"
        f"🤝 Всего встреч: {total_meetings}\n"
        f"📝 Всего отзывов: {total_feedback}\n\n"
        "*Доступные команды:*\n"
        "/adminstats - Подробная статистика\n"
        "/adminusers - Список пользователей\n"
        "/adminmeetings - Список встреч\n"
        "/adminfeedback - Отзывы пользователей"
        f"{test_mode_info}"
    )
    
    await message.answer(stats_message, parse_mode="Markdown")


@admin_router.message(Command("admin_stats", "adminstats"))
async def cmd_admin_stats(message: Message, session: AsyncSession):
    """
    Показывает подробную статистику.
    """
    if not is_admin(message.from_user.id):
        return
    
    # Статистика по отделам
    departments = await session.execute(
        select(User.department, func.count(User.telegram_id))
        .where(User.department.isnot(None))
        .group_by(User.department)
    )
    departments_stats = "\n".join([
        f"• {dept}: {count}" for dept, count in departments
    ]) if departments else "Нет данных"
    
    # Статистика по форматам встреч
    formats = await session.execute(
        select(User.meeting_format, func.count(User.telegram_id))
        .where(User.meeting_format.isnot(None))
        .group_by(User.meeting_format)
    )
    formats_stats = "\n".join([
        f"• {fmt.value}: {count}" for fmt, count in formats
    ]) if formats else "Нет данных"
    
    # Средняя оценка встреч
    avg_rating = await session.scalar(
        select(func.avg(Feedback.rating))
        .where(Feedback.rating.isnot(None))
    )
    avg_rating = round(avg_rating, 1) if avg_rating else "Нет данных"
    
    # Формируем сообщение
    stats_message = (
        "📈 *Подробная статистика*\n\n"
        f"🏢 *Распределение по отделам:*\n{departments_stats}\n\n"
        f"🤝 *Предпочитаемые форматы встреч:*\n{formats_stats}\n\n"
        f"⭐ *Средняя оценка встреч:* {avg_rating}"
    )
    
    await message.answer(stats_message, parse_mode="Markdown")


@admin_router.message(Command("admin_users", "adminusers"))
async def cmd_admin_users(message: Message, session: AsyncSession):
    """
    Показывает список пользователей.
    """
    if not is_admin(message.from_user.id):
        return
    
    # Получаем список пользователей
    users = await get_active_users(session)
    
    # Формируем сообщение
    users_message = "👥 *Список активных пользователей:*\n\n"
    
    for user in users:
        # Получаем количество встреч пользователя
        meetings_count = await session.scalar(
            select(func.count(Meeting.id))
            .where(
                (Meeting.user1_id == user.telegram_id) |
                (Meeting.user2_id == user.telegram_id)
            )
        )
        
        # Получаем среднюю оценку пользователя
        avg_rating = await session.scalar(
            select(func.avg(Feedback.rating))
            .where(Feedback.to_user_id == user.telegram_id)
            .where(Feedback.rating.isnot(None))
        )
        avg_rating = round(avg_rating, 1) if avg_rating else "Нет оценок"
        
        users_message += (
            f"*{user.full_name}*\n"
            f"ID: {user.telegram_id}\n"
            f"Отдел: {user.department or 'Не указан'}\n"
            f"Встреч: {meetings_count}\n"
            f"Средняя оценка: {avg_rating}\n\n"
        )
    
    await message.answer(users_message, parse_mode="Markdown")


@admin_router.message(Command("admin_meetings", "adminmeetings"))
async def cmd_admin_meetings(message: Message, session: AsyncSession):
    """
    Показывает список последних встреч.
    """
    if not is_admin(message.from_user.id):
        return
    
    # Получаем последние 10 встреч
    meetings = await session.execute(
        select(Meeting)
        .order_by(Meeting.created_at.desc())
        .limit(10)
    )
    meetings = meetings.scalars().all()
    
    # Формируем сообщение
    meetings_message = "🤝 *Последние встречи:*\n\n"
    
    for meeting in meetings:
        user1 = await get_user(session, meeting.user1_id)
        user2 = await get_user(session, meeting.user2_id)
        
        if not user1 or not user2:
            continue
        
        meetings_message += (
            f"*Встреча #{meeting.id}*\n"
            f"Участники: {user1.full_name} и {user2.full_name}\n"
            f"Дата создания: {meeting.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Статус: {'✅ Подтверждена' if meeting.is_confirmed else '⏳ Ожидает подтверждения'}\n\n"
        )
    
    await message.answer(meetings_message, parse_mode="Markdown")


@admin_router.message(Command("admin_feedback", "adminfeedback"))
async def cmd_admin_feedback(message: Message, session: AsyncSession):
    """
    Показывает последние отзывы.
    """
    if not is_admin(message.from_user.id):
        return
    
    # Получаем последние 10 отзывов
    feedbacks = await session.execute(
        select(Feedback)
        .order_by(Feedback.created_at.desc())
        .limit(10)
    )
    feedbacks = feedbacks.scalars().all()
    
    # Формируем сообщение
    feedback_message = "📝 *Последние отзывы:*\n\n"
    
    for feedback in feedbacks:
        from_user = await get_user(session, feedback.from_user_id)
        to_user = await get_user(session, feedback.to_user_id)
        
        if not from_user or not to_user:
            continue
        
        feedback_message += (
            f"*Отзыв от {from_user.full_name} для {to_user.full_name}*\n"
            f"Оценка: {'⭐' * feedback.rating}\n"
            f"Комментарий: {feedback.comment or 'Нет комментария'}\n"
            f"Дата: {feedback.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    await message.answer(feedback_message, parse_mode="Markdown")


@admin_router.message(Command("admin_testmode", "testmode", "test_mode"))
async def cmd_admin_testmode(message: Message, session: AsyncSession):
    """
    Скрытая команда для включения/отключения тестового режима.
    """
    if not is_admin(message.from_user.id):
        return
    
    # Получаем аргументы команды
    args = message.text.split()
    action = args[1].lower() if len(args) > 1 else "status"
    
    if action == "on":
        # Включаем тестовый режим
        if activate_test_mode():
            await message.answer("🧪 Тестовый режим активирован!\n"
                               "⏱ Время ускорено: 1 час = 5 рабочих дней\n"
                               "📅 Встречи и уведомления будут происходить чаще\n\n"
                               "Для отключения используйте: /testmode off")
            # Перенастраиваем планировщик
            reconfigure_scheduler()
        else:
            await message.answer("⚠️ Тестовый режим уже активен")
    
    elif action == "off":
        # Отключаем тестовый режим
        if deactivate_test_mode():
            await message.answer("🔄 Тестовый режим деактивирован\n"
                               "⏱ Восстановлен обычный временной режим\n\n"
                               "Для повторного включения используйте: /testmode on")
            # Перенастраиваем планировщик
            reconfigure_scheduler()
        else:
            await message.answer("⚠️ Тестовый режим не был активен")
    
    else:
        # Показываем статус
        status = get_test_mode_status()
        commands_help = (
            "\n\nДоступные команды:\n"
            "/testmode on - Включить тестовый режим\n"
            "/testmode off - Выключить тестовый режим"
        )
        await message.answer(f"{status}{commands_help}")


# Алиасы для скрытой команды тестового режима
@admin_router.message(Command("tm", "tmode"))
async def cmd_admin_testmode_alias(message: Message, session: AsyncSession):
    """
    Алиас для команды тестового режима.
    """
    await cmd_admin_testmode(message, session) 