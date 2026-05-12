import type {
  CalendarContext,
  AiMetrics,
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
const ADMIN_API_KEY = import.meta.env.VITE_ADMIN_API_KEY;
const ACTOR_AUTH_TOKEN = import.meta.env.VITE_ACTOR_AUTH_TOKEN;

type BackendCalendarEvent = TimeWindow & { title: string };
type BackendCalendarResponse = { blocks: BackendCalendarEvent[] };
type BackendDecisionsResponse = { decisions: DecisionLogEntry[] };
type BackendCalendarBlock = TimeWindow & { title: string; busy: boolean };
export type ActorIdentity = { actorId: string; email?: string; name?: string };

let currentActorIdentity: ActorIdentity | undefined;

export function setActorIdentity(actor: ActorIdentity) {
  currentActorIdentity = actor;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

function adminHeaders(): HeadersInit {
  return ADMIN_API_KEY ? { 'X-DeskAI-Admin-Key': ADMIN_API_KEY } : {};
}

function actorHeaders(): HeadersInit {
  if (!ACTOR_AUTH_TOKEN || !currentActorIdentity) {
    return {};
  }
  return {
    'X-DeskAI-Actor-Token': ACTOR_AUTH_TOKEN,
    'X-Actor-Id': currentActorIdentity.actorId,
    ...(currentActorIdentity.email ? { 'X-Actor-Email': currentActorIdentity.email } : {}),
    ...(currentActorIdentity.name ? { 'X-Actor-Name': currentActorIdentity.name } : {}),
  };
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

function calendarBlocks(calendar?: CalendarContext): BackendCalendarBlock[] {
  return (calendar?.busy_blocks ?? []).map((block, index) => ({
    title: block.title ?? `Busy block ${index + 1}`,
    start: block.start,
    end: block.end,
    busy: true,
  }));
}

export const api = {
  health: () => request<HealthStatus>('/api/health'),
  aiMetrics: () => request<AiMetrics>('/api/telemetry/ai/dashboard', { headers: adminHeaders() }),
  defaultRules: () => request<ExecutiveRules>('/api/rules/default'),
  mockCalendar: async () =>
    normalizeCalendar(await request<CalendarContext | BackendCalendarEvent[] | BackendCalendarResponse>('/api/calendar/mock')),
  parseRequest: (rawText: string) =>
    request<MeetingRequest>('/api/requests/parse', {
      method: 'POST',
      headers: actorHeaders(),
      body: JSON.stringify({ raw_text: rawText }),
    }),
  recommendation: (meetingRequest: MeetingRequest, rules: ExecutiveRules, calendar?: CalendarContext) =>
    request<Recommendation>('/api/recommendations/generate', {
      method: 'POST',
      headers: actorHeaders(),
      body: JSON.stringify({ parsed_request: meetingRequest, rules, calendar_blocks: calendarBlocks(calendar) }),
    }),
  draftResponse: (meetingRequest: MeetingRequest, recommendation: Recommendation) =>
    request<DraftResponse>('/api/drafts/generate', {
      method: 'POST',
      headers: actorHeaders(),
      body: JSON.stringify({ recommendation }),
    }),
  decisions: async () => normalizeDecisions(await request<DecisionLogEntry[] | BackendDecisionsResponse>('/api/decisions')),
  logDecision: (entry: Omit<DecisionLogEntry, 'id' | 'created_at'>) =>
    request<DecisionLogEntry>('/api/decisions', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),
  signOut: () =>
    request<{ status: string }>('/api/auth/signout', {
      method: 'POST',
      body: JSON.stringify({}),
    }),
};

export function getDefaultRules(): Promise<ExecutiveRules> {
  return api.defaultRules();
}

export function parseRequest(rawText: string): Promise<MeetingRequest> {
  return api.parseRequest(rawText);
}

export function getRecommendation(meetingRequest: MeetingRequest, rules: ExecutiveRules, calendar?: CalendarContext): Promise<Recommendation> {
  return api.recommendation(meetingRequest, rules, calendar);
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
