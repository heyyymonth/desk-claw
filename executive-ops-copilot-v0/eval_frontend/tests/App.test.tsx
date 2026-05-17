import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../src/App';
import type { EvalCase, EvalRun, ExpectedIntent } from '../src/types';

const expected: ExpectedIntent = {
  title: 'Customer renewal risk',
  requester: 'Jordan',
  duration_minutes: 30,
  priority: 'high',
  meeting_type: 'customer',
  attendees: ['Dana', 'Priya'],
  preferred_windows: [{ start: 'Tuesday afternoon', end: 'Tuesday afternoon' }],
  constraints: ['include Legal if possible'],
  missing_fields: [],
  sensitivity: 'medium',
  async_candidate: false,
  escalation_required: false,
};

const cases: EvalCase[] = [
  {
    id: 'case-1',
    name: 'Customer renewal',
    description: 'Renewal risk case',
    prompt: 'From Jordan at Atlas Finance: can Dana meet for 30 minutes next Tuesday afternoon?',
    expected,
    active: true,
    created_at: '2026-05-16T12:00:00Z',
    updated_at: '2026-05-16T12:00:00Z',
  },
];

const run: EvalRun = {
  id: 'run-1',
  created_at: '2026-05-16T12:05:00Z',
  total_cases: 1,
  passed_cases: 0,
  pass_rate: 0,
  avg_latency_ms: 415,
  results: [
    {
      id: 'result-1',
      run_id: 'run-1',
      case_id: 'case-1',
      case_name: 'Customer renewal',
      status: 'failed',
      passed: false,
      score: 0.8,
      latency_ms: 415,
      provider: 'ollama',
      model: 'gemma4:31b-cloud',
      raw_output: '{"requester":"From Jordan"}',
      normalized_output: { ...expected, requester: 'From Jordan' },
      expected,
      diffs: [
        {
          field: 'requester',
          expected: 'Jordan',
          actual: 'From Jordan',
          passed: false,
          message: 'Expected Jordan, got From Jordan',
        },
      ],
      error: null,
      created_at: '2026-05-16T12:05:00Z',
    },
  ],
};

function renderApp() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

function mockJson(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }));
}

describe('eval dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const path = input.toString();
        if (path === '/api/eval-cases' && !init?.method) {
          return mockJson(cases);
        }
        if (path === '/api/eval-runs' && !init?.method) {
          return mockJson([]);
        }
        if (path === '/api/eval-runs' && init?.method === 'POST') {
          return mockJson(run);
        }
        if (path === '/api/eval-runs/run-1') {
          return mockJson(run);
        }
        if (path === '/api/eval-cases/case-1' && init?.method === 'PUT') {
          return mockJson({ ...cases[0], name: 'Edited renewal' });
        }
        return Promise.resolve(new Response('{}', { status: 404 }));
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders seeded eval cases', async () => {
    renderApp();
    expect(await screen.findByText('Customer renewal')).toBeInTheDocument();
    expect(screen.getAllByText(/Jordan/).length).toBeGreaterThan(0);
  });

  it('edits a case and saves it', async () => {
    const user = userEvent.setup();
    renderApp();
    const nameInput = await screen.findByDisplayValue('Customer renewal');
    await user.clear(nameInput);
    await user.type(nameInput, 'Edited renewal');
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/eval-cases/case-1',
        expect.objectContaining({ method: 'PUT' }),
      );
    });
  });

  it('runs evals and shows failed field details', async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findAllByText('Customer renewal');
    await user.click(screen.getByRole('button', { name: /run 1 active cases/i }));

    expect(await screen.findByText('requester')).toBeInTheDocument();
    expect(screen.getAllByText('ollama / gemma4:31b-cloud').length).toBeGreaterThan(0);
    expect(screen.getByText(/Raw model output/i)).toBeInTheDocument();
  });
});
