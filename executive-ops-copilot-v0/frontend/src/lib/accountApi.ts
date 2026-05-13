import { request } from './apiClient';

export const accountApi = {
  signOut: () =>
    request<{ status: string }>('/api/auth/signout', {
      method: 'POST',
      body: JSON.stringify({}),
    }),
};
