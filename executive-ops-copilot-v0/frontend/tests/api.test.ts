import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/lib/api';

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses the current browser host for the default backend URL', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ status: 'ok' })));
    vi.stubGlobal('fetch', fetchMock);

    await api.health();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/health',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    );
  });

  it('sends raw request text to the unified parser endpoint', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(parseResponse())));
    vi.stubGlobal('fetch', fetchMock);

    await api.parseRequest('From Jordan: need 30 minutes with Dana tomorrow.');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/parse-request',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ raw_text: 'From Jordan: need 30 minutes with Dana tomorrow.' }),
      }),
    );
  });

  it('surfaces FastAPI error messages instead of raw JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 502,
          text: () =>
            Promise.resolve(JSON.stringify({ error: { code: 'ai_model_invalid_output', message: 'Model returned invalid parse output.' } })),
        } as Response),
      ),
    );

    await expect(api.parseRequest('Schedule this.')).rejects.toThrow('Model returned invalid parse output.');
  });
});

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  } as Response;
}

function parseResponse() {
  return {
    parsed_request: {
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
    },
    recommendation: {
      decision: 'clarify',
      confidence: 0.65,
      rationale: ['More context is needed.'],
      risks: [],
      risk_level: 'low',
      safe_action: 'ask_for_missing_context',
      proposed_slots: [],
      model_status: 'not_configured',
    },
    draft_response: {
      subject: 'Meeting request',
      body: 'Thanks for reaching out. We need a bit more information before proposing a time.',
      tone: 'concise',
      draft_type: 'clarify',
      model_status: 'not_configured',
    },
    next_steps: ['Ask for missing context', 'More context is needed.'],
  };
}
