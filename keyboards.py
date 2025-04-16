from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database.models import MeetingFormat, TopicType, WeekDay, TimeSlot


def get_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для команды /start."""
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="📝 Регистрация"))
    kb.add(KeyboardButton(text="❓ Помощь"))
    return kb.as_markup(resize_keyboard=True)


def get_skip_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой пропуска."""
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="⏩ Пропустить"))
    return kb.as_markup(resize_keyboard=True)


def get_meeting_format_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора формата встречи."""
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(text="🏢 Оффлайн", callback_data=f"format:{MeetingFormat.OFFLINE.value}"),
        InlineKeyboardButton(text="💻 Онлайн", callback_data=f"format:{MeetingFormat.ONLINE.value}"),
        InlineKeyboardButton(text="🔄 Любой", callback_data=f"format:{MeetingFormat.ANY.value}")
    )
    return kb.as_markup()


def get_topics_keyboard(selected_topics=None) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора интересующих тем.
    
    Args:
        selected_topics: Список уже выбранных тем
    """
    if selected_topics is None:
        selected_topics = []
    
    kb = InlineKeyboardBuilder()
    
    for topic in TopicType:
        # Отметка выбранных тем
        prefix = "✅ " if topic.value in selected_topics else ""
        kb.add(InlineKeyboardButton(
            text=f"{prefix}{get_topic_emoji(topic)} {get_topic_name(topic)}",
            callback_data=f"topic:{topic.value}"
        ))
    
    # Добавляем кнопку Готово, если выбрана хотя бы одна тема
    if selected_topics:
        kb.add(InlineKeyboardButton(text="✅ Готово", callback_data="topics_done"))
    
    # Выстраиваем кнопки в столбец
    kb.adjust(1)
    return kb.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения данных."""
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_registration"),
        InlineKeyboardButton(text="🔄 Изменить", callback_data="change_registration")
    )
    kb.adjust(1)
    return kb.as_markup()


def get_rating_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки встречи."""
    kb = InlineKeyboardBuilder()
    emojis = ["😞", "😕", "😐", "🙂", "😄"]
    
    for i, emoji in enumerate(emojis, 1):
        kb.add(InlineKeyboardButton(
            text=f"{emoji} {i}",
            callback_data=f"rating:{i}"
        ))
    
    kb.adjust(5)
    return kb.as_markup()


def get_feedback_skip_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пропуска комментария."""
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_comment"))
    return kb.as_markup()


def get_topic_emoji(topic: TopicType) -> str:
    """Получить эмодзи для темы."""
    emoji_map = {
        TopicType.PRODUCT_DEVELOPMENT: "🚀",
        TopicType.HOBBIES: "🎨",
        TopicType.LANGUAGES: "🗣️",
        TopicType.GENERAL_CHAT: "💬"
    }
    return emoji_map.get(topic, "📌")


def get_topic_name(topic: TopicType) -> str:
    """Получить читаемое название темы."""
    name_map = {
        TopicType.PRODUCT_DEVELOPMENT: "Разработка продуктов",
        TopicType.HOBBIES: "Увлечения и хобби",
        TopicType.LANGUAGES: "Изучение языков",
        TopicType.GENERAL_CHAT: "Просто пообщаться"
    }
    return name_map.get(topic, str(topic))


def create_yes_no_keyboard(yes_text: str = "Да", no_text: str = "Нет") -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру с кнопками "Да" и "Нет".
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=yes_text, callback_data=yes_text),
            InlineKeyboardButton(text=no_text, callback_data=no_text)
        ]
    ])
    return keyboard


def create_meeting_format_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора формата встречи.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Онлайн", callback_data="Онлайн"),
        ],
        [
            InlineKeyboardButton(text="Оффлайн", callback_data="Оффлайн"),
        ],
        [
            InlineKeyboardButton(text="Не важно", callback_data="Не важно"),
        ]
    ])
    return keyboard


def create_interest_keyboard(interests, selected_interests=None, show_done=False) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора интересов.
    
    :param interests: Список доступных интересов
    :param selected_interests: Список ID выбранных интересов
    :param show_done: Показывать ли кнопку "Готово"
    :return: Инлайн-клавиатура
    """
    if selected_interests is None:
        selected_interests = []
    
    builder = InlineKeyboardBuilder()
    
    # Создаем кнопки для каждого интереса
    for interest in interests:
        # Добавляем галочку для выбранных интересов
        prefix = "✅ " if interest.id in selected_interests else ""
        
        button = InlineKeyboardButton(
            text=f"{prefix}{interest.emoji} {interest.name}",
            callback_data=f"interest_{interest.id}"
        )
        builder.add(button)
    
    # Располагаем кнопки в две колонки
    builder.adjust(2)
    
    # Добавляем кнопку "Готово", если нужно
    if show_done:
        done_button = InlineKeyboardButton(text="✅ Готово", callback_data="interests_done")
        # Добавляем кнопку как отдельную строку (на всю ширину)
        builder.row(done_button)
    
    return builder.as_markup()


