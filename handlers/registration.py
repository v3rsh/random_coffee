from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, TopicType, MeetingFormat
from keyboards import (
    get_start_keyboard, get_skip_keyboard, get_meeting_format_keyboard,
    get_topics_keyboard, get_confirmation_keyboard, get_topic_name, get_topic_emoji
)
from services.user_service import get_user, create_user, update_user, add_user_topic, remove_user_topic
from states import RegistrationStates

# Создаем роутер для регистрации
registration_router = Router()


@registration_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """
    Обработчик команды /start - приветствие и начало регистрации.
    """
    user = await get_user(session, message.from_user.id)
    
    if user and user.registration_complete:
        # Пользователь уже зарегистрирован
        await message.answer(
            "Привет! Вы уже зарегистрированы в системе Random Coffee.\n"
            "Каждую неделю я буду искать вам собеседника для встречи. 👋",
            reply_markup=get_start_keyboard()
        )
    else:
        # Начинаем регистрацию
        if not user:
            # Если пользователя нет в базе, создаем его
            full_name = message.from_user.full_name
            username = message.from_user.username
            user = await create_user(session, message.from_user.id, full_name, username)
        
        # Приветственное сообщение
        await message.answer(
            f"Привет, {user.full_name}! 👋\n\n"
            "Добро пожаловать в Random Coffee! Это бот для организации случайных встреч с коллегами. "
            "Я помогу вам познакомиться с интересными людьми и расширить круг общения.\n\n"
            "Давайте пройдем небольшую регистрацию, чтобы я мог подбирать вам подходящих собеседников."
        )
        
        # Запрашиваем имя
        await message.answer(
            "Как вас зовут? (Можно оставить то, что указано в профиле Telegram)",
            reply_markup=get_skip_keyboard()
        )
        
        # Устанавливаем состояние "ожидание имени"
        await message.bot.state_storage.set_state(message.from_user.id, RegistrationStates.waiting_for_name)


@registration_router.message(StateFilter(RegistrationStates.waiting_for_name))
async def process_name(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик имени пользователя.
    """
    user = await get_user(session, message.from_user.id)
    
    # Если пользователь не выбрал "Пропустить", обновляем имя
    if message.text != "⏩ Пропустить":
        await update_user(session, user, full_name=message.text)
    
    # Запрашиваем отдел/роль
    await message.answer(
        "Укажите ваш отдел или роль (например, «Разработка», «Маркетинг» и т.д.):",
        reply_markup=get_skip_keyboard()
    )
    
    # Устанавливаем следующее состояние
    await state.set_state(RegistrationStates.waiting_for_department)


@registration_router.message(StateFilter(RegistrationStates.waiting_for_department))
async def process_department(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик отдела/роли пользователя.
    """
    user = await get_user(session, message.from_user.id)
    
    # Если пользователь не выбрал "Пропустить", обновляем отдел
    if message.text != "⏩ Пропустить":
        await update_user(session, user, department=message.text)
    
    # Запрашиваем рабочие часы
    await message.answer(
        "Укажите ваши рабочие часы или время, удобное для общения.\n"
        "Например, «10:00-18:00» или «После обеда»:",
        reply_markup=get_skip_keyboard()
    )
    
    # Устанавливаем следующее состояние
    await state.set_state(RegistrationStates.waiting_for_work_hours)


@registration_router.message(StateFilter(RegistrationStates.waiting_for_work_hours))
async def process_work_hours(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик рабочих часов пользователя.
    """
    user = await get_user(session, message.from_user.id)
    
    # Если пользователь не выбрал "Пропустить", обновляем рабочие часы
    if message.text != "⏩ Пропустить":
        work_hours = message.text
        # Если указаны часы в формате HH:MM-HH:MM, разбиваем на начало и конец
        if "-" in work_hours and len(work_hours.split("-")) == 2:
            start_time, end_time = work_hours.split("-")
            start_time = start_time.strip()
            end_time = end_time.strip()
            
            # Если время в правильном формате, сохраняем отдельно начало и конец
            if ":" in start_time and ":" in end_time:
                await update_user(session, user, work_hours_start=start_time, work_hours_end=end_time)
            else:
                # Иначе сохраняем как строку
                await update_user(session, user, work_hours_start=work_hours)
        else:
            # Если формат не распознан, сохраняем как строку
            await update_user(session, user, work_hours_start=work_hours)
    
    # Запрашиваем формат встречи
    await message.answer(
        "Выберите предпочтительный формат встречи:",
        reply_markup=get_meeting_format_keyboard()
    )
    
    # Устанавливаем следующее состояние
    await state.set_state(RegistrationStates.waiting_for_meeting_format)


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_meeting_format), F.data.startswith("format:"))
async def process_meeting_format(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик выбора формата встречи.
    """
    # Извлекаем формат из callback data
    format_value = callback.data.split(":")[1]
    meeting_format = MeetingFormat(format_value)
    
    # Обновляем данные пользователя
    user = await get_user(session, callback.from_user.id)
    await update_user(session, user, meeting_format=meeting_format)
    
    # Запрашиваем интересующие темы
    await callback.message.edit_text(
        "Выберите интересующие вас темы для общения (можно выбрать несколько):",
        reply_markup=get_topics_keyboard()
    )
    
    # Сохраняем выбранные темы в контексте
    await state.update_data(selected_topics=[])
    
    # Устанавливаем следующее состояние
    await state.set_state(RegistrationStates.waiting_for_topics)


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_topics), F.data.startswith("topic:"))
async def process_topic_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик выбора тем для общения.
    """
    # Получаем текущие выбранные темы
    user_data = await state.get_data()
    selected_topics = user_data.get("selected_topics", [])
    
    # Извлекаем тему из callback data
    topic_value = callback.data.split(":")[1]
    
    # Добавляем или удаляем тему из списка
    if topic_value in selected_topics:
        selected_topics.remove(topic_value)
    else:
        selected_topics.append(topic_value)
    
    # Обновляем данные в контексте
    await state.update_data(selected_topics=selected_topics)
    
    # Обновляем клавиатуру с отметками выбранных тем
    await callback.message.edit_reply_markup(reply_markup=get_topics_keyboard(selected_topics))


@registration_router.callback_query(StateFilter(RegistrationStates.waiting_for_topics), F.data == "topics_done")
async def process_topics_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик завершения выбора тем.
    """
    # Получаем выбранные темы
    user_data = await state.get_data()
    selected_topics = user_data.get("selected_topics", [])
    
    # Если не выбрано ни одной темы, просим выбрать хотя бы одну
    if not selected_topics:
        await callback.answer("Пожалуйста, выберите хотя бы одну тему", show_alert=True)
        return
    
    # Обновляем темы пользователя в базе данных
    user = await get_user(session, callback.from_user.id)
    
    # Сначала очищаем все темы пользователя
    user.topics.clear()
    await session.commit()
    
    # Затем добавляем выбранные темы
    for topic_value in selected_topics:
        topic = TopicType(topic_value)
        await add_user_topic(session, user, topic)
    
    # Подготавливаем сводку данных для подтверждения
    meeting_format_name = {
        MeetingFormat.OFFLINE: "Оффлайн 🏢",
        MeetingFormat.ONLINE: "Онлайн 💻",
        MeetingFormat.ANY: "Любой 🔄"
    }.get(user.meeting_format, "Не указан")
    
    topics_str = "\n".join([
        f"• {get_topic_emoji(TopicType(topic))} {get_topic_name(TopicType(topic))}"
        for topic in selected_topics
    ])
    
    work_hours = f"{user.work_hours_start}"
    if user.work_hours_end:
        work_hours += f" - {user.work_hours_end}"
    
    summary = (
        f"📋 *Ваши данные для Random Coffee:*\n\n"
        f"👤 *Имя:* {user.full_name}\n"
        f"🏢 *Отдел/роль:* {user.department or 'Не указан'}\n"
        f"🕒 *Рабочие часы:* {work_hours or 'Не указаны'}\n"
        f"🤝 *Формат встреч:* {meeting_format_name}\n\n"
        f"📌 *Интересующие темы:*\n{topics_str}\n\n"
        f"Всё верно?"
    )
    
    # Отправляем сводку с клавиатурой подтверждения
    await callback.message.edit_text(
        summary,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="Markdown"
    )
    
    # Устанавливаем состояние подтверждения
    await state.set_state(RegistrationStates.confirming_data)


