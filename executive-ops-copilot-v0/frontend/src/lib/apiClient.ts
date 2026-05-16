const DEFAULT_API_BASE_URL =
  typeof window === 'undefined' ? 'http://localhost:8000' : `${window.location.protocol}//${window.location.hostname}:8000`;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL === undefined ? DEFAULT_API_BASE_URL : import.meta.env.VITE_API_BASE_URL;

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
