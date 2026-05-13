import type { AiMetrics } from '../types';
import { adminHeaders, request } from './apiClient';

export const adminApi = {
  aiMetrics: () => request<AiMetrics>('/api/telemetry/ai/dashboard', { headers: adminHeaders() }),
};
