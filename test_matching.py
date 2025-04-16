import asyncio
import logging
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import delete, or_

from database.db import async_session_maker, init_db
from database.models import User, TopicType, MeetingFormat, Meeting
from services.user_service import create_user, update_user, add_user_topic
from services.meeting_service import create_meetings_for_users

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def delete_test_data():
    """
    Удаляет тестовые данные из базы данных (пользователей и связанные встречи).
    """
    test_ids = [100001, 100002, 100003, 100004, 100005]
    
    async with async_session_maker() as session:
        # Сначала удаляем встречи, связанные с тестовыми пользователями
        meetings_query = delete(Meeting).where(
            or_(
                Meeting.user1_id.in_(test_ids),
                Meeting.user2_id.in_(test_ids)
            )
        )
        meetings_result = await session.execute(meetings_query)
        await session.commit()
        logger.info(f"Удалено {meetings_result.rowcount} тестовых встреч")
        
        # Затем удаляем самих тестовых пользователей
        users_query = delete(User).where(User.telegram_id.in_(test_ids))
        users_result = await session.execute(users_query)
        await session.commit()
        logger.info(f"Удалено {users_result.rowcount} тестовых пользователей")


async def create_test_users():
    """
    Создает тестовых пользователей для проверки функционала.
    """
    async with async_session_maker() as session:
        # Пользователь 1
        user1 = await create_user(session, 100001, "Александр", "alexander")
        await update_user(
            session, 
            user1, 
            department="Разработка",
            work_hours_start="10:00",
            work_hours_end="18:00",
            meeting_format=MeetingFormat.OFFLINE,
            registration_complete=True
        )
        await add_user_topic(session, user1, TopicType.PRODUCT_DEVELOPMENT)
        await add_user_topic(session, user1, TopicType.HOBBIES)
        
        # Пользователь 2
        user2 = await create_user(session, 100002, "Мария", "maria")
        await update_user(
            session, 
            user2, 
            department="Маркетинг",
            work_hours_start="9:00",
            work_hours_end="17:00",
            meeting_format=MeetingFormat.ANY,
            registration_complete=True
        )
        await add_user_topic(session, user2, TopicType.HOBBIES)
        await add_user_topic(session, user2, TopicType.LANGUAGES)
        
        # Пользователь 3
        user3 = await create_user(session, 100003, "Дмитрий", "dmitry")
        await update_user(
            session, 
            user3, 
            department="Дизайн",
            work_hours_start="11:00",
            work_hours_end="19:00",
            meeting_format=MeetingFormat.ONLINE,
            registration_complete=True
        )
        await add_user_topic(session, user3, TopicType.PRODUCT_DEVELOPMENT)
        await add_user_topic(session, user3, TopicType.GENERAL_CHAT)
        
        # Пользователь 4
        user4 = await create_user(session, 100004, "Анна", "anna")
        await update_user(
            session, 
            user4, 
            department="HR",
            work_hours_start="9:00",
            work_hours_end="18:00",
            meeting_format=MeetingFormat.OFFLINE,
            registration_complete=True
        )
        await add_user_topic(session, user4, TopicType.GENERAL_CHAT)
        
        # Пользователь 5
        user5 = await create_user(session, 100005, "Сергей", "sergey")
        await update_user(
            session, 
            user5, 
            department="Финансы",
            work_hours_start="10:00",
            work_hours_end="19:00",
            meeting_format=MeetingFormat.ANY,
            registration_complete=True
        )
        await add_user_topic(session, user5, TopicType.HOBBIES)
        await add_user_topic(session, user5, TopicType.LANGUAGES)
        
        logger.info("Создано 5 тестовых пользователей")


async def test_matching():
    """
    Тестирует алгоритм формирования пар.
    """
    # Инициализируем базу данных
    await init_db()
    
    # Удаляем существующие тестовые данные
    await delete_test_data()
    
    # Создаем тестовых пользователей
    await create_test_users()
    
    # Запускаем формирование пар
    async with async_session_maker() as session:
        logger.info("Запуск алгоритма формирования пар...")
        meetings = await create_meetings_for_users(session)
        
        logger.info(f"Создано {len(meetings)} пар")
        
        # Выводим информацию о созданных парах
        for i, meeting in enumerate(meetings, 1):
            user1 = await session.get(User, meeting.user1_id)
            user2 = await session.get(User, meeting.user2_id)
            
            # Проверяем наличие атрибута topics
            if not hasattr(user1, 'topics') or not hasattr(user2, 'topics'):
                logger.warning(f"У одного из пользователей отсутствует атрибут topics")
                user1_topics = set()
                user2_topics = set()
            else:
                # Общие интересы
                user1_topics = set(topic.value for topic in user1.topics)
                user2_topics = set(topic.value for topic in user2.topics)
            
            common_topics = user1_topics.intersection(user2_topics)
            
            common_topics_str = ", ".join([
                TopicType(topic).name for topic in common_topics
            ]) if common_topics else "Нет общих интересов"
            
            logger.info(f"Пара #{i}: {user1.full_name} и {user2.full_name}")
            logger.info(f"  Общие интересы: {common_topics_str}")
            
            # Проверяем наличие атрибута meeting_format
            if hasattr(user1, 'meeting_format') and hasattr(user2, 'meeting_format') and user1.meeting_format and user2.meeting_format:
                logger.info(f"  Форматы встреч: {user1.meeting_format.value} и {user2.meeting_format.value}")
            else:
                logger.info(f"  Информация о форматах встреч недоступна")
            
            # Проверяем наличие атрибутов work_hours_start и work_hours_end перед их использованием
            if hasattr(user1, 'work_hours_start') and hasattr(user1, 'work_hours_end') and \
               hasattr(user2, 'work_hours_start') and hasattr(user2, 'work_hours_end'):
                logger.info(f"  Рабочие часы: {user1.work_hours_start}-{user1.work_hours_end} и "
                          f"{user2.work_hours_start}-{user2.work_hours_end}")
            else:
                logger.info(f"  Информация о рабочих часах недоступна")


if __name__ == "__main__":
    load_dotenv()
    try:
        asyncio.run(test_matching())
    except Exception as e:
        logger.error(f"Ошибка при выполнении теста: {e}", exc_info=True)
        import sys
        sys.exit(1) 