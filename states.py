from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации пользователя."""
    waiting_for_name = State()
    waiting_for_department = State()
    waiting_for_work_hours = State()
    waiting_for_meeting_format = State()
    waiting_for_topics = State()
    confirming_data = State()


class FeedbackStates(StatesGroup):
    """Состояния для процесса сбора обратной связи после встречи."""
    waiting_for_rating = State()
    waiting_for_comment = State()
    confirming_feedback = State() 