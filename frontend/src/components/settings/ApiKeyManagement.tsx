import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, Check, Clock3, Copy, KeyRound, Plus, ShieldCheck, Trash2, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import * as api from '@/api/endpoints';
import type { ApiKeyRecord } from '@/api/endpoints';
import { Button, useConfirm, useToast } from '@/components/shared';
import { useT } from '@/hooks/useT';

const apiKeyI18n = {
  zh: {
    apiKeys: {
      title: '开放 API 密钥',
      description: '用于服务端调用“已有大纲 → 逐页描述 → 图片”链路。密钥继承当前账号的模型配置和积分账户。',
      docs: '查看 API 文档',
      createTitle: '创建密钥',
      nameLabel: '密钥名称',
      namePlaceholder: '例如：测试环境、内部自动化',
      expiryLabel: '有效期',
      never: '永不过期',
      days: '{{days}} 天',
      create: '创建密钥',
      creating: '正在创建',
      oneTimeTitle: '请立即保存这个密钥',
      oneTimeDescription: '该密钥只显示这一次。关闭后无法再次查看，丢失后需重新创建。',
      copy: '复制',
      copied: '已复制',
      dismiss: '我已保存',
      listTitle: '现有密钥',
      empty: '暂无密钥。创建后即可在服务端开始调用。',
      loading: '正在加载密钥…',
      active: '可用',
      revoked: '已撤销',
      expired: '已过期',
      scope: '权限',
      createdAt: '创建于 {{date}}',
      expiresAt: '到期 {{date}}',
      noExpiry: '无到期日',
      lastUsed: '最后使用 {{date}}',
      neverUsed: '尚未使用',
      revoke: '撤销',
      revokeTitle: '撤销 API 密钥',
      revokeConfirm: '撤销后，使用密钥“{{name}}”的所有服务会立即认证失败。确定继续吗？',
      revokeAction: '确认撤销',
      cancel: '取消',
      createdMessage: '密钥已创建，请立即保存',
      revokedMessage: '密钥已撤销',
      loadFailed: '密钥加载失败',
      createFailed: '密钥创建失败',
      revokeFailed: '密钥撤销失败',
      copyFailed: '无法自动复制，请手动选中密钥',
      retry: '重试',
    },
  },
  en: {
    apiKeys: {
      title: 'Public API keys',
      description: 'Server-side credentials for the existing outline → slide descriptions → images workflow. Keys use this account\'s model configuration and credit balance.',
      docs: 'View API docs',
      createTitle: 'Create a key',
      nameLabel: 'Key name',
      namePlaceholder: 'For example: Staging or Internal automation',
      expiryLabel: 'Expiration',
      never: 'Never expires',
      days: '{{days}} days',
      create: 'Create key',
      creating: 'Creating',
      oneTimeTitle: 'Save this key now',
      oneTimeDescription: 'This key is shown only once. It cannot be viewed again after dismissal; create a replacement if it is lost.',
      copy: 'Copy',
      copied: 'Copied',
      dismiss: 'I have saved it',
      listTitle: 'Existing keys',
      empty: 'No API keys yet. Create one to start calling the workflow from your server.',
      loading: 'Loading API keys…',
      active: 'Active',
      revoked: 'Revoked',
      expired: 'Expired',
      scope: 'Scope',
      createdAt: 'Created {{date}}',
      expiresAt: 'Expires {{date}}',
      noExpiry: 'No expiration',
      lastUsed: 'Last used {{date}}',
      neverUsed: 'Never used',
      revoke: 'Revoke',
      revokeTitle: 'Revoke API key',
      revokeConfirm: 'All services using the key "{{name}}" will immediately fail authentication. Continue?',
      revokeAction: 'Revoke key',
      cancel: 'Cancel',
      createdMessage: 'API key created. Save it now',
      revokedMessage: 'API key revoked',
      loadFailed: 'Failed to load API keys',
      createFailed: 'Failed to create API key',
      revokeFailed: 'Failed to revoke API key',
      copyFailed: 'Could not copy automatically. Select and copy the key manually',
      retry: 'Retry',
    },
  },
};

const EXPIRY_OPTIONS = [0, 30, 90, 365];

const errorMessage = (error: unknown, fallback: string) => {
  const candidate = error as {
    response?: { data?: { error?: { message?: string } } };
    message?: string;
  };
  return candidate?.response?.data?.error?.message || candidate?.message || fallback;
};

