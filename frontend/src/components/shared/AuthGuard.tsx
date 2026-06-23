import { useEffect, useState, type ReactNode } from 'react';
import { ChevronDown, LogOut, Settings as SettingsIcon, User } from 'lucide-react';
import { getAuthConfig, getCurrentUser, getSettings, login, logout, register, type AuthUser } from '@/api/endpoints';
import { setAuthToken } from '@/api/client';
import { useProjectStore } from '@/store/useProjectStore';
import type { Settings } from '@/types';
import { Button } from './Button';
import { Input } from './Input';

type Mode = 'login' | 'register';
type Status = 'loading' | 'pass' | 'prompt' | 'connectError';

export function AuthGuard({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('loading');
  const [mode, setMode] = useState<Mode>('login');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [identifier, setIdentifier] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const setCurrentProject = useProjectStore((state) => state.setCurrentProject);

  const loadAuth = async () => {
    setStatus('loading');
    try {
      const config = await getAuthConfig();
      if (!config.data?.enabled) {
        setStatus('pass');
        return;
      }
      const me = await getCurrentUser();
      if (!me.data?.user) throw new Error('Missing user');
      setUser(me.data.user);
      setStatus('pass');
    } catch {
      setUser(null);
      setStatus('prompt');
    }
  };

  useEffect(() => {
    loadAuth();
  }, []);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const response = mode === 'login'
        ? await login(identifier.trim(), password)
        : await register(username.trim(), password, email.trim() || undefined);
      if (!response.data?.token || !response.data.user) throw new Error('Missing auth token');
      setAuthToken(response.data.token);
      setUser(response.data.user);
      setCurrentProject(null);
      localStorage.removeItem('currentProjectId');
      sessionStorage.removeItem('banana-settings');
      setStatus('pass');
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || '登录失败，请检查账号信息');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Local token removal is enough for this client.
    }
    setAuthToken('');
    setCurrentProject(null);
    localStorage.removeItem('currentProjectId');
    sessionStorage.removeItem('banana-settings');
    setUser(null);
    setStatus('prompt');
  };

  const loadSettingsSummary = async () => {
    if (settings || settingsLoading) return;
    setSettingsLoading(true);
    try {
      const response = await getSettings();
      setSettings(response.data || null);
    } catch {
      setSettings(null);
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleToggleMenu = () => {
    const nextOpen = !menuOpen;
    setMenuOpen(nextOpen);
    if (nextOpen) {
      loadSettingsSummary();
    }
  };

  if (status === 'loading') return null;

  if (status === 'pass') {
    return (
      <>
        {children}
        {user && (
          <div className="fixed right-4 top-4 z-[100]">
            <button
              type="button"
              onClick={handleToggleMenu}
              className="flex h-10 items-center gap-2 rounded-full border border-[#121212]/10 bg-white/95 px-3 text-sm font-semibold text-[#121212] shadow-lg backdrop-blur transition hover:bg-white dark:border-white/10 dark:bg-background-secondary/95 dark:text-foreground-primary"
            >
              <User className="h-4 w-4" />
              <span className="max-w-32 truncate">{user.username}</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
            </button>

            {menuOpen && (
              <div className="mt-2 w-80 rounded-xl border border-[#121212]/10 bg-white p-4 text-sm shadow-2xl dark:border-white/10 dark:bg-background-secondary">
                <div className="mb-3 flex items-center justify-between gap-3 border-b border-[#121212]/10 pb-3 dark:border-white/10">
                  <div className="min-w-0">
                    <p className="truncate font-bold text-gray-900 dark:text-foreground-primary">{user.username}</p>
                    {user.email && (
                      <p className="truncate text-xs text-gray-500 dark:text-foreground-tertiary">{user.email}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => { window.location.href = '/settings'; }}
                    className="inline-flex h-8 items-center gap-1 rounded-full px-2 font-semibold text-gray-700 hover:bg-gray-100 dark:text-foreground-secondary dark:hover:bg-white/10"
                  >
                    <SettingsIcon className="h-4 w-4" />
                    设置
                  </button>
                </div>

                <div className="space-y-2">
                  <ConfigRow label="Provider" value={settings?.ai_provider_format || (settingsLoading ? '加载中...' : '-')} />
                  <ConfigRow label="文本模型" value={settings?.text_model || '-'} />
                  <ConfigRow label="图片模型" value={settings?.image_model || '-'} />
                  <ConfigRow label="识图模型" value={settings?.image_caption_model || '-'} />
                  <ConfigRow label="输出语言" value={settings?.output_language || '-'} />
                  <ConfigRow label="全局 Key" value={settings ? (settings.api_key_length > 0 ? '已配置' : '未配置') : '-'} />
                  <ConfigRow label="文本 Key" value={settings ? (settings.text_api_key_length > 0 ? '已配置' : '未配置') : '-'} />
                  <ConfigRow label="图片 Key" value={settings ? (settings.image_api_key_length > 0 ? '已配置' : '未配置') : '-'} />
                </div>

                <button
                  type="button"
                  onClick={handleLogout}
                  className="mt-4 flex h-9 w-full items-center justify-center gap-2 rounded-full border border-red-200 font-semibold text-red-600 hover:bg-red-50 dark:border-red-500/30 dark:text-red-300 dark:hover:bg-red-500/10"
                >
                  <LogOut className="h-4 w-4" />
                  退出登录
                </button>
              </div>
            )}
          </div>
        )}
      </>
    );
  }

  if (status === 'connectError') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-primary px-4">
        <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 text-center shadow-lg dark:border-border-primary dark:bg-background-secondary">
          <p className="mb-4 text-gray-600 dark:text-foreground-secondary">无法连接到后端服务</p>
          <Button className="w-full" onClick={loadAuth}>重试</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background-primary px-4">
      <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 shadow-lg dark:border-border-primary dark:bg-background-secondary">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-foreground-primary">
            {mode === 'login' ? '登录 Banana Slides' : '创建账号'}
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-foreground-tertiary">
            作品、API Key、模板和素材会保存在当前账号下
          </p>
        </div>

        <form onSubmit={(event) => { event.preventDefault(); handleSubmit(); }} className="space-y-4">
          {mode === 'login' ? (
            <Input
              label="用户名或邮箱"
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              autoFocus
            />
          ) : (
            <>
              <Input
                label="用户名"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoFocus
              />
              <Input
                label="邮箱（选填）"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </>
          )}
          <Input
            label="密码"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={error}
          />
          <Button type="submit" className="w-full" loading={submitting}>
            {mode === 'login' ? '登录' : '注册并登录'}
          </Button>
        </form>

        <button
          type="button"
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
          className="mt-4 w-full text-sm font-semibold text-gray-700 hover:text-gray-950 dark:text-foreground-secondary dark:hover:text-foreground-primary"
        >
          {mode === 'login' ? '没有账号？创建一个' : '已有账号？去登录'}
        </button>
      </div>
    </div>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="shrink-0 text-gray-500 dark:text-foreground-tertiary">{label}</span>
      <span className="min-w-0 truncate font-semibold text-gray-900 dark:text-foreground-primary">{value}</span>
    </div>
  );
}
