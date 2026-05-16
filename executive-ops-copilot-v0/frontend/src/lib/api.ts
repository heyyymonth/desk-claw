import type { HealthStatus, ParseRequestResponse } from '../types';
import { request } from './apiClient';

export const api = {
  health: () => request<HealthStatus>('/api/health'),
  parseRequest: (rawText: string) =>
    request<ParseRequestResponse>('/api/parse-request', {
      method: 'POST',
      body: JSON.stringify({ raw_text: rawText }),
    }),
};
