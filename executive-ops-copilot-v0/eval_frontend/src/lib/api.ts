import type { EvalCase, EvalRun } from '../types';
import { request } from './apiClient';

export const api = {
  cases: () => request<EvalCase[]>('/api/eval-cases'),
  updateCase: (caseItem: EvalCase) =>
    request<EvalCase>(`/api/eval-cases/${caseItem.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: caseItem.name,
        description: caseItem.description,
        prompt: caseItem.prompt,
        expected: caseItem.expected,
        active: caseItem.active,
      }),
    }),
  runEvals: () => request<EvalRun>('/api/eval-runs', { method: 'POST' }),
  runs: () => request<EvalRun[]>('/api/eval-runs'),
  run: (id: string) => request<EvalRun>(`/api/eval-runs/${id}`),
};
