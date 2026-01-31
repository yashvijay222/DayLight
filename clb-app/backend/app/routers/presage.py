import random
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Request

from app.models import PresageReading, SageSession
from app.services.cognitive_calculator import calculate_event_cost

router = APIRouter()


def _simulate_reading() -> PresageReading:
    hrv = random.randint(40, 80)
    breathing_rate = random.randint(12, 20)
    focus_score = random.randint(60, 95)
    stress_level = random.randint(20, 90)
    cognitive_delta = round((stress_level / 100) * 6)
    return PresageReading(
        hrv=hrv,
        breathing_rate=breathing_rate,
        focus_score=focus_score,
        stress_level=stress_level,
        timestamp=datetime.utcnow(),
        cognitive_cost_delta=cognitive_delta,
    )


@router.post("/presage/start-sage")
def start_sage(request: Request, payload: dict) -> dict:
    event_id = payload.get("event_id")
    estimated_cost = 0
    for event in request.app.state.events:
        if event.id == event_id:
            estimated_cost = calculate_event_cost(event)
            break
    session = SageSession(
        session_id=str(uuid4()),
        event_id=event_id,
        start_time=datetime.utcnow(),
        estimated_cost=estimated_cost,
    )
    request.app.state.sage_sessions[session.session_id] = session
    return {"status": "started", "session_id": session.session_id}


@router.get("/presage/reading")
def get_reading(request: Request) -> dict:
    session_id = request.query_params.get("session_id")
    session = request.app.state.sage_sessions.get(session_id)
    if not session:
        return {"status": "not_found"}
    reading = _simulate_reading()
    session.readings.append(reading)
    return {"status": "ok", "reading": reading}


@router.post("/presage/end-sage")
def end_sage(request: Request, payload: dict) -> dict:
    session_id = payload.get("session_id")
    session = request.app.state.sage_sessions.get(session_id)
    if not session:
        return {"status": "not_found"}
    
    if session.readings:
        avg_delta = round(
            sum(r.cognitive_cost_delta for r in session.readings)
            / len(session.readings)
        )
    else:
        avg_delta = 0
    
    session.actual_cost = session.estimated_cost + avg_delta
    session.debt_adjustment = session.actual_cost - session.estimated_cost
    
    # Update the event's actual_cost if this session was tied to an event
    if session.event_id:
        for event in request.app.state.events:
            if event.id == session.event_id:
                event.actual_cost = session.actual_cost
                break
    
    return {"status": "ended", "session": session}
