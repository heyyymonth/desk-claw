import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, it, vi } from 'vitest';
import { App } from '../../src/App';

const parseResponse = {
  parsed_request: {
    raw_text: 'Important customer meeting from Alex for 30 minutes next week',
    intent: {
      title: 'Customer meeting',
      requester: 'Alex',
      duration_minutes: 30,
      priority: 'high',
      meeting_type: 'customer',
      attendees: ['Alex'],
      preferred_windows: [],
      constraints: ['Requested for next week'],
      missing_fields: [],
      sensitivity: 'low',
      async_candidate: false,
      escalation_required: false,
    },
  },
  recommendation: {
    decision: 'schedule',
    confidence: 0.84,
    rationale: ['Found a safe slot.'],
    risks: [],
    risk_level: 'low',
    proposed_slots: [{ start: '2026-05-11T11:00:00-07:00', end: '2026-05-11T11:30:00-07:00', reason: 'Open' }],
    safe_action: 'propose_slot_for_human_review_before_final_send',
    model_status: 'used',
  },
  draft_response: {
    subject: 'Re: Customer meeting',
    body: 'Please confirm whether that works on your side.',
    tone: 'warm',
    draft_type: 'accept',
    model_status: 'used',
  },
  next_steps: ['Propose slot for human review before final send', 'Found a safe slot.'],
};

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.endsWith('/api/health')) {
          return Promise.resolve(jsonResponse({ status: 'ok', model_provider: 'openai', model: 'gpt-5.5' }));
        }
        if (url.endsWith('/api/parse-request')) return Promise.resolve(jsonResponse(parseResponse));
        return Promise.reject(new Error(`Unhandled ${url}`));
      }),
    );
  });

  it('runs the request-response parser workflow', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    );

    await screen.findByText('openai/gpt-5.5 · FastAPI');
    await userEvent.clear(screen.getByLabelText('Incoming request'));
    await userEvent.type(screen.getByLabelText('Incoming request'), parseResponse.parsed_request.raw_text);
    await userEvent.click(screen.getByRole('button', { name: /run agent/i }));

    await screen.findByText('Customer meeting');
    await screen.findAllByText('Found a safe slot.');
    await screen.findByText('Propose slot for human review before final send');
    await screen.findByText('Please confirm whether that works on your side.');
  });
});

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  } as Response;
}