export const ApiKeyManagement: React.FC = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const t = useT(apiKeyI18n);
  const { show, ToastContainer } = useToast();
  const { confirm, ConfirmDialog } = useConfirm();
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [name, setName] = useState('');
  const [expiryDays, setExpiryDays] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [createdSecret, setCreatedSecret] = useState<{ name: string; key: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const locale = i18n.language?.startsWith('zh') ? 'zh-CN' : 'en-US';

  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric' }),
    [locale]
  );

  const formatDate = (value?: string | null) => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
  };

  const loadKeys = async () => {
    setIsLoading(true);
    setLoadError('');
    try {
      const response = await api.listApiKeys();
      setKeys(response.data?.api_keys || []);
    } catch (error) {
      const message = errorMessage(error, t('apiKeys.loadFailed'));
      setLoadError(message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadKeys();
  }, []);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName || isCreating) return;

    setIsCreating(true);
    setCreatedSecret(null);
    setCopied(false);
    try {
      const response = await api.createApiKey(trimmedName, expiryDays || undefined);
      if (!response.data?.key || !response.data.api_key) {
        throw new Error(t('apiKeys.createFailed'));
      }
      setCreatedSecret({ name: response.data.api_key.name, key: response.data.key });
      setKeys((current) => [response.data!.api_key, ...current]);
      setName('');
      show({ message: t('apiKeys.createdMessage'), type: 'success' });
    } catch (error) {
      show({ message: errorMessage(error, t('apiKeys.createFailed')), type: 'error' });
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopy = async () => {
    if (!createdSecret) return;
    try {
      await navigator.clipboard.writeText(createdSecret.key);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      show({ message: t('apiKeys.copyFailed'), type: 'error' });
    }
  };

  const handleRevoke = (item: ApiKeyRecord) => {
    confirm(
      t('apiKeys.revokeConfirm', { name: item.name }),
      async () => {
        try {
          const response = await api.revokeApiKey(item.id);
          if (response.data?.api_key) {
            setKeys((current) => current.map((key) => key.id === item.id ? response.data!.api_key : key));
          } else {
            await loadKeys();
          }
          show({ message: t('apiKeys.revokedMessage'), type: 'success' });
        } catch (error) {
          show({ message: errorMessage(error, t('apiKeys.revokeFailed')), type: 'error' });
        }
      },
      {
        title: t('apiKeys.revokeTitle'),
        confirmText: t('apiKeys.revokeAction'),
        cancelText: t('apiKeys.cancel'),
        variant: 'danger',
      }
    );
  };

  const statusFor = (item: ApiKeyRecord) => {
    if (!item.is_active || item.revoked_at) return { label: t('apiKeys.revoked'), tone: 'text-red-600 dark:text-red-400', dot: 'bg-red-500' };
    if (item.expires_at && new Date(item.expires_at).getTime() <= Date.now()) {
      return { label: t('apiKeys.expired'), tone: 'text-amber-700 dark:text-amber-300', dot: 'bg-amber-500' };
    }
    return { label: t('apiKeys.active'), tone: 'text-emerald-700 dark:text-emerald-300', dot: 'bg-emerald-500' };
  };

  return (
    <section
      data-testid="api-key-management"
      className="overflow-hidden rounded-xl border border-emerald-200 bg-white shadow-sm dark:border-emerald-900/70 dark:bg-background-secondary"
    >
      <ToastContainer />
      {ConfirmDialog}

      <div className="flex flex-col gap-4 border-b border-gray-200 px-5 py-5 dark:border-border-primary md:flex-row md:items-start md:justify-between md:px-6">
        <div className="flex min-w-0 gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
            <KeyRound size={20} />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-foreground-primary">{t('apiKeys.title')}</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-gray-500 dark:text-foreground-tertiary">
              {t('apiKeys.description')}
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          icon={<BookOpen size={16} />}
          onClick={() => navigate('/developer/api-docs', { state: { from: '/settings' } })}
          className="shrink-0"
        >
          {t('apiKeys.docs')}
        </Button>
      </div>

      <div className="px-5 py-5 md:px-6">
        <form onSubmit={handleCreate} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_160px_auto] md:items-end">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700 dark:text-foreground-secondary">{t('apiKeys.nameLabel')}</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              autoComplete="off"
              placeholder={t('apiKeys.namePlaceholder')}
              className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-border-primary dark:bg-background-primary dark:text-foreground-primary"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700 dark:text-foreground-secondary">{t('apiKeys.expiryLabel')}</span>
            <select
              value={expiryDays}
              onChange={(event) => setExpiryDays(Number(event.target.value))}
              className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-border-primary dark:bg-background-primary dark:text-foreground-primary"
            >
              {EXPIRY_OPTIONS.map((days) => (
                <option key={days} value={days}>
                  {days === 0 ? t('apiKeys.never') : t('apiKeys.days', { days })}
                </option>
              ))}
            </select>
          </label>
          <Button
            type="submit"
            size="sm"
            icon={<Plus size={16} />}
            loading={isCreating}
            disabled={!name.trim()}
            className="h-10"
          >
            {isCreating ? t('apiKeys.creating') : t('apiKeys.create')}
          </Button>
        </form>

        {createdSecret && (
          <div className="mt-5 border-l-4 border-emerald-500 bg-emerald-50 px-4 py-4 dark:bg-emerald-950/30" role="status">
            <div className="flex items-start justify-between gap-4">
              <div className="flex gap-3">
                <ShieldCheck size={20} className="mt-0.5 shrink-0 text-emerald-700 dark:text-emerald-300" />
                <div>
                  <h3 className="text-sm font-semibold text-emerald-950 dark:text-emerald-100">{t('apiKeys.oneTimeTitle')}</h3>
                  <p className="mt-1 text-xs leading-5 text-emerald-800 dark:text-emerald-200">{t('apiKeys.oneTimeDescription')}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setCreatedSecret(null)}
                aria-label={t('apiKeys.dismiss')}
                className="shrink-0 text-emerald-800 transition hover:text-emerald-950 dark:text-emerald-300 dark:hover:text-emerald-100"
              >
                <X size={18} />
              </button>
            </div>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <code className="min-w-0 flex-1 overflow-x-auto rounded-md bg-gray-950 px-3 py-2.5 font-mono text-xs text-emerald-200 selection:bg-emerald-300 selection:text-gray-950">
                {createdSecret.key}
              </code>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={copied ? <Check size={16} /> : <Copy size={16} />}
                onClick={handleCopy}
              >
                {copied ? t('apiKeys.copied') : t('apiKeys.copy')}
              </Button>
            </div>
            <button
              type="button"
              onClick={() => setCreatedSecret(null)}
              className="mt-3 text-xs font-medium text-emerald-800 underline-offset-4 hover:underline dark:text-emerald-200"
            >
              {t('apiKeys.dismiss')}
            </button>
          </div>
        )}

        <div className="mt-6 border-t border-gray-200 pt-5 dark:border-border-primary">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-foreground-primary">{t('apiKeys.listTitle')}</h3>

          {isLoading ? (
            <p className="py-6 text-sm text-gray-500 dark:text-foreground-tertiary">{t('apiKeys.loading')}</p>
          ) : loadError ? (
            <div className="flex items-center justify-between gap-4 py-5 text-sm text-red-600 dark:text-red-400">
              <span>{loadError}</span>
              <Button type="button" variant="ghost" size="sm" onClick={() => void loadKeys()}>{t('apiKeys.retry')}</Button>
            </div>
          ) : keys.length === 0 ? (
            <p className="py-6 text-sm text-gray-500 dark:text-foreground-tertiary">{t('apiKeys.empty')}</p>
          ) : (
            <div className="mt-2 divide-y divide-gray-200 dark:divide-border-primary">
              {keys.map((item) => {
                const status = statusFor(item);
                const canRevoke = item.is_active && !item.revoked_at && (!item.expires_at || new Date(item.expires_at).getTime() > Date.now());
                return (
                  <div key={item.id} className="flex flex-col gap-3 py-4 first:pt-2 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-foreground-primary">{item.name}</span>
                        <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${status.tone}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
                          {status.label}
                        </span>
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600 dark:bg-background-hover dark:text-foreground-secondary">
                          {t('apiKeys.scope')}: {item.scopes.join(', ')}
                        </span>
                      </div>
                      <code className="mt-1.5 block truncate font-mono text-xs text-gray-600 dark:text-foreground-secondary">{item.prefix}…</code>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-foreground-tertiary">
                        <span>{t('apiKeys.createdAt', { date: formatDate(item.created_at) })}</span>
                        <span className="inline-flex items-center gap-1">
                          <Clock3 size={12} />
                          {item.expires_at ? t('apiKeys.expiresAt', { date: formatDate(item.expires_at) }) : t('apiKeys.noExpiry')}
                        </span>
                        <span>{item.last_used_at ? t('apiKeys.lastUsed', { date: formatDate(item.last_used_at) }) : t('apiKeys.neverUsed')}</span>
                      </div>
                    </div>
                    {canRevoke && (
                      <button
                        type="button"
                        onClick={() => handleRevoke(item)}
                        className="inline-flex shrink-0 items-center gap-1.5 self-start text-sm font-medium text-red-600 transition hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 md:self-auto"
                      >
                        <Trash2 size={15} />
                        {t('apiKeys.revoke')}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
