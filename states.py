from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """
    Группа состояний для регистрации пользователя
    """
    waiting_for_name = State()       # Ожидание имени и ника в TG
    waiting_for_department = State() # Ожидание подразделения и роли
    waiting_for_format = State()     # Ожидание формата встречи
    waiting_for_location = State()   # Ожидание города и офиса
    waiting_for_interests = State()  # Ожидание интересов
    waiting_for_schedule = State()   # Ожидание графика встреч
    waiting_for_photo = State()      # Ожидание фото (опционально)


class FeedbackStates(StatesGroup):
    """
    Группа состояний для сбора фидбека после встречи
    """
    waiting_for_rating = State()      # Ожидание оценки встречи
    waiting_for_comment = State()     # Ожидание комментария (опционально)
    waiting_for_improvement = State() # Ожидание предложений по улучшению


class PairingStates(StatesGroup):
    """
    Группа состояний для подбора пары
    """
    waiting_for_selection = State()  # Ожидание выбора пользователя из предложенных вариантов
    waiting_for_confirmation = State()  # Ожидание подтверждения встречи 