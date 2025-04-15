import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Feedback, Meeting
from keyboards import create_rating_keyboard, create_feedback_keyboard, create_yes_no_keyboard
from services.user_service import get_user
from services.meeting_service import get_meeting, update_meeting
from states import FeedbackStates

# Создаем роутер для обратной связи
feedback_router = Router()
logger = logging.getLogger(__name__)


@feedback_router.callback_query(F.data.startswith("rating_"))
async def process_rating(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик выбора оценки для встречи.
    """
    # Получаем рейтинг из callback_data
    rating = int(callback.data.split("_")[1])
    
    # Сохраняем рейтинг во временное хранилище
    await state.update_data(rating=rating)
    
    # Отвечаем на callback
    await callback.answer()
    
    # Редактируем сообщение
    await callback.message.edit_text(
        f"Ты поставил(а) {rating} {'🌟' * rating}\n\n"
        "Хочешь добавить комментарий? (необязательно)"
    )
    
    # Переходим к ожиданию комментария
    await state.set_state(FeedbackStates.waiting_for_comment)


@feedback_router.message(StateFilter(FeedbackStates.waiting_for_comment))
async def process_comment(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик комментария для встречи.
    """
    # Сохраняем комментарий во временное хранилище
    await state.update_data(comment=message.text)
    
    # Спрашиваем про участие в следующих встречах
    await message.answer(
        "Хочешь поучаствовать ещё раз?",
        reply_markup=create_feedback_keyboard()
    )


@feedback_router.callback_query(F.data == "participate_again")
async def process_participate_again(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик желания участвовать снова.
    """
    # Получаем данные из state
    feedback_data = await state.get_data()
    
    # Получаем данные о встрече из context (предполагается, что они там уже есть)
    meeting_id = feedback_data.get("meeting_id")
    to_user_id = feedback_data.get("to_user_id")
    
    if not meeting_id or not to_user_id:
        await callback.answer("Ошибка при сохранении отзыва. Попробуйте снова позже.", show_alert=True)
        await state.clear()
        return
    
    # Создаем новую запись обратной связи
    feedback = Feedback(
        meeting_id=meeting_id,
        from_user_id=callback.from_user.id,
        to_user_id=to_user_id,
        rating=feedback_data.get("rating"),
        comment=feedback_data.get("comment")
    )
    
    # Сохраняем в базу данных
    session.add(feedback)
    await session.commit()
    
    # Обновляем статус встречи
    meeting = await get_meeting(session, meeting_id)
    await update_meeting(session, meeting, is_completed=True)
    
    # Отвечаем пользователю
    await callback.answer()
    await callback.message.edit_text(
        "Спасибо за отзыв! Твоя оценка и комментарий сохранены.\n\n"
        "Я буду подбирать тебе новые встречи каждую неделю. Жди новых уведомлений! 😊"
    )
    
    # Очищаем состояние
    await state.clear()


@feedback_router.callback_query(F.data == "participate_later")
async def process_participate_later(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик желания отложить участие.
    """
    # Получаем данные из state
    feedback_data = await state.get_data()
    
    # Получаем данные о встрече из context
    meeting_id = feedback_data.get("meeting_id")
    to_user_id = feedback_data.get("to_user_id")
    
    if not meeting_id or not to_user_id:
        await callback.answer("Ошибка при сохранении отзыва. Попробуйте снова позже.", show_alert=True)
        await state.clear()
        return
    
    # Создаем новую запись обратной связи
    feedback = Feedback(
        meeting_id=meeting_id,
        from_user_id=callback.from_user.id,
        to_user_id=to_user_id,
        rating=feedback_data.get("rating"),
        comment=feedback_data.get("comment")
    )
    
    # Сохраняем в базу данных
    session.add(feedback)
    await session.commit()
    
    # Обновляем статус встречи
    meeting = await get_meeting(session, meeting_id)
    await update_meeting(session, meeting, is_completed=True)
    
    # Деактивируем пользователя на время
    user = await get_user(session, callback.from_user.id)
    user.is_active = False
    await session.commit()
    
    # Отвечаем пользователю
    await callback.answer()
    await callback.message.edit_text(
        "Спасибо за отзыв! Твоя оценка и комментарий сохранены.\n\n"
        "Я напомню тебе через неделю. А если передумаешь раньше — просто напиши «‎Участвую» 😉"
    )
    
    # Очищаем состояние
    await state.clear()


@feedback_router.callback_query(F.data == "suggest_improvement")
async def process_suggest_improvement(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик желания предложить улучшения.
    """
    await callback.answer()
    await callback.message.edit_text(
        "Что можно улучшить в работе бота? Твои предложения помогут сделать бота лучше!"
    )
    
    # Переходим к ожиданию предложений
    await state.set_state(FeedbackStates.waiting_for_improvement)


@feedback_router.message(StateFilter(FeedbackStates.waiting_for_improvement))
async def process_improvement(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик предложений по улучшению.
    """
    # Сохраняем предложение во временное хранилище
    await state.update_data(improvement_suggestion=message.text)
    
    # Получаем данные из state
    feedback_data = await state.get_data()
    
    # Получаем данные о встрече из context
    meeting_id = feedback_data.get("meeting_id")
    to_user_id = feedback_data.get("to_user_id")
    
    if not meeting_id or not to_user_id:
        await message.answer("Ошибка при сохранении отзыва. Попробуйте снова позже.")
        await state.clear()
        return
    
    # Создаем новую запись обратной связи
    feedback = Feedback(
        meeting_id=meeting_id,
        from_user_id=message.from_user.id,
        to_user_id=to_user_id,
        rating=feedback_data.get("rating"),
        comment=feedback_data.get("comment"),
        improvement_suggestion=feedback_data.get("improvement_suggestion")
    )
    
    # Сохраняем в базу данных
    session.add(feedback)
    await session.commit()
    
    # Обновляем статус встречи
    meeting = await get_meeting(session, meeting_id)
    await update_meeting(session, meeting, is_completed=True)
    
    # Отвечаем пользователю
    await message.answer(
        "Большое спасибо за твои предложения! Мы обязательно их учтем.\n\n"
        "Хочешь поучаствовать в следующих встречах?",
        reply_markup=create_yes_no_keyboard("Да!", "Позже")
    )


@feedback_router.callback_query(StateFilter(FeedbackStates.waiting_for_improvement), F.data == "Да!")
async def confirm_after_improvement(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик подтверждения участия после предложения улучшений.
    """
    # Отвечаем пользователю
    await callback.answer()
    await callback.message.edit_text(
        "Отлично! Буду подбирать тебе новые встречи каждую неделю. Жди новых уведомлений! 😊"
    )
    
    # Очищаем состояние
    await state.clear()


@feedback_router.callback_query(StateFilter(FeedbackStates.waiting_for_improvement), F.data == "Позже")
async def postpone_after_improvement(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик отложенного участия после предложения улучшений.
    """
    # Деактивируем пользователя на время
    user = await get_user(session, callback.from_user.id)
    user.is_active = False
    await session.commit()
    
    # Отвечаем пользователю
    await callback.answer()
    await callback.message.edit_text(
        "Хорошо! Я напомню тебе через неделю. А если передумаешь раньше — просто напиши «‎Участвую» 😉"
    )
    
    # Очищаем состояние
    await state.clear() 