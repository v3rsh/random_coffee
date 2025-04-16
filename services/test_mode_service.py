import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения статуса тестового режима
_test_mode_active = False

# Коэффициент ускорения: 1 час = 1 рабочий день (5 дней недели = 1 час)
TIME_ACCELERATION_FACTOR = 5 * 24

# Хранение времени активации тестового режима
_test_mode_start_time: Optional[datetime] = None


def activate_test_mode() -> bool:
    """
    Активирует тестовый режим.
    
    :return: True, если режим был активирован, False если он уже был активен
    """
    global _test_mode_active, _test_mode_start_time
    
    if _test_mode_active:
        return False
    
    _test_mode_active = True
    _test_mode_start_time = datetime.now()
    logger.info(f"Тестовый режим активирован в {_test_mode_start_time}")
    return True


def deactivate_test_mode() -> bool:
    """
    Деактивирует тестовый режим.
    
    :return: True, если режим был деактивирован, False если он не был активен
    """
    global _test_mode_active, _test_mode_start_time
    
    if not _test_mode_active:
        return False
    
    _test_mode_active = False
    _test_mode_start_time = None
    logger.info("Тестовый режим деактивирован")
    return True


def is_test_mode_active() -> bool:
    """
    Проверяет, активен ли тестовый режим.
    
    :return: True, если тестовый режим активен, иначе False
    """
    return _test_mode_active


def get_accelerated_date(real_date: datetime) -> datetime:
    """
    Конвертирует реальную дату в ускоренную в соответствии с тестовым режимом.
    
    :param real_date: Реальная дата
    :return: Ускоренная дата, если тестовый режим активен, иначе исходная дата
    """
    if not _test_mode_active or _test_mode_start_time is None:
        return real_date
    
    # Вычисляем разницу между текущим временем и началом тестового режима
    time_diff = datetime.now() - _test_mode_start_time
    
    # Конвертируем разницу в ускоренное время (только рабочие дни)
    accelerated_time_diff = time_diff * TIME_ACCELERATION_FACTOR
    
    # Добавляем ускоренную разницу к начальной дате
    accelerated_date = real_date + accelerated_time_diff
    
    return accelerated_date


def get_real_date(accelerated_date: datetime) -> datetime:
    """
    Конвертирует ускоренную дату обратно в реальную.
    
    :param accelerated_date: Ускоренная дата
    :return: Реальная дата, если тестовый режим активен, иначе исходная дата
    """
    if not _test_mode_active or _test_mode_start_time is None:
        return accelerated_date
    
    # Вычисляем разницу между ускоренной датой и текущим ускоренным временем
    accelerated_now = get_accelerated_date(datetime.now())
    accelerated_diff = accelerated_date - accelerated_now
    
    # Конвертируем разницу в реальное время
    real_diff = accelerated_diff / TIME_ACCELERATION_FACTOR
    
    # Добавляем реальную разницу к текущему времени
    real_date = datetime.now() + real_diff
    
    return real_date


def get_test_mode_status() -> str:
    """
    Возвращает текущий статус тестового режима.
    
    :return: Строка с информацией о статусе
    """
    if not _test_mode_active:
        return "Тестовый режим не активен"
    
    active_duration = datetime.now() - _test_mode_start_time
    accelerated_time = active_duration * TIME_ACCELERATION_FACTOR
    
    # Преобразуем в дни, часы, минуты
    days = accelerated_time.days
    hours = accelerated_time.seconds // 3600
    minutes = (accelerated_time.seconds % 3600) // 60
    
    status = (
        f"✅ Тестовый режим активен\n"
        f"⏱ Активен: {active_duration.total_seconds() // 60:.0f} мин.\n"
        f"⏩ Ускоренное время: {days} дн., {hours} час., {minutes} мин.\n"
        f"🔄 Коэффициент ускорения: x{TIME_ACCELERATION_FACTOR}"
    )
    
    return status 