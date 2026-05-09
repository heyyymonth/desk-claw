import type {
  CalendarContext,
  DecisionLogEntry,
  DraftResponse,
  ExecutiveRules,
  HealthStatus,
  MeetingRequest,
  Recommendation,
  TimeWindow,
} from '../types';

const DEFAULT_API_BASE_URL =
  typeof window === 'undefined' ? 'http://localhost:8000' : `${window.location.protocol}//${window.location.hostname}:8000`;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

type BackendCalendarEvent = TimeWindow & { title: string };
type BackendCalendarResponse = { blocks: BackendCalendarEvent[] };
type BackendDecisionsResponse = { decisions: DecisionLogEntry[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function errorMessage(response: Response): Promise<string> {
  const fallback = `API request failed: ${response.status}`;
  const body = await response.text().catch(() => '');
  if (!body) {
    return fallback;
  }

  try {
    const payload = JSON.parse(body) as { error?: { message?: string }; detail?: string };
    return payload.error?.message ?? payload.detail ?? fallback;
  } catch {
    return body;
  }
}

function normalizeCalendar(payload: CalendarContext | BackendCalendarEvent[] | BackendCalendarResponse): CalendarContext {
  if (Array.isArray(payload)) {
    return {
      busy_blocks: payload,
      assumptions: ['Using seeded V0 mock calendar blocks from FastAPI.'],
      missing_context: [],
    };
  }
  if ('blocks' in payload) {
    return {
      busy_blocks: payload.blocks,
      assumptions: ['Using seeded V0 mock calendar blocks from FastAPI.'],
      missing_context: [],
    };
  }
  return payload;
}

function normalizeDecisions(payload: DecisionLogEntry[] | BackendDecisionsResponse): DecisionLogEntry[] {
  return Array.isArray(payload) ? payload : payload.decisions;
}

export const api = {
  health: () => request<HealthStatus>('/api/health'),
  defaultRules: () => request<ExecutiveRules>('/api/default-rules'),
  mockCalendar: async () =>
    normalizeCalendar(await request<CalendarContext | BackendCalendarEvent[] | BackendCalendarResponse>('/api/mock-calendar')),
  parseRequest: (rawText: string) =>
    request<MeetingRequest>('/api/parse-request', {
      method: 'POST',
      body: JSON.stringify({ raw_text: rawText }),
    }),
  recommendation: (meetingRequest: MeetingRequest, rules: ExecutiveRules) =>
    request<Recommendation>('/api/recommendation', {
      method: 'POST',
      body: JSON.stringify({ meeting_request: meetingRequest, rules }),
    }),
  draftResponse: (meetingRequest: MeetingRequest, recommendation: Recommendation) =>
    request<DraftResponse>('/api/draft-response', {
      method: 'POST',
      body: JSON.stringify({ meeting_request: meetingRequest, recommendation }),
    }),
  decisions: async () => normalizeDecisions(await request<DecisionLogEntry[] | BackendDecisionsResponse>('/api/decisions')),
  logDecision: (entry: Omit<DecisionLogEntry, 'id' | 'created_at'>) =>
    request<DecisionLogEntry>('/api/decisions', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),
};

export function getDefaultRules(): Promise<ExecutiveRules> {
  return api.defaultRules();
}

export function parseRequest(rawText: string): Promise<MeetingRequest> {
  return api.parseRequest(rawText);
}

export function getRecommendation(meetingRequest: MeetingRequest, rules: ExecutiveRules): Promise<Recommendation> {
  return api.recommendation(meetingRequest, rules);
}

export function getDraftResponse(meetingRequest: MeetingRequest, recommendation: Recommendation): Promise<DraftResponse> {
  return api.draftResponse(meetingRequest, recommendation);
}

export function logDecision(
  meetingRequest: MeetingRequest,
  recommendation: Recommendation,
  finalDecision: string,
  notes: string,
): Promise<DecisionLogEntry> {
  return api.logDecision({
    meeting_request: meetingRequest,
    recommendation,
    final_decision: finalDecision,
    notes,
  });
}
