import random
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Meeting, Feedback
from services.user_service import get_recent_meeting_partners, get_matching_users
from services.test_mode_service import is_test_mode_active, get_accelerated_date, get_real_date


async def create_meeting(
    session: AsyncSession,
    user1_id: int,
    user2_id: int
) -> Meeting:
    """
    Создание новой встречи между двумя пользователями.
    
    Args:
        session: Сессия базы данных
        user1_id: ID первого пользователя
        user2_id: ID второго пользователя
    
    Returns:
        Созданная встреча
    """
    meeting = Meeting(
        user1_id=user1_id,
        user2_id=user2_id,
        is_confirmed=False
    )
    session.add(meeting)
    await session.commit()
    return meeting


async def get_meeting(
    session: AsyncSession,
    meeting_id: int
) -> Optional[Meeting]:
    """
    Получение встречи по ID.
    
    Args:
        session: Сессия базы данных
        meeting_id: ID встречи
    
    Returns:
        Встреча или None, если не найдена
    """
    result = await session.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    return result.scalar_one_or_none()


async def update_meeting(
    session: AsyncSession,
    meeting: Meeting,
    **kwargs
) -> Meeting:
    """
    Обновление данных встречи.
    
    Args:
        session: Сессия базы данных
        meeting: Объект встречи
        **kwargs: Атрибуты для обновления
    
    Returns:
        Обновленная встреча
    """
    for key, value in kwargs.items():
        if hasattr(meeting, key):
            setattr(meeting, key, value)
    
    await session.commit()
    return meeting


async def get_user_meetings(
    session: AsyncSession,
    user_id: int,
    only_active: bool = False
) -> List[Meeting]:
    """
    Получение всех встреч пользователя.
    
    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        only_active: Только активные встречи (без прошедших)
    
    Returns:
        Список встреч
    """
    query = (
        select(Meeting)
        .where(or_(
            Meeting.user1_id == user_id,
            Meeting.user2_id == user_id
        ))
    )
    
    if only_active:
        # Учитываем только встречи, которые еще не прошли
        current_time = datetime.utcnow()
        
        # В тестовом режиме используем ускоренное время
        if is_test_mode_active():
            current_time = get_accelerated_date(current_time)
        
        query = query.where(or_(
            Meeting.scheduled_date.is_(None),
            Meeting.scheduled_date >= current_time
        ))
    
    result = await session.execute(query.order_by(Meeting.created_at.desc()))
    return result.scalars().all()


async def get_pending_feedback_meetings(
    session: AsyncSession,
    user_id: int
) -> List[Meeting]:
    """
    Получение встреч, по которым нужен фидбек от пользователя.
    
    Args:
        session: Сессия базы данных
        user_id: ID пользователя
    
    Returns:
        Список встреч без фидбека
    """
    # Сначала находим все встречи пользователя
    user_meetings = await get_user_meetings(session, user_id)
    
    # Текущее время (с учетом тестового режима, если он активен)
    current_time = datetime.utcnow()
    if is_test_mode_active():
        current_time = get_accelerated_date(current_time)
    
    # Находим встречи без фидбека от указанного пользователя
    pending_feedback = []
    for meeting in user_meetings:
        # Проверяем только прошедшие встречи с датой
        if meeting.scheduled_date and meeting.scheduled_date < current_time:
            # Проверяем, оставил ли пользователь фидбек
            result = await session.execute(
                select(Feedback)
                .where(Feedback.meeting_id == meeting.id)
                .where(Feedback.from_user_id == user_id)
            )
            feedback = result.scalar_one_or_none()
            
            if not feedback:
                pending_feedback.append(meeting)
    
    return pending_feedback


async def create_meetings_for_users(session: AsyncSession) -> List[Meeting]:
    """
    Алгоритм создания пар для всех активных пользователей.
    
    Args:
        session: Сессия базы данных
    
    Returns:
        Список созданных встреч
    """
    from services.user_service import get_active_users
    
    # Получаем всех активных пользователей
    users = await get_active_users(session)
    if len(users) < 2:
        return []  # Недостаточно пользователей для создания пар
    
    # Перемешиваем пользователей случайным образом
    random.shuffle(users)
    
    # Словарь для хранения результатов
    matched_users = set()
    created_meetings = []
    
    # Обрабатываем каждого пользователя
    for user in users:
        # Если пользователь уже в паре, пропускаем
        if user.telegram_id in matched_users:
            continue
        
        # Получаем недавних собеседников, чтобы исключить их
        recent_partners = await get_recent_meeting_partners(session, user.telegram_id)
        
        # Получаем список подходящих пользователей
        matching_users = await get_matching_users(
            session, 
            user, 
            excluded_user_ids=list(matched_users) + recent_partners
        )
        
        # Если есть подходящие пользователи, создаем пару
        if matching_users:
            # Предпочитаем пользователей с похожими интересами
            best_match = None
            max_common_topics = -1
            
            for potential_match in matching_users:
                # Подсчитываем количество общих интересов
                common_topics = set(topic.value for topic in user.topics) & set(topic.value for topic in potential_match.topics)
                common_count = len(common_topics)
                
                if common_count > max_common_topics:
                    max_common_topics = common_count
                    best_match = potential_match
            
            # Если нашли подходящего пользователя
            if best_match:
                meeting = await create_meeting(session, user.telegram_id, best_match.telegram_id)
                created_meetings.append(meeting)
                
                # Отмечаем обоих пользователей как сопоставленных
                matched_users.add(user.telegram_id)
                matched_users.add(best_match.telegram_id)
    
    # Проверяем, остался ли один несопоставленный пользователь
    remaining_users = [u for u in users if u.telegram_id not in matched_users]
    if len(remaining_users) == 1 and len(users) >= 3:
        # Берем последнюю созданную пару и делаем из нее тройку
        last_meeting = created_meetings[-1]
        
        # Удаляем последнюю встречу
        await session.delete(last_meeting)
        await session.commit()
        
        # Создаем две новые встречи
        user1_id = last_meeting.user1_id
        user2_id = last_meeting.user2_id
        user3_id = remaining_users[0].telegram_id
        
        meeting1 = await create_meeting(session, user1_id, user3_id)
        meeting2 = await create_meeting(session, user2_id, user3_id)
        
        # Заменяем последнюю встречу двумя новыми
        created_meetings[-1] = meeting1
        created_meetings.append(meeting2)
    
    return created_meetings


async def add_feedback(
    session: AsyncSession,
    meeting_id: int,
    from_user_id: int,
    to_user_id: int,
    rating: int,
    comment: Optional[str] = None
) -> Feedback:
    """
    Добавление фидбека после встречи.
    
    Args:
        session: Сессия базы данных
        meeting_id: ID встречи
        from_user_id: ID пользователя, оставляющего фидбек
        to_user_id: ID пользователя, на которого оставляют фидбек
        rating: Оценка (1-5)
        comment: Комментарий (опционально)
    
    Returns:
        Объект фидбека
    """
    feedback = Feedback(
        meeting_id=meeting_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        rating=rating,
        comment=comment
    )
    session.add(feedback)
    await session.commit()
    return feedback 