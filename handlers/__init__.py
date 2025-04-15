from handlers.registration import registration_router
from handlers.feedback import feedback_router
from handlers.common import common_router
from handlers.admin import admin_router
from handlers.pairing import pairing_router

__all__ = [
    'registration_router',
    'feedback_router',
    'common_router',
    'admin_router',
    'pairing_router'
] 