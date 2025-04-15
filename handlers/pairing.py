import logging
import random
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Meeting, Interest
from keyboards import create_pairing_keyboard
from services.user_service import get_user, get_active_users
from services.meeting_service import create_meeting, get_user_meetings
from states import PairingStates

# Создаем роутер для подбора пар
pairing_router = Router()
logger = logging.getLogger(__name__)


@pairing_router.message(Command("find"))
async def cmd_find(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик команды /find - запускает поиск собеседника
    """
    user = await get_user(session, message.from_user.id)
    
    if not user or not user.registration_complete:
        await message.answer(
            "Чтобы искать собеседников, нужно сначала зарегистрироваться.\n"
            "Отправь /start для регистрации."
        )
        return
    
    # Ищем подходящие варианты собеседников
    potential_matches = await find_potential_matches(session, user)
    
    if not potential_matches:
        await message.answer(
            "🔎 К сожалению, сейчас не удалось найти подходящих собеседников.\n"
            "Попробуй запросить поиск позже или дождись еженедельного подбора."
        )
        return
    
    # Выбираем до 3 случайных вариантов
    matches_to_show = random.sample(potential_matches, min(len(potential_matches), 3))
    
    # Сохраняем варианты в state
    await state.update_data(potential_matches=[user.telegram_id for user in matches_to_show])
    
    # Формируем сообщение с вариантами
    await message.answer(
        "🔎 Ищу тебе идеального собеседника...\n"
        "*Нашёл несколько вариантов:*",
        parse_mode="Markdown"
    )
    
    # Формируем описание каждого варианта
    for i, match in enumerate(matches_to_show, 1):
        # Получаем общие интересы
        common_interests = await get_common_interests(session, user, match)
        interests_text = ", ".join([f"{interest.emoji} {interest.name}" for interest in common_interests])
        
        user_info = (
            f"*{i}. {match.full_name}*, {match.role}\n"
            f"   Отдел: {match.department}\n"
            f"   Интересы: {interests_text}\n"
            f"   Доступен: {match.available_day}, {match.available_time}"
        )
        
        await message.answer(user_info, parse_mode="Markdown")
    
    # Предлагаем выбрать собеседника
    await message.answer(
        "Выбери коллегу или попроси другие варианты:",
        reply_markup=create_pairing_keyboard(matches_to_show)
    )
    
    # Устанавливаем состояние выбора собеседника
    await state.set_state(PairingStates.waiting_for_selection)


@pairing_router.callback_query(StateFilter(PairingStates.waiting_for_selection), F.data.startswith("user_"))
async def select_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик выбора собеседника
    """
    # Получаем ID выбранного пользователя
    selected_user_id = int(callback.data.split("_")[1])
    
    # Получаем текущего пользователя
    user = await get_user(session, callback.from_user.id)
    
    # Получаем выбранного пользователя
    selected_user = await get_user(session, selected_user_id)
    
    if not user or not selected_user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        await state.clear()
        return
    
    # Создаем встречу
    meeting = await create_meeting(
        session, 
        user1_id=user.telegram_id, 
        user2_id=selected_user.telegram_id
    )
    
    # Формируем сообщение с информацией о собеседнике
    common_interests = await get_common_interests(session, user, selected_user)
    interests_text = ", ".join([f"{interest.emoji} {interest.name}" for interest in common_interests])
    
    meeting_info = (
        f"✅ Отлично! Ты выбрал(а) встречу с *{selected_user.full_name}*\n\n"
        f"*О собеседнике:*\n"
        f"📋 Подразделение: {selected_user.department}\n"
        f"👨‍💼 Роль: {selected_user.role}\n"
        f"🤝 Формат: {selected_user.meeting_format.value if selected_user.meeting_format else 'Не указан'}\n"
        f"📍 Место встречи: {selected_user.city}, {selected_user.office}\n"
        f"🕒 Доступное время: {selected_user.available_day}, {selected_user.available_time}\n\n"
        f"*Общие интересы:*\n{interests_text}\n\n"
        f"Напиши собеседнику напрямую, чтобы договориться о встрече: @{selected_user.username}"
    )
    
    await callback.message.edit_text(meeting_info, parse_mode="Markdown")
    
    # Отправляем уведомление собеседнику
    partner_message = (
        f"🎉 Хорошие новости! *{user.full_name}* выбрал(а) тебя для встречи!\n\n"
        f"*О собеседнике:*\n"
        f"📋 Подразделение: {user.department}\n"
        f"👨‍💼 Роль: {user.role}\n"
        f"🤝 Формат: {user.meeting_format.value if user.meeting_format else 'Не указан'}\n"
        f"📍 Место встречи: {user.city}, {user.office}\n"
        f"🕒 Доступное время: {user.available_day}, {user.available_time}\n\n"
        f"*Общие интересы:*\n{interests_text}\n\n"
        f"Собеседник напишет тебе напрямую для согласования деталей встречи.\n"
        f"Также ты можешь сам(а) написать ему: @{user.username}"
    )
    
    try:
        await callback.bot.send_message(
            selected_user.telegram_id, 
            partner_message, 
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")
    
    # Очищаем состояние
    await state.clear()


@pairing_router.callback_query(StateFilter(PairingStates.waiting_for_selection), F.data == "more_users")
async def show_more_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик запроса других вариантов
    """
    # Получаем текущего пользователя
    user = await get_user(session, callback.from_user.id)
    
    # Получаем уже показанные варианты
    state_data = await state.get_data()
    shown_user_ids = state_data.get("potential_matches", [])
    
    # Ищем новые варианты
    potential_matches = await find_potential_matches(session, user, exclude_ids=shown_user_ids)
    
    if not potential_matches:
        # Если нет новых вариантов, предлагаем повторить поиск на следующей неделе
        await callback.message.edit_text(
            "К сожалению, сейчас нет других подходящих вариантов.\n"
            "Я попробую найти тебе другую пару на следующей неделе, "
            "или ты можешь написать в личные сообщения любому из коллег и договориться самостоятельно."
        )
        await state.clear()
        return
    
    # Выбираем до 3 случайных вариантов
    matches_to_show = random.sample(potential_matches, min(len(potential_matches), 3))
    
    # Добавляем новые варианты к уже показанным
    all_shown_ids = shown_user_ids + [user.telegram_id for user in matches_to_show]
    await state.update_data(potential_matches=all_shown_ids)
    
    # Формируем сообщение с вариантами
    await callback.message.edit_text(
        "🔎 Вот еще варианты собеседников:\n",
        parse_mode="Markdown"
    )
    
    # Формируем описание каждого варианта
    for i, match in enumerate(matches_to_show, 1):
        # Получаем общие интересы
        common_interests = await get_common_interests(session, user, match)
        interests_text = ", ".join([f"{interest.emoji} {interest.name}" for interest in common_interests])
        
        user_info = (
            f"*{i}. {match.full_name}*, {match.role}\n"
            f"   Отдел: {match.department}\n"
            f"   Интересы: {interests_text}\n"
            f"   Доступен: {match.available_day}, {match.available_time}"
        )
        
        await callback.bot.send_message(
            callback.from_user.id,
            user_info,
            parse_mode="Markdown"
        )
    
    # Предлагаем выбрать собеседника
    await callback.bot.send_message(
        callback.from_user.id,
        "Выбери коллегу или попроси другие варианты:",
        reply_markup=create_pairing_keyboard(matches_to_show)
    )


async def find_potential_matches(session: AsyncSession, user: User, exclude_ids=None):
    """
    Находит потенциальных собеседников для пользователя.
    
    :param session: Сессия базы данных
    :param user: Пользователь, для которого ищем собеседников
    :param exclude_ids: Список ID пользователей, которых нужно исключить из поиска
    :return: Список потенциальных собеседников
    """
    if exclude_ids is None:
        exclude_ids = []
    
    # Добавляем ID самого пользователя в список исключений
    exclude_ids.append(user.telegram_id)
    
    # Получаем всех активных пользователей, кроме исключенных
    query = select(User).where(
        User.is_active == True,
        User.registration_complete == True,
        User.telegram_id.notin_(exclude_ids)
    )
    
    # Фильтрация по формату встречи, если указан
    if user.meeting_format and user.meeting_format.value != "Не важно":
        query = query.where(
            or_(
                User.meeting_format == user.meeting_format,
                User.meeting_format.is_(None),
                User.meeting_format.value == "Не важно"
            )
        )
    
    # Получаем список последних встреч пользователя
    recent_meetings = await get_user_meetings(session, user.telegram_id, limit=5)
    recent_partner_ids = []
    
    for meeting in recent_meetings:
        if meeting.user1_id == user.telegram_id:
            recent_partner_ids.append(meeting.user2_id)
        else:
            recent_partner_ids.append(meeting.user1_id)
    
    # Исключаем недавних собеседников
    if recent_partner_ids:
        query = query.where(User.telegram_id.notin_(recent_partner_ids))
    
    # Получаем потенциальных собеседников
    result = await session.execute(query)
    potential_matches = result.scalars().all()
    
    # Сортируем по количеству общих интересов
    matches_with_scores = []
    for match in potential_matches:
        common_interests = await get_common_interests(session, user, match)
        matches_with_scores.append((match, len(common_interests)))
    
    # Сортируем по количеству общих интересов (от большего к меньшему)
    matches_with_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Возвращаем только пользователей, без оценок
    return [match for match, score in matches_with_scores if score > 0]


async def get_common_interests(session: AsyncSession, user1: User, user2: User):
    """
    Находит общие интересы между двумя пользователями.
    
    :param session: Сессия базы данных
    :param user1: Первый пользователь
    :param user2: Второй пользователь
    :return: Список общих интересов
    """
    # Получаем ID интересов первого пользователя
    user1_interests = [interest.id for interest in user1.interests]
    
    # Получаем ID интересов второго пользователя
    user2_interests = [interest.id for interest in user2.interests]
    
    # Находим пересечение
    common_interest_ids = set(user1_interests) & set(user2_interests)
    
    # Получаем объекты интересов
    common_interests = []
    for interest_id in common_interest_ids:
        interest = await session.get(Interest, interest_id)
        if interest:
            common_interests.append(interest)
    
    return common_interests 