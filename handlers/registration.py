import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import User, Interest, MeetingFormat
from database.interests_data import DEFAULT_INTERESTS
from keyboards import (
    create_meeting_format_keyboard,
    create_interest_keyboard,
    create_yes_no_keyboard,
    get_confirmation_keyboard,
    get_meeting_format_keyboard,
    create_weekday_keyboard,
    create_timeslot_keyboard
)
from services.user_service import get_user, create_user, update_user
from states import RegistrationStates

# Создаем роутер для регистрации
registration_router = Router()
logger = logging.getLogger(__name__)


@registration_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик команды /start
    """
    user = await get_user(session, message.from_user.id)
    
    # Если пользователь уже зарегистрирован и завершил регистрацию
    if user and user.registration_complete:
        await message.answer(
            "Привет! Ты уже зарегистрирован в боте Неслучайно. Ожидай уведомления о новых встречах!\n\n"
            "Используй /help чтобы узнать доступные команды."
        )
        await state.clear()
        return
    
    # Приветственное сообщение для новых пользователей
    await message.answer(
        "Привет! Если ты попал в этот бот, значит — это неслучайно 😌\n"
        "Здесь ты можешь:\n"
        "- найти единомышленников в билайне\n"
        "- обменяться опытом\n"
        "- обсудить интересные темы\n"
        "- просто приятно провести время\n"
        "Хочешь попробовать?",
        reply_markup=create_yes_no_keyboard("Да, хочу!", "Расскажи подробнее")
    )


@registration_router.callback_query(F.data == "Расскажи подробнее")
async def explain_more(callback: CallbackQuery):
    """
    Обработчик кнопки "Расскажи подробнее"
    """
    await callback.message.edit_text(
        "неслучайно — это:\n\n"
        "✅ встречи с коллегами из других подразделений и городов\n"
        "✅ 15-30 минут живого общения онлайн или в офисе\n"
        "✅ обсуждение только интересных тебе тем\n\n"
        "Как это работает:\n"
        "1. Ты заполняешь короткую анкету\n"
        "2. Я подбираю тебе коллегу с похожими интересами\n"
        "3. Вы встречаетесь в удобное время и общаетесь\n\n"
        "Попробуем? 😊",
        reply_markup=create_yes_no_keyboard("Да, участвую!", "Позже")
    )
    await callback.answer()


@registration_router.callback_query(F.data == "Позже")
async def postpone_registration(callback: CallbackQuery):
    """
    Обработчик кнопки "Позже"
    """
    await callback.message.edit_text(
        "Хорошо! Напомню тебе через неделю. \n"
        "А если передумаешь раньше — просто напиши «‎Участвую» 😉"
    )
    # Здесь можно добавить логику для создания отложенного напоминания
    await callback.answer()


@registration_router.message(F.text.lower() == "участвую")
@registration_router.callback_query(F.data == "Да, хочу!" or F.data == "Да, участвую!")
async def start_registration(message: Message | CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Начало регистрации пользователя
    """
    if isinstance(message, CallbackQuery):
        message_obj = message.message
        await message.answer()
    else:
        message_obj = message
    
    # Проверяем, есть ли пользователь в базе
    user = await get_user(session, message_obj.chat.id)
    if not user:
        # Создаем нового пользователя
        user = await create_user(
            session, 
            telegram_id=message_obj.chat.id,
            username=message_obj.chat.username,
            full_name=message_obj.chat.full_name
        )
    
    await message_obj.answer(
        "Отлично! Чтобы подобрать тебе подходящего собеседника, мне нужно немного информации. "
        "Давай заполним мини-анкету — это займёт не более 2 минут."
    )
    
    # Переходим к вопросу о имени
    await message_obj.answer(
        "1/6 🔹 Как тебя зовут? Напиши имя и ник в TG, например: Анна, @name_beeline"
    )
    await state.set_state(RegistrationStates.waiting_for_name)


