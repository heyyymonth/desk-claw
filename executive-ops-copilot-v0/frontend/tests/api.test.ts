import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/lib/api';
import type { ExecutiveRules, MeetingRequest, Recommendation } from '../src/types';

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses the current browser host for the default backend URL', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ status: 'ok', ollama: 'used' })));
    vi.stubGlobal('fetch', fetchMock);

    await api.health();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/health',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    );
  });

  it('surfaces FastAPI error messages instead of raw JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 502,
          text: () => Promise.resolve(JSON.stringify({ error: { code: 'ollama_invalid_output', message: 'Gemma returned invalid parse output.' } })),
        } as Response),
      ),
    );

    await expect(api.parseRequest('Schedule this.')).rejects.toThrow('Gemma returned invalid parse output.');
  });

  it('uses primary workflow endpoints instead of backend compatibility aliases', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(workflowResponse())));
    vi.stubGlobal('fetch', fetchMock);

    const parsed = await api.parseRequest('From Jordan: need 30 minutes with Dana tomorrow.');
    await api.recommendation(parsed, rulesResponse(), {
      busy_blocks: [{ title: 'Focus block', start: '2026-05-12T13:00:00-07:00', end: '2026-05-12T14:00:00-07:00' }],
    });
    await api.draftResponse(parsed, recommendationResponse());

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/api/requests/parse',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/api/recommendations/generate',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"parsed_request"'),
      }),
    );
    const recommendationInit = (fetchMock.mock.calls as unknown as Array<[string, RequestInit]>)[1][1];
    expect(JSON.parse(recommendationInit.body as string).calendar_blocks).toEqual([
      { title: 'Focus block', start: '2026-05-12T13:00:00-07:00', end: '2026-05-12T14:00:00-07:00', busy: true },
    ]);
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/api/drafts/generate',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ recommendation: recommendationResponse() }),
      }),
    );
  });

  it('uses primary rules and calendar endpoints', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ blocks: [] })));
    vi.stubGlobal('fetch', fetchMock);

    await api.defaultRules();
    await api.mockCalendar();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/api/rules/default',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/api/calendar/mock',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    );
  });

  it('links sign out to the backend auth endpoint', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ status: 'accepted' })));
    vi.stubGlobal('fetch', fetchMock);

    await api.signOut();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/auth/signout',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('loads AI performance metrics from the backend audit endpoint', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ total_events: 3, success_rate: 1 })));
    vi.stubGlobal('fetch', fetchMock);

    await api.aiMetrics();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/telemetry/ai/dashboard',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    );
  });
});

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  } as Response;
}

function workflowResponse(): MeetingRequest {
  return {
    raw_text: 'From Jordan: need 30 minutes with Dana tomorrow.',
    intent: {
      title: 'Meeting',
      requester: 'Jordan',
      duration_minutes: 30,
      priority: 'normal',
      meeting_type: 'other',
      attendees: ['Dana'],
      preferred_windows: [],
      constraints: [],
      missing_fields: [],
      sensitivity: 'low',
      async_candidate: false,
      escalation_required: false,
    },
  };
}

function rulesResponse(): ExecutiveRules {
  return {
    executive_name: 'Dana Lee',
    timezone: 'America/Los_Angeles',
    working_hours: { start: '09:00', end: '17:00' },
    protected_blocks: [],
    preferences: [],
  };
}

function recommendationResponse(): Recommendation {
  return {
    decision: 'schedule',
    confidence: 0.84,
    rationale: ['Found a safe slot.'],
    risks: [],
    risk_level: 'low',
    safe_action: 'human_review_before_external_action',
    proposed_slots: [],
    model_status: 'not_configured',
  };
}
