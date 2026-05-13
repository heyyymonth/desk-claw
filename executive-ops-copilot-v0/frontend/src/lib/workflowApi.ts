import type {
  CalendarContext,
  DecisionLogEntry,
  DraftResponse,
  ExecutiveRules,
  MeetingRequest,
  Recommendation,
  TimeWindow,
} from '../types';
import { actorHeaders, request } from './apiClient';

type BackendCalendarEvent = TimeWindow & { title: string };
type BackendCalendarResponse = { blocks: BackendCalendarEvent[] };
type BackendDecisionsResponse = { decisions: DecisionLogEntry[] };
type BackendCalendarBlock = TimeWindow & { title: string; busy: boolean };

export const workflowApi = {
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
  draftResponse: (_meetingRequest: MeetingRequest, recommendation: Recommendation) =>
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
};

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
