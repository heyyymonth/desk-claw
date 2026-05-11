import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/lib/api';

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
      'http://localhost:8000/api/audit/ai/metrics',
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
