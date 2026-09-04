from aiogram import Router

from .analysis import router as analysis_router
from .questionnaire import router as questionnaire_router
from .start import router as start_router
from .history import router as history_router
from .manual_parts import router as manual_parts_router
from .fallback import router as fallback_router


def build_router() -> Router:
    router = Router()
    router.include_routers(start_router, questionnaire_router, analysis_router, history_router, manual_parts_router, fallback_router)
    return router
