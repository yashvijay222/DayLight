import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers import baseline, budget, calendar, camera, events, optimize, presage, recovery, team
from app.routers.presage import get_presage_client
from app.utils.mock_data import generate_mock_week, generate_team_metrics
from app.services.event_classifier import classify_event
from app.services.cognitive_calculator import calculate_events_with_proximity

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def auto_connect_presage():
    """Automatically connect to the Presage daemon on startup."""
    client = get_presage_client()
    
    # Give the presage container time to start
    max_attempts = 10
    for attempt in range(max_attempts):
        if client.connect():
            logger.info("Connected to Presage daemon on startup")
            return True
        logger.info(f"Waiting for Presage daemon... attempt {attempt + 1}/{max_attempts}")
        await asyncio.sleep(2)
    
    logger.warning("Could not connect to Presage daemon - will retry on demand")
    return False


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
                if event.requires_tool_switch is None:
                    event.requires_tool_switch = False
    
    # Calculate costs with proximity awareness
    calculate_events_with_proximity(events_list)
    return events_list


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed data
    logger.info("Starting DayLight Backend...")
    app.state.events = generate_mock_week()
    app.state.team_metrics = generate_team_metrics()
    app.state.sage_sessions = {}
    app.state.daily_session_costs = []  # List of {"date": "YYYY-MM-DD", "amount": float}
    app.state.oauth_tokens = {}
    # Auto-connect to Presage daemon (non-blocking)
    asyncio.create_task(auto_connect_presage())
    app.state.last_suggestions = None
    app.state.last_week_proposal = None
    yield
    
    # Shutdown: cleanup
    logger.info("Shutting down DayLight Backend...")
    client = get_presage_client()
    client.disconnect()
    logger.info("DayLight Backend shutdown complete")


app = FastAPI(title="CLB Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(baseline.router, prefix="/api", tags=["baseline"])
app.include_router(calendar.router, prefix="/api", tags=["calendar"])
app.include_router(camera.router, prefix="/api", tags=["camera"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(budget.router, prefix="/api", tags=["budget"])
app.include_router(optimize.router, prefix="/api", tags=["optimize"])
app.include_router(recovery.router, prefix="/api", tags=["recovery"])
app.include_router(presage.router, prefix="/api", tags=["presage"])
app.include_router(team.router, prefix="/api", tags=["team"])


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {"status": "healthy", "service": "daylight-backend"}
