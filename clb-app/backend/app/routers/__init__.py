from .events import router as events_router
from .budget import router as budget_router
from .calendar import router as calendar_router
from .optimize import router as optimize_router
from .recovery import router as recovery_router
from .presage import router as presage_router
from .team import router as team_router

__all__ = [
    "events_router",
    "budget_router", 
    "calendar_router",
    "optimize_router",
    "recovery_router",
    "presage_router",
    "team_router",
]
