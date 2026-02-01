from .budget import router as budget_router
from .calendar import router as calendar_router
from .camera import router as camera_router
from .events import router as events_router
from .optimize import router as optimize_router
from .presage import router as presage_router
from .recovery import router as recovery_router
from .team import router as team_router

__all__ = [
    "budget_router",
    "calendar_router",
    "camera_router",
    "events_router",
    "optimize_router",
    "presage_router",
    "recovery_router",
    "team_router",
]