@registration_router.callback_query(StateFilter(RegistrationStates.confirming_data), F.data == "confirm_registration")
async def confirm_registration(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик подтверждения регистрации.
    """
    # Помечаем регистрацию как завершенную
    user = await get_user(session, callback.from_user.id)
    await update_user(session, user, registration_complete=True)
    
    # Сбрасываем состояние FSM
    await state.clear()
    
    # Отправляем сообщение об успешной регистрации
    await callback.message.edit_text(
        "✅ Отлично! Ваша регистрация успешно завершена.\n\n"
        "Теперь вы участвуете в Random Coffee. Каждую неделю я буду подбирать вам собеседника "
        "по вашим интересам и предпочтениям.\n\n"
        "Когда будет найден подходящий собеседник, я отправлю вам уведомление с информацией о нём."
    )
    
    # Отправляем основное меню
    await callback.message.answer(
        "Что вы хотите сделать?",
        reply_markup=get_start_keyboard()
    )


@registration_router.callback_query(StateFilter(RegistrationStates.confirming_data), F.data == "change_registration")
async def change_registration(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик изменения данных регистрации.
    """
    # Возвращаемся к первому шагу регистрации
    await callback.message.edit_text(
        "Давайте начнем регистрацию заново. Как вас зовут?",
        reply_markup=get_skip_keyboard()
    )
    
    # Устанавливаем состояние "ожидание имени"
    await state.set_state(RegistrationStates.waiting_for_name)


@registration_router.message(F.text == "📝 Регистрация")
async def btn_registration(message: Message, session: AsyncSession):
    """
    Обработчик кнопки "Регистрация" из главного меню.
    """
    user = await get_user(session, message.from_user.id)
    
    if user and user.registration_complete:
        # Пользователь уже зарегистрирован
        await message.answer(
            "Вы уже зарегистрированы в системе Random Coffee.\n\n"
            "Хотите изменить свои данные?",
            reply_markup=get_confirmation_keyboard()
        )
    else:
        # Начинаем регистрацию
        await cmd_start(message, session) 