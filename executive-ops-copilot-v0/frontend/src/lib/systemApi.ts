import type { HealthStatus } from '../types';
import { request } from './apiClient';

export const systemApi = {
  health: () => request<HealthStatus>('/api/health'),
};
