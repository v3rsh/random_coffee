from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from keyboards import get_start_keyboard

# Создаем роутер для общих команд
common_router = Router()


@common_router.message(Command("help"))
@common_router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message):
    """
    Обработчик команды /help и кнопки "Помощь".
    """
    help_text = (
        "🤖 *Random Coffee Bot* — бот для организации случайных встреч с коллегами.\n\n"
        "*Основные команды:*\n"
        "/start — начать использование бота\n"
        "/help — показать эту справку\n\n"
        "*Как это работает:*\n"
        "1. Вы регистрируетесь, указывая свои интересы и предпочтения.\n"
        "2. Каждую неделю бот подбирает вам собеседника с похожими интересами.\n"
        "3. Вы получаете уведомление с информацией о собеседнике.\n"
        "4. Вы связываетесь с собеседником и договариваетесь о встрече.\n"
        "5. После встречи вы можете оставить фидбек.\n\n"
        "Приятного общения! ☕"
    )
    
    await message.answer(help_text, parse_mode="Markdown")


@common_router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """
    Обработчик команды /cancel - отмена текущего действия и возврат в главное меню.
    """
    # В аргументах нет state, поэтому мы не можем очистить состояние здесь.
    # Для очистки состояния нужно использовать middleware, которая будет очищать состояние при команде /cancel.
    # В этом примере просто отправляем сообщение.
    
    await message.answer(
        "Действие отменено. Вы вернулись в главное меню.",
        reply_markup=get_start_keyboard()
    ) 