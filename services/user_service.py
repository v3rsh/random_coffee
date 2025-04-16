from typing import List, Optional, Tuple

from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import User, Meeting, TopicType, MeetingFormat


async def get_user(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """
    Получение пользователя по telegram_id.
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None
) -> User:
    """
    Создание нового пользователя.
    """
    # Определяем максимальный номер пользователя
    result = await session.execute(
        select(func.max(User.user_number))
    )
    max_number = result.scalar_one_or_none()
    
    # Присваиваем порядковый номер (максимальный + 1 или 1, если пользователей нет)
    next_number = (max_number or 0) + 1
    
    user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        username=username,
        user_number=next_number,
        is_active=True,
        registration_complete=False
    )
    session.add(user)
    await session.commit()
    return user


async def update_user(
    session: AsyncSession,
    user: User,
    **kwargs
) -> User:
    """
    Обновление данных пользователя.
    """
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    await session.commit()
    return user


async def update_user(
    session: AsyncSession,
    user_or_id,
    data=None,
    **kwargs
) -> User:
    """
    Обновление данных пользователя.
    
    Args:
        session: Сессия базы данных
        user_or_id: Объект User или telegram_id пользователя
        data: Словарь с данными для обновления (опционально)
        **kwargs: Именованные аргументы с данными для обновления
    
    Returns:
        Обновленный объект User
    """
    # Получаем пользователя, если передан telegram_id
    if isinstance(user_or_id, int):
        user = await get_user(session, user_or_id)
        if not user:
            raise ValueError(f"Пользователь с ID {user_or_id} не найден")
    else:
        user = user_or_id
    
    # Обрабатываем словарь data, если он передан
    if data:
        for key, value in data.items():
            if hasattr(user, key):
                setattr(user, key, value)
    
    # Обрабатываем именованные аргументы
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    await session.commit()
    return user


async def add_user_topic(
    session: AsyncSession,
    user: User,
    topic: TopicType
) -> User:
    """
    Добавление темы интересов для пользователя.
    """
    # Проверяем, что топик является экземпляром перечисления TopicType
    if isinstance(topic, str):
        topic = TopicType(topic)
    
    # Добавляем топик в список интересов пользователя
    if topic not in user.topics:
        user.topics.append(topic)
        await session.commit()
    
    return user


async def remove_user_topic(
    session: AsyncSession,
    user: User,
    topic: TopicType
) -> User:
    """
    Удаление темы интересов у пользователя.
    """
    # Проверяем, что топик является экземпляром перечисления TopicType
    if isinstance(topic, str):
        topic = TopicType(topic)
    
    # Удаляем топик из списка интересов пользователя
    if topic in user.topics:
        user.topics.remove(topic)
        await session.commit()
    
    return user


async def get_active_users(session: AsyncSession) -> List[User]:
    """
    Получение всех активных пользователей.
    """
    result = await session.execute(
        select(User)
        .where(User.is_active == True)
        .where(User.registration_complete == True)
    )
    return result.scalars().all()


async def get_matching_users(
    session: AsyncSession, 
    user: User,
    excluded_user_ids: List[int] = None
) -> List[User]:
    """
    Получение подходящих пользователей для создания пар.
    
    Args:
        session: Сессия базы данных
        user: Пользователь, для которого ищем пары
        excluded_user_ids: Список ID пользователей, которых нужно исключить
    
    Returns:
        Список подходящих пользователей
    """
    if excluded_user_ids is None:
        excluded_user_ids = []
    
    # Исключаем самого пользователя из списка
    excluded_user_ids.append(user.telegram_id)
    
    # Базовый запрос с предварительной загрузкой interests
    query = (
        select(User)
        .options(selectinload(User.interests))
        .where(User.is_active == True)
        .where(User.registration_complete == True)
        .where(User.telegram_id.not_in(excluded_user_ids))
    )
    
    # Проверяем совместимость форматов встречи
    format_condition = or_(
        user.meeting_format == MeetingFormat.ANY,
        User.meeting_format == MeetingFormat.ANY,
        user.meeting_format == User.meeting_format
    )
    query = query.where(format_condition)
    
    # Выполняем запрос
    result = await session.execute(query)
    return result.scalars().all()


async def get_recent_meeting_partners(
    session: AsyncSession,
    user_id: int,
    limit: int = 5
) -> List[int]:
    """
    Получение недавних собеседников пользователя.
    
    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        limit: Максимальное количество недавних собеседников
    
    Returns:
        Список ID недавних собеседников
    """
    # Находим последние встречи
    query = (
        select(Meeting)
        .where(
            or_(
                Meeting.user1_id == user_id,
                Meeting.user2_id == user_id
            )
        )
        .order_by(Meeting.created_at.desc())
        .limit(limit)
    )
    
    result = await session.execute(query)
    meetings = result.scalars().all()
    
    # Извлекаем ID партнеров
    partner_ids = []
    for meeting in meetings:
        if meeting.user1_id == user_id:
            partner_ids.append(meeting.user2_id)
        else:
            partner_ids.append(meeting.user1_id)
    
    return partner_ids 