import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '@/api/client';
import { createApiKey, listApiKeys, revokeApiKey } from '@/api/endpoints';

vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
  getAuthHeaders: vi.fn(() => ({})),
}));

describe('API key management endpoints', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates a scoped key and omits an empty expiration', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { success: true, data: { key: 'secret' } } });

    await createApiKey('生产任务');

    expect(apiClient.post).toHaveBeenCalledWith('/api/api-keys', {
      name: '生产任务',
      scopes: ['ppt:generate'],
    });
  });

  it('sends expiration days when selected', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { success: true } });

    await createApiKey('测试环境', 90);

    expect(apiClient.post).toHaveBeenCalledWith('/api/api-keys', {
      name: '测试环境',
      scopes: ['ppt:generate'],
      expires_in_days: 90,
    });
  });

  it('lists and revokes keys through the logged-in management API', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { success: true, data: { api_keys: [] } } });
    vi.mocked(apiClient.delete).mockResolvedValue({ data: { success: true } });

    await listApiKeys();
    await revokeApiKey('key-1');

    expect(apiClient.get).toHaveBeenCalledWith('/api/api-keys');
    expect(apiClient.delete).toHaveBeenCalledWith('/api/api-keys/key-1');
  });
});
