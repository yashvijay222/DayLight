# DayLight - Cognitive Load Budgeting

**Manage your mental energy like you manage your time.**

DayLight is an intelligent calendar app that tracks and manages cognitive load in real-time. Using vital signs monitoring and smart scheduling algorithms, it helps you maintain optimal mental performance throughout your day.

---

## Overview

Most productivity tools focus on time management, but mental energy is the real limiting factor. DayLight introduces **Cognitive Load Budgeting** - a system that:

- Assigns cognitive costs to calendar events based on type, duration, and context
- Monitors your actual stress levels using real-time vital signs
- Provides a daily budget (20 points) to prevent cognitive overload
- Suggests optimizations to balance your schedule

## Key Features

### Real-Time Vital Signs Monitoring (Sage Mode)

Connect your webcam to monitor your physiological state during work sessions:

- **Pulse Rate** - Heart rate from facial blood flow analysis
- **Breathing Rate** - Respiratory rate detection
- **HRV (Heart Rate Variability)** - Primary stress indicator using RMSSD
- **Focus Score** - Computed from combined vital signs
- **Stress Level** - Real-time stress classification

The system learns your personal baselines over ~5 sessions for accurate readings.

### Intelligent Event Costing

Events are automatically assigned cognitive costs based on:

| Factor | Impact |
|--------|--------|
| Duration | Base cost scales with time |
| Participants | More people = higher cost |
| No Agenda | +4 points penalty |
| Deep Work | 50% cost reduction |
| Afternoon | 10% discount |
| Proximity | +2 points for back-to-back events |

### Schedule Optimization

**Individual Suggestions:**
- Cancel low-priority meetings
- Postpone non-urgent events
- Shorten meeting durations

**Week-Level Optimization:**
- Redistributes movable events across the week
- Balances daily cognitive load
- Maximizes recovery gaps between events
- Selectively apply only the changes you want

### Recovery System

When you're overdrafted, DayLight suggests recovery activities:

| Activity | Cost Reduction |
|----------|----------------|
| Micro Break (5-10 min) | -5 points |
| Walk/Stretch (15-30 min) | -8 points |
| Power Nap (20-30 min) | -10 points |
| Full Day Off | -40 points |

### Calendar Integration

- Google Calendar sync
- AI-powered event classification (meeting, deep_work, recovery, admin)
- Event enrichment with meeting details
- Flexibility marking (movable/unmovable)

### Team Dashboard

- Team health metrics
- High-risk member tracking
- Context switching analysis

---

## Tech Stack

### Frontend
- **React 18** with Vite
- **Tailwind CSS** for styling
- **Recharts** for data visualization
- **WebSocket** for real-time streaming

### Backend
- **FastAPI** (Python)
- **WebSocket** for real-time communication
- **Gemini API** for event classification
- **Google Calendar API** for calendar sync

### Vital Signs Processing
- **Presage SmartSpectra SDK** (C++)
- Video capture and processing
- TCP communication for metrics streaming

---

## Architecture

```
┌─────────────────┐
│    Frontend     │
│    (React)      │
└────────┬────────┘
         │ WebSocket (video frames + metrics)
         ▼
┌─────────────────┐
│    Backend      │
│   (FastAPI)     │
└────────┬────────┘
         │ TCP (video + control)
         ▼
┌─────────────────┐
│ Presage Daemon  │
│     (C++)       │
└────────┬────────┘
         │ SmartSpectra SDK
         ▼
┌─────────────────┐
│  Vital Signs    │
│   Extraction    │
└─────────────────┘
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- Docker & Docker Compose (for Presage daemon)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/your-repo/daylight.git
cd daylight
```

2. **Install frontend dependencies**

```bash
cd clb-app/frontend
npm install
```

3. **Install backend dependencies**

```bash
cd ../backend
pip install -r requirements.txt
```

4. **Set up environment variables**

```bash
# Backend (.env)
OPENAI_API_KEY=your_openai_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

5. **Start the services**

```bash
# Terminal 1 - Backend
cd clb-app/backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd clb-app/frontend
npm run dev

# Terminal 3 - Presage Daemon (optional, Linux only)
docker-compose up presage
```

6. **Open the app**

Navigate to `http://localhost:5173`

---

## Usage

### 1. Connect Your Calendar

Click "Connect Calendar" to sync with Google Calendar. Events will be automatically imported and classified.

### 2. Configure Event Flexibility

Go to **Schedule Analysis** and mark events as:
- **Movable** - Can be rescheduled for optimization
- **Unmovable** - Fixed in place

For meetings, add participant count and agenda status.

### 3. Monitor Your Budget

The **Dashboard** shows:
- Today's budget usage (out of 20 points)
- Weekly heatmap of cognitive load
- Upcoming events with costs

### 4. Start a Sage Session

During important meetings or work sessions:
1. Click "Start Sage" on an event
2. Allow camera access
3. Work normally while the system monitors your vitals
4. End the session to update your budget with actual stress data

### 5. Optimize Your Schedule

When overdrafted:
1. Review optimization suggestions
2. Generate a week optimization proposal
3. Select which changes to apply
4. Schedule recovery activities as needed

---

## API Endpoints

### Events
- `GET /api/events` - List all events
- `POST /api/events` - Create event
- `PATCH /api/events/{id}/flexibility` - Set flexibility
- `PATCH /api/events/{id}/enrich` - Add meeting details

### Budget
- `GET /api/budget/daily` - Get daily budget status
- `GET /api/budget/weekly` - Get weekly summary

### Optimization
- `GET /api/optimize/suggestions` - Get optimization suggestions
- `POST /api/optimize/apply` - Apply a suggestion
- `GET /api/optimize/week` - Generate week optimization
- `POST /api/optimize/week/apply` - Apply selected changes

### Sage (Vital Signs)
- `POST /api/presage/start-sage` - Start a session
- `GET /api/presage/reading` - Get current readings
- `POST /api/presage/end-sage` - End session

### Calendar
- `GET /api/calendar/auth-url` - Get OAuth URL
- `POST /api/calendar/sync` - Sync calendar

---

## How Cognitive Cost is Calculated

```
Base Cost = duration_minutes × 0.15

Adjustments:
  + (participants - 1) × 1.5    (meeting overhead)
  + 4                           (no agenda penalty)
  - base_cost × 0.5             (deep work discount)
  - base_cost × 0.1             (afternoon discount)
  + 2                           (proximity penalty per nearby event)
```

After a Sage session, the estimated cost is adjusted based on actual measured stress levels.

---

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

---

## License

MIT License - see LICENSE file for details.

---

## Acknowledgments

- **Presage Technologies** for the SmartSpectra vital signs SDK
- Built at **SpartaHack 2026**