@registration_router.message(StateFilter(RegistrationStates.waiting_for_name))
async def process_name(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработка имени пользователя
    """
    # Разделяем имя и username по запятой
    name_parts = message.text.split(",", 1)
    
    full_name = name_parts[0].strip()
    username = name_parts[1].strip() if len(name_parts) > 1 else None
    
    # Если есть username, убираем @ в начале, если он есть
    if username and username.startswith("@"):
        username = username[1:]
    
    # Сохраняем данные в state
    await state.update_data(full_name=full_name, username=username)
    
    # Обновляем информацию в базе данных
    await update_user(
        session, 
        message.from_user.id, 
        data={"full_name": full_name, "username": username}
    )
    
    # Переходим к вопросу о подразделении и роли
    await message.answer(
        "2/6 🔹 Твои подразделение и роль, например: менеджер, отдел коммуникаций"
    )
    await state.set_state(RegistrationStates.waiting_for_department)


@registration_router.message(StateFilter(RegistrationStates.waiting_for_department))
async def process_department(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработка подразделения и роли
    """
    # Сохраняем информацию о подразделении и роли
    department_role = message.text.split(",", 1)
    
    role = department_role[0].strip()
    department = department_role[1].strip() if len(department_role) > 1 else ""
    
    await state.update_data(department=department, role=role)
    
    # Обновляем в базе данных
    await update_user(
        session, 
        message.from_user.id, 
        {"department": department, "role": role}
    )
    
    # Переходим к вопросу о формате встречи
    await message.answer(
        "3/6 🔹 Формат встречи:",
        reply_markup=create_meeting_format_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_format)


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_format))
async def process_format(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработка формата встречи
    """
    # Определяем формат встречи из callback_data
    format_text = callback.data
    meeting_format = None
    
    if format_text == "Онлайн":
        meeting_format = MeetingFormat.ONLINE
    elif format_text == "Оффлайн":
        meeting_format = MeetingFormat.OFFLINE
    else:
        meeting_format = MeetingFormat.ANY
    
    # Сохраняем формат встречи
    await state.update_data(meeting_format=meeting_format.value)
    
    # Обновляем в базе данных
    await update_user(
        session, 
        callback.from_user.id, 
        {"meeting_format": meeting_format}
    )
    
    # Отвечаем на callback и редактируем сообщение
    await callback.answer()
    await callback.message.edit_text(f"Выбран формат: {meeting_format.value}")
    
    # Переходим к вопросу о городе и офисе
    await callback.message.answer(
        "4/6 🔹 Город и офис для встречи, например: «‎Москва, офис на Ленинском»"
    )
    await state.set_state(RegistrationStates.waiting_for_location)


@registration_router.message(StateFilter(RegistrationStates.waiting_for_location))
async def process_location(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработка города и офиса
    """
    location = message.text.split(",", 1)
    
    city = location[0].strip()
    office = location[1].strip() if len(location) > 1 else ""
    
    # Сохраняем информацию о локации
    await state.update_data(city=city, office=office)
    
    # Обновляем в базе данных
    await update_user(
        session, 
        message.from_user.id, 
        {"city": city, "office": office}
    )
    
    # Получаем список интересов из базы данных или создаем по умолчанию
    interests = await session.execute(select(Interest))
    interests = interests.scalars().all()
    
    if not interests:
        # Если интересов нет в базе, создаем их
        for interest_data in DEFAULT_INTERESTS:
            interest = Interest(name=interest_data["name"], emoji=interest_data["emoji"])
            session.add(interest)
        await session.commit()
        
        interests = await session.execute(select(Interest))
        interests = interests.scalars().all()
    
    # Переходим к вопросу об интересах
    await message.answer(
        "5/6 🔹 Твои интересы (выбери 1-3 варианта):",
        reply_markup=create_interest_keyboard(interests)
    )
    await state.set_state(RegistrationStates.waiting_for_interests)


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_interests), F.data.startswith("interest_"))
async def process_interests(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработка интересов пользователя
    """
    # Получаем текущие данные из state
    user_data = await state.get_data()
    selected_interests = user_data.get("selected_interests", [])
    
    # Извлекаем ID интереса из callback_data
    interest_id = int(callback.data.split("_")[1])
    
    # Проверяем, выбран ли интерес уже или нет
    if interest_id in selected_interests:
        selected_interests.remove(interest_id)
    else:
        # Ограничиваем количество выбранных интересов до 3
        if len(selected_interests) < 3:
            selected_interests.append(interest_id)
    
    # Сохраняем обновленный список интересов
    await state.update_data(selected_interests=selected_interests)
    
    # Получаем информацию о выбранных интересах для отображения
    interests_info = []
    for interest_id in selected_interests:
        interest = await session.get(Interest, interest_id)
        if interest:
            interests_info.append(f"{interest.emoji} {interest.name}")
    
    # Отвечаем на callback и обновляем сообщение
    await callback.answer()
    
    # Получаем все интересы для обновления клавиатуры
    all_interests = await session.execute(select(Interest))
    all_interests = all_interests.scalars().all()
    
    if selected_interests:
        selected_text = "Выбранные интересы:\n" + "\n".join(interests_info)
        if len(selected_interests) >= 1:
            selected_text += "\n\nНажми «Готово», если закончил выбор"
    else:
        selected_text = "Выбери хотя бы один интерес"
    
    await callback.message.edit_text(
        f"5/6 🔹 Твои интересы (выбери 1-3 варианта):\n\n{selected_text}",
        reply_markup=create_interest_keyboard(all_interests, selected_interests, show_done=(len(selected_interests) >= 1))
    )


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_interests), F.data == "interests_done")
async def process_interests_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработка завершения выбора интересов
    """
    await callback.answer()
    
    # Получаем пользователя из базы данных
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.message.answer("Ошибка: пользователь не найден")
        return
    
    user_data = await state.get_data()
    selected_interests = user_data.get("selected_interests", [])
    
    interests = []
    for interest_id in selected_interests:
        result = await session.execute(select(Interest).where(Interest.id == interest_id))
        interest = result.scalar_one_or_none()
        if interest:
            interests.append(interest)
    
    # Обновляем интересы пользователя
    await session.refresh(user, ["interests"])
    
    # Очищаем старые интересы
    user.interests = []
    await session.commit()
    
    # Добавляем новые интересы
    for interest in interests:
        user.interests.append(interest)
    await session.commit()
    
    # Переходим к выбору дней недели
    await callback.message.edit_text(
        "Интересы сохранены!"
    )
    
    await callback.message.answer(
        "6/7 🔹 Выбери дни недели, в которые ты готов(а) встречаться.",
        reply_markup=create_weekday_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_days)


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_days), F.data.startswith("day_"))
async def process_days(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора дней недели
    """
    await callback.answer()
    
    # Получаем выбранный день
    selected_day = callback.data.split("_")[1]
    
    # Получаем текущий список выбранных дней
    user_data = await state.get_data()
    selected_days = user_data.get("selected_days", [])
    
    # Добавляем или удаляем день из списка
    if selected_day in selected_days:
        selected_days.remove(selected_day)
    else:
        selected_days.append(selected_day)
    
    # Обновляем данные состояния
    await state.update_data(selected_days=selected_days)
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=create_weekday_keyboard(selected_days)
    )


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_days), F.data == "days_done")
async def process_days_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработка завершения выбора дней недели
    """
    await callback.answer()
    
    # Получаем выбранные дни
    user_data = await state.get_data()
    selected_days = user_data.get("selected_days", [])
    
    # Если дни не выбраны, просим пользователя выбрать хотя бы один день
    if not selected_days:
        await callback.answer("Пожалуйста, выберите хотя бы один день недели", show_alert=True)
        return
    
    # Преобразуем список дней в строку, разделенную запятыми
    days_str = ",".join(selected_days)
    
    # Сохраняем в БД
    await update_user(
        session, 
        callback.from_user.id, 
        {"available_days": days_str}
    )
    
    # Переходим к выбору временного слота
    await callback.message.edit_text(
        "Дни сохранены! Теперь выбери удобный временной слот для встреч."
    )
    
    await callback.message.answer(
        "7/7 🔹 В какое время тебе удобно встречаться?",
        reply_markup=create_timeslot_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_time_slot)


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_time_slot), F.data.startswith("slot_"))
async def process_time_slot(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработка выбора временного слота
    """
    await callback.answer()
    
    try:
        # Получаем выбранный слот
        selected_slot = callback.data.split("_")[1]
        
        # Сохраняем данные
        await state.update_data(available_time_slot=selected_slot)
        
        # Обновляем в БД
        await update_user(
            session, 
            callback.from_user.id, 
            {"available_time_slot": selected_slot}
        )
        
        # Переходим к добавлению фото
        await callback.message.edit_text(
            f"Отлично! Временной слот {selected_slot} сохранен."
        )
        
        # Спрашиваем о фото
        await callback.message.answer(
            "Хочешь добавить фото?",
            reply_markup=create_yes_no_keyboard("Да, загружаю", "Нет, спасибо")
        )
        await state.set_state(RegistrationStates.waiting_for_photo)
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении временного слота: {e}")
        await callback.message.answer("Произошла ошибка при сохранении временного слота. Пожалуйста, попробуйте еще раз.")


@registration_router.message(StateFilter(RegistrationStates.waiting_for_photo), F.photo)
async def process_photo(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработка фото пользователя
    """
    # Получаем фото с наилучшим разрешением
    photo = message.photo[-1]
    
    # Сохраняем ID фото
    await state.update_data(photo_id=photo.file_id)
    
    # Обновляем в базе данных
    await update_user(
        session, 
        message.from_user.id, 
        {"photo_id": photo.file_id}
    )
    
    # Завершаем регистрацию
    await complete_registration(message, state, session)


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_photo), F.data == "Нет, спасибо")
async def skip_photo(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Пропускаем добавление фото
    """
    await callback.answer()
    await callback.message.edit_text("Без проблем! Регистрация завершена без фото.")
    
    # Завершаем регистрацию
    await complete_registration(callback.message, state, session)


async def complete_registration(message: Message, state: FSMContext, session: AsyncSession):
    """
    Завершение процесса регистрации
    """
    # Обновляем статус регистрации в базе данных
    await update_user(
        session, 
        message.chat.id, 
        {"registration_complete": True}
    )
    
    # Получаем данные пользователя с явной загрузкой interests
    # Используем selectinload для предотвращения lazy loading
    query = select(User).where(User.telegram_id == message.chat.id).options(selectinload(User.interests))
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Произошла ошибка при завершении регистрации. Пожалуйста, попробуйте ещё раз.")
        return
    
    # Формируем сообщение с данными пользователя
    interests_text = ", ".join([interest.name for interest in user.interests]) if user.interests else "Не указаны"
    
    # Преобразуем строки дней в читаемый формат
    days_list = user.available_days.split(",") if user.available_days else []
    days_names = {
        "monday": "Понедельник",
        "tuesday": "Вторник",
        "wednesday": "Среда",
        "thursday": "Четверг",
        "friday": "Пятница"
    }
    days_text = ", ".join([days_names.get(day, day) for day in days_list]) if days_list else "Не указаны"
    
    user_info = (
        "🎉 Регистрация успешно завершена! 🎉\n\n"
        f"№{user.user_number}\n"
        f"Имя: {user.full_name}\n"
        f"Подразделение: {user.department}, {user.role}\n"
        f"Формат встреч: {user.meeting_format.value if user.meeting_format else 'Не указан'}\n"
        f"Локация: {user.city}, {user.office}\n"
        f"Интересы: {interests_text}\n"
        f"Дни для встреч: {days_text}\n"
        f"Время: {user.available_time_slot}\n\n"
        "Теперь я буду искать тебе идеального собеседника. Как только найду – сразу сообщу! 🕵️‍♂️"
    )
    
    await message.answer(user_info)
    
    # Очищаем состояние FSM
    await state.clear() 