from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers import budget, calendar, events, optimize, presage, recovery, team
from app.utils.mock_data import generate_mock_week, generate_team_metrics
from app.services.event_classifier import classify_event
from app.services.cognitive_calculator import calculate_events_with_proximity

load_dotenv()


def _classify_and_prepare_events(events_list):
    """Classify events using AI and calculate initial costs."""
    for event in events_list:
        if event.event_type is None:
            # Classify using AI (or fallback heuristics)
            event.event_type = classify_event(
                title=event.title,
                duration_minutes=event.duration_minutes,
                description=event.description,
            )
            
            # For non-meeting types, set default values for meeting-specific fields
            if event.event_type in ("recovery", "deep_work"):
                if event.participants is None:
                    event.participants = 1
                if event.has_agenda is None:
                    event.has_agenda = True
    
    # Calculate costs with proximity awareness
    calculate_events_with_proximity(events_list)
    return events_list


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed data
    raw_events = generate_mock_week()
    app.state.events = _classify_and_prepare_events(raw_events)
    app.state.team_metrics = generate_team_metrics()
    app.state.sage_sessions = {}
    app.state.oauth_tokens = {}
    app.state.last_suggestions = None
    app.state.last_week_proposal = None
    yield
    # Shutdown: cleanup (none needed for in-memory)


app = FastAPI(title="CLB Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calendar.router, prefix="/api", tags=["calendar"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(budget.router, prefix="/api", tags=["budget"])
app.include_router(optimize.router, prefix="/api", tags=["optimize"])
app.include_router(recovery.router, prefix="/api", tags=["recovery"])
app.include_router(presage.router, prefix="/api", tags=["presage"])
app.include_router(team.router, prefix="/api", tags=["team"])
