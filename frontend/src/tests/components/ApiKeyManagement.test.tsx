import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import * as api from '@/api/endpoints';
import { ApiKeyManagement } from '@/components/settings/ApiKeyManagement';

vi.mock('@/api/endpoints', () => ({
  listApiKeys: vi.fn(),
  createApiKey: vi.fn(),
  revokeApiKey: vi.fn(),
}));

vi.mock('react-i18next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-i18next')>();
  return {
    ...actual,
    useTranslation: () => ({ i18n: { language: 'zh' } }),
  };
});

const translations: Record<string, string> = {
  'apiKeys.title': '开放 API 密钥',
  'apiKeys.description': '密钥说明',
  'apiKeys.docs': '查看 API 文档',
  'apiKeys.nameLabel': '密钥名称',
  'apiKeys.namePlaceholder': '输入名称',
  'apiKeys.expiryLabel': '有效期',
  'apiKeys.never': '永不过期',
  'apiKeys.days': '{{days}} 天',
  'apiKeys.create': '创建密钥',
  'apiKeys.creating': '正在创建',
  'apiKeys.oneTimeTitle': '请立即保存这个密钥',
  'apiKeys.oneTimeDescription': '只显示一次',
  'apiKeys.copy': '复制',
  'apiKeys.copied': '已复制',
  'apiKeys.dismiss': '我已保存',
  'apiKeys.listTitle': '现有密钥',
  'apiKeys.empty': '暂无密钥',
  'apiKeys.loading': '正在加载',
  'apiKeys.active': '可用',
  'apiKeys.revoked': '已撤销',
  'apiKeys.expired': '已过期',
  'apiKeys.scope': '权限',
  'apiKeys.createdAt': '创建于 {{date}}',
  'apiKeys.expiresAt': '到期 {{date}}',
  'apiKeys.noExpiry': '无到期日',
  'apiKeys.lastUsed': '最后使用 {{date}}',
  'apiKeys.neverUsed': '尚未使用',
  'apiKeys.revoke': '撤销',
  'apiKeys.revokeTitle': '撤销 API 密钥',
  'apiKeys.revokeConfirm': '确定撤销 {{name}}？',
  'apiKeys.revokeAction': '确认撤销',
  'apiKeys.cancel': '取消',
  'apiKeys.createdMessage': '密钥已创建',
  'apiKeys.revokedMessage': '密钥已撤销',
  'apiKeys.loadFailed': '加载失败',
  'apiKeys.createFailed': '创建失败',
  'apiKeys.revokeFailed': '撤销失败',
  'apiKeys.copyFailed': '复制失败',
  'apiKeys.retry': '重试',
};

vi.mock('@/hooks/useT', () => ({
  useT: () => (key: string, params?: Record<string, string | number>) => {
    let text = translations[key] || key;
    Object.entries(params || {}).forEach(([name, value]) => {
      text = text.replace(`{{${name}}}`, String(value));
    });
    return text;
  },
}));

const activeKey = {
  id: 'key-1',
  name: '生产服务',
  prefix: 'lt_live_abc',
  scopes: ['ppt:generate'],
  is_active: true,
  expires_at: null,
  last_used_at: null,
  created_at: '2026-07-23T10:00:00',
  revoked_at: null,
};

describe('ApiKeyManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listApiKeys).mockResolvedValue({ data: { api_keys: [] } });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('creates a key and shows its plaintext once', async () => {
    vi.mocked(api.createApiKey).mockResolvedValue({
      data: {
        api_key: activeKey,
        key: 'lt_live_abc.one-time-secret',
        warning: 'save it',
      },
    });

    render(<MemoryRouter><ApiKeyManagement /></MemoryRouter>);
    await screen.findByText('暂无密钥');

    fireEvent.change(screen.getByLabelText('密钥名称'), { target: { value: '生产服务' } });
    fireEvent.click(screen.getByRole('button', { name: '创建密钥' }));

    expect(await screen.findByText('lt_live_abc.one-time-secret')).toBeInTheDocument();
    expect(api.createApiKey).toHaveBeenCalledWith('生产服务', undefined);
    expect(screen.getByText('请立即保存这个密钥')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '复制' }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith('lt_live_abc.one-time-secret'));
  });

  it('revokes an active key after confirmation', async () => {
    vi.mocked(api.listApiKeys).mockResolvedValue({ data: { api_keys: [activeKey] } });
    vi.mocked(api.revokeApiKey).mockResolvedValue({
      data: { api_key: { ...activeKey, is_active: false, revoked_at: '2026-07-23T11:00:00' } },
    });

    render(<MemoryRouter><ApiKeyManagement /></MemoryRouter>);
    expect(await screen.findByText('生产服务')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '撤销' }));
    fireEvent.click(screen.getByRole('button', { name: '确认撤销' }));

    await waitFor(() => expect(api.revokeApiKey).toHaveBeenCalledWith('key-1'));
    expect(await screen.findByText('已撤销')).toBeInTheDocument();
  });
});
