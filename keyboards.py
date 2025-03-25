from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database.models import MeetingFormat, TopicType


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