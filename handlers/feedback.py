from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from keyboards import get_rating_keyboard, get_feedback_skip_keyboard
from services.meeting_service import get_meeting, add_feedback
from services.user_service import get_user
from states import FeedbackStates

# Создаем роутер для обратной связи
feedback_router = Router()


@feedback_router.callback_query(F.data.startswith("feedback:"))
async def process_feedback_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик запроса на оставление фидбека.
    """
    # Извлекаем данные из callback_data
    data_parts = callback.data.split(":")
    if len(data_parts) != 3:
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте позже.", show_alert=True)
        return
    
    meeting_id = int(data_parts[1])
    partner_id = int(data_parts[2])
    
    # Получаем данные о встрече и партнере
    meeting = await get_meeting(session, meeting_id)
    partner = await get_user(session, partner_id)
    
    if not meeting or not partner:
        await callback.answer("Информация о встрече не найдена.", show_alert=True)
        return
    
    # Сохраняем данные в контексте
    await state.update_data(
        meeting_id=meeting_id,
        partner_id=partner_id
    )
    
    # Запрашиваем оценку
    await callback.message.edit_text(
        f"Как вы оцените вашу встречу с {partner.full_name}?",
        reply_markup=get_rating_keyboard()
    )
    
    # Устанавливаем состояние ожидания рейтинга
    await state.set_state(FeedbackStates.waiting_for_rating)


@feedback_router.callback_query(StateFilter(FeedbackStates.waiting_for_rating), F.data.startswith("rating:"))
async def process_rating(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик выбора оценки.
    """
    # Извлекаем рейтинг из callback_data
    rating = int(callback.data.split(":")[1])
    
    # Сохраняем рейтинг в контексте
    await state.update_data(rating=rating)
    
    # Запрашиваем комментарий
    await callback.message.edit_text(
        "Спасибо за оценку! Хотите оставить комментарий о встрече?",
        reply_markup=get_feedback_skip_keyboard()
    )
    
    # Устанавливаем состояние ожидания комментария
    await state.set_state(FeedbackStates.waiting_for_comment)


@feedback_router.callback_query(StateFilter(FeedbackStates.waiting_for_comment), F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик пропуска комментария.
    """
    # Сохраняем пустой комментарий
    await state.update_data(comment=None)
    
    # Переходим к сохранению фидбека
    await save_feedback(callback, state, session)


@feedback_router.message(StateFilter(FeedbackStates.waiting_for_comment))
async def process_comment(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик комментария.
    """
    # Сохраняем комментарий в контексте
    await state.update_data(comment=message.text)
    
    # Отправляем сообщение о сохранении
    await message.answer("Спасибо за комментарий! Сохраняю ваш фидбек...")
    
    # Переходим к сохранению фидбека
    await save_feedback(message, state, session)


async def save_feedback(event, state: FSMContext, session: AsyncSession):
    """
    Сохраняет фидбек в базе данных.
    """
    # Получаем данные из контекста
    data = await state.get_data()
    meeting_id = data.get("meeting_id")
    partner_id = data.get("partner_id")
    rating = data.get("rating")
    comment = data.get("comment")
    
    # Получаем ID пользователя в зависимости от типа события
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
    else:  # Message
        user_id = event.from_user.id
    
    # Сохраняем фидбек
    try:
        await add_feedback(
            session,
            meeting_id=meeting_id,
            from_user_id=user_id,
            to_user_id=partner_id,
            rating=rating,
            comment=comment
        )
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем сообщение об успешном сохранении
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(
                "✅ Спасибо за ваш отзыв! Ваш фидбек поможет нам улучшить сервис Random Coffee."
            )
        else:  # Message
            await event.answer(
                "✅ Спасибо за ваш отзыв! Ваш фидбек поможет нам улучшить сервис Random Coffee."
            )
            
    except Exception as e:
        # В случае ошибки
        error_message = "Произошла ошибка при сохранении фидбека. Пожалуйста, попробуйте позже."
        
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(error_message)
        else:  # Message
            await event.answer(error_message)
        
        print(f"Ошибка при сохранении фидбека: {e}") 