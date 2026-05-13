const DEFAULT_API_BASE_URL =
  typeof window === 'undefined' ? 'http://localhost:8000' : `${window.location.protocol}//${window.location.hostname}:8000`;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
const ADMIN_API_KEY = import.meta.env.VITE_ADMIN_API_KEY;
const ACTOR_AUTH_TOKEN = import.meta.env.VITE_ACTOR_AUTH_TOKEN;

export type ActorIdentity = { actorId: string; email?: string; name?: string };

let currentActorIdentity: ActorIdentity | undefined;

export function setActorIdentity(actor: ActorIdentity) {
  currentActorIdentity = actor;
}

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

export function adminHeaders(): HeadersInit {
  return ADMIN_API_KEY ? { 'X-DeskAI-Admin-Key': ADMIN_API_KEY } : {};
}

export function actorHeaders(): HeadersInit {
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