def create_pairing_keyboard(users) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора пары.
    
    :param users: Список пользователей для выбора
    :return: Инлайн-клавиатура
    """
    buttons = []
    
    # Создаем кнопки для каждого пользователя
    for user in users:
        button = InlineKeyboardButton(
            text=user.full_name,
            callback_data=f"user_{user.telegram_id}"
        )
        buttons.append([button])
    
    # Добавляем кнопку "Другие варианты"
    more_button = InlineKeyboardButton(text="🔄 Другие варианты", callback_data="more_users")
    buttons.append([more_button])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_rating_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для оценки встречи.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 🌟", callback_data="rating_1"),
            InlineKeyboardButton(text="3 🌟", callback_data="rating_3"),
            InlineKeyboardButton(text="5 🌟", callback_data="rating_5"),
        ]
    ])
    return keyboard


def create_feedback_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру после оценки встречи.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да!", callback_data="participate_again"),
            InlineKeyboardButton(text="Позже", callback_data="participate_later"),
        ],
        [
            InlineKeyboardButton(text="Предложить улучшения", callback_data="suggest_improvement"),
        ]
    ])
    return keyboard


def create_weekday_keyboard(selected_days=None) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора дней недели.
    
    :param selected_days: Список уже выбранных дней (значения WeekDay)
    :return: Инлайн-клавиатура
    """
    if selected_days is None:
        selected_days = []
    
    builder = InlineKeyboardBuilder()
    
    # Словарь с русскими названиями дней недели и эмодзи
    weekday_names = {
        WeekDay.MONDAY: "🗓️ Понедельник",
        WeekDay.TUESDAY: "🗓️ Вторник",
        WeekDay.WEDNESDAY: "🗓️ Среда",
        WeekDay.THURSDAY: "🗓️ Четверг",
        WeekDay.FRIDAY: "🗓️ Пятница"
    }
    
    # Создаем кнопки для каждого дня недели
    for day in WeekDay:
        # Добавляем галочку для выбранных дней
        prefix = "✅ " if day.value in selected_days else ""
        
        button = InlineKeyboardButton(
            text=f"{prefix}{weekday_names[day]}",
            callback_data=f"day_{day.value}"
        )
        builder.add(button)
    
    # Располагаем кнопки в один столбец
    builder.adjust(1)
    
    # Добавляем кнопку "Готово", если выбран хотя бы один день
    if selected_days:
        done_button = InlineKeyboardButton(text="✅ Готово", callback_data="days_done")
        # Добавляем кнопку как отдельную строку (на всю ширину)
        builder.row(done_button)
    
    return builder.as_markup()


def create_timeslot_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора временного слота.
    
    :return: Инлайн-клавиатура
    """
    builder = InlineKeyboardBuilder()
    
    # Словарь с русскими названиями временных слотов и эмодзи
    timeslot_names = {
        TimeSlot.SLOT_8_10: "🕘 8:00 - 10:00",
        TimeSlot.SLOT_10_12: "🕙 10:00 - 12:00",
        TimeSlot.SLOT_12_14: "🕛 12:00 - 14:00",
        TimeSlot.SLOT_14_16: "🕝 14:00 - 16:00",
        TimeSlot.SLOT_16_18: "🕡 16:00 - 18:00"
    }
    
    # Создаем кнопки для каждого временного слота
    for slot in TimeSlot:
        button = InlineKeyboardButton(
            text=timeslot_names[slot],
            callback_data=f"slot_{slot.value}"
        )
        builder.add(button)
    
    # Располагаем кнопки в один столбец
    builder.adjust(1)
    
    return builder.as_markup() 