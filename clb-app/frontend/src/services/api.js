import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
  timeout: 10000
});

const handle = async (promise) => {
  try {
    const response = await promise;
    return { data: response.data, error: null };
  } catch (error) {
    return { data: null, error: error?.response?.data || error.message };
  }
};

export const getAuthUrl = () => handle(api.get("/calendar/auth-url"));
export const handleCallback = (code) => handle(api.post("/calendar/callback", { code }));
export const syncCalendar = () => handle(api.post("/calendar/sync"));
export const pushToCalendar = () => handle(api.post("/calendar/push"));

export const fetchEvents = () => handle(api.get("/events"));
export const addEvent = (event) => handle(api.post("/events", event));
export const deleteEvent = (id) => handle(api.delete(`/events/${id}`));
export const updateEvent = (id, payload) => handle(api.patch(`/events/${id}`, payload));
export const updateFlexibility = (id, payload) =>
  handle(api.patch(`/events/${id}/flexibility`, payload));
export const enrichEvent = (id, payload) =>
  handle(api.patch(`/events/${id}/enrich`, payload));
export const getCostBreakdown = (id) =>
  handle(api.get(`/events/${id}/cost-breakdown`));
export const analyzeEvents = () => handle(api.get("/events/analyze"));

export const getDailyBudget = () => handle(api.get("/budget/daily"));
export const getWeeklyBudget = () => handle(api.get("/budget/weekly"));

export const getOptimizationSuggestions = () => handle(api.get("/optimize/suggestions"));
export const applySuggestion = (suggestionId) =>
  handle(api.post("/optimize/apply", { suggestion_id: suggestionId }));
export const applyAllSuggestions = (ids) =>
  handle(api.post("/optimize/apply-all", { ids }));
export const getWeekOptimization = () => handle(api.get("/optimize/week"));
export const applyWeekOptimization = () => handle(api.post("/optimize/week/apply"));

export const getRecoverySuggestions = () => handle(api.get("/recovery/suggestions"));
export const scheduleRecovery = (payload) => handle(api.post("/recovery/schedule", payload));

export const startSage = (eventId) =>
  handle(api.post("/presage/start-sage", { event_id: eventId }));
export const getSageReading = (sessionId) =>
  handle(api.get(`/presage/reading?session_id=${sessionId}`));
export const endSage = (sessionId) =>
  handle(api.post("/presage/end-sage", { session_id: sessionId }));

export const getTeamMetrics = () => handle(api.get("/team/health-score"));
