import { useEffect, useState, type ReactNode } from 'react';
import {
  Building2,
  ChevronDown,
  Eye,
  EyeOff,
  Home as HomeIcon,
  Lock,
  LogOut,
  Phone,
  Settings as SettingsIcon,
  User,
} from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { getAuthConfig, getCurrentUser, getSettings, login, logout, register, type AuthUser } from '@/api/endpoints';
import { useProjectStore } from '@/store/useProjectStore';
import type { Settings } from '@/types';
import { Button } from './Button';

type Mode = 'login' | 'register';
type Status = 'loading' | 'pass' | 'prompt' | 'connectError';
type AuthMethod = 'account' | 'code';

export function AuthGuard({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [status, setStatus] = useState<Status>('loading');
  const [mode, setMode] = useState<Mode>('login');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [identifier, setIdentifier] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMethod, setAuthMethod] = useState<AuthMethod>('account');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const setCurrentProject = useProjectStore((state) => state.setCurrentProject);
  const isPublicRoute = location.pathname === '/' || location.pathname === '/landing';
  const shouldShowUserMenu = location.pathname === '/' || location.pathname === '/app';

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
    if (mode === 'login' && authMethod === 'code') {
      setError('验证码登录暂未接入，请使用账号登录');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const response = mode === 'login'
        ? await login(identifier.trim(), password)
        : await register(username.trim(), password, email.trim() || undefined);
      if (!response.data?.user) throw new Error('Missing authenticated user');
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
      // The UI still clears local state if the backend is temporarily unavailable.
    }
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

  if (status === 'prompt' && isPublicRoute) {
    return <>{children}</>;
  }

  if (status === 'pass') {
    return (
      <>
        {children}
        {user && shouldShowUserMenu && (
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
    <div className="flex min-h-screen w-full flex-col bg-gradient-to-br from-[#e8f8ee] via-[#f2faf2] to-[#d4f0e0] text-[#121212]">
      <header className="flex w-full shrink-0 items-center justify-between px-5 py-4 md:px-8">
        <button
          type="button"
          onClick={() => { window.location.href = '/'; }}
          className="flex items-center gap-2 text-left"
          aria-label="返回首页"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#4ade80] text-sm font-black text-white">
            兰
          </span>
          <span className="text-base font-bold tracking-normal text-[#16a34a]">兰台</span>
          <span className="mx-0.5 text-gray-400">·</span>
          <span className="text-sm font-semibold text-gray-600">PPT Agent</span>
        </button>
        <button
          type="button"
          onClick={() => { window.location.href = '/'; }}
          className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-semibold text-gray-500 transition-colors hover:bg-white/50 hover:text-[#16a34a]"
        >
          <HomeIcon className="h-4 w-4" />
          返回首页
        </button>
      </header>

      <main className="flex flex-1 items-center justify-center p-4 md:p-6 lg:p-8">
        <div className="w-full max-w-[1080px] overflow-hidden rounded-2xl bg-white shadow-xl md:rounded-[2rem]">
          <div className="grid min-h-[680px] gap-0 lg:grid-cols-2">
            <section className="flex flex-col items-center justify-center bg-white p-8 lg:p-12">
              <div className="w-full max-w-[380px] space-y-6">
                <div className="space-y-1 text-center">
                  <h1 className="text-2xl font-bold text-gray-900">
                    {mode === 'login' ? '欢迎登录' : '创建账号'}
                  </h1>
                  <p className="text-sm leading-6 text-gray-400">
                    {mode === 'login'
                      ? '登录兰台 PPT Agent，开启智能化 PPT 交付体验'
                      : '创建账号后，作品、模板和 Harness 交付记录会保存在当前账号下'}
                  </p>
                </div>

                {mode === 'login' && (
                  <div className="flex border-b border-gray-200">
                    {([
                      ['account', '账号登录'],
                      ['code', '验证码登录'],
                    ] as const).map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => { setAuthMethod(value); setError(''); }}
                        className={`relative flex-1 pb-2.5 text-sm font-semibold transition-colors ${
                          authMethod === value ? 'text-[#16a34a]' : 'text-gray-400 hover:text-gray-600'
                        }`}
                      >
                        {label}
                        {authMethod === value && (
                          <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-[#4ade80]" />
                        )}
                      </button>
                    ))}
                  </div>
                )}

                <form onSubmit={(event) => { event.preventDefault(); handleSubmit(); }} className="space-y-4">
                  {mode === 'register' ? (
                    <>
                      <AuthInput
                        icon={<User className="h-4 w-4" />}
                        placeholder="用户名"
                        value={username}
                        onChange={(event) => setUsername(event.target.value)}
                        autoFocus
                      />
                      <AuthInput
                        icon={<Phone className="h-4 w-4" />}
                        placeholder="邮箱（选填）"
                        type="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                      />
                    </>
                  ) : authMethod === 'account' ? (
                    <AuthInput
                      icon={<User className="h-4 w-4" />}
                      placeholder="请输入账号"
                      value={identifier}
                      onChange={(event) => setIdentifier(event.target.value)}
                      autoFocus
                    />
                  ) : (
                    <>
                      <AuthInput
                        icon={<User className="h-4 w-4" />}
                        placeholder="请输入手机号"
                        type="tel"
                        value={phone}
                        onChange={(event) => setPhone(event.target.value)}
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <AuthInput
                          className="min-w-0 flex-1"
                          inputClassName="pl-4"
                          placeholder="请输入验证码"
                          value={code}
                          onChange={(event) => setCode(event.target.value)}
                        />
                        <button
                          type="button"
                          onClick={() => setError('验证码登录暂未接入，请使用账号登录')}
                          className="h-12 whitespace-nowrap rounded-xl border border-[#4ade80] px-4 text-sm font-semibold text-[#16a34a] transition-colors hover:bg-[#f0fdf4]"
                        >
                          获取验证码
                        </button>
                      </div>
                    </>
                  )}

                  {(mode === 'register' || authMethod === 'account') && (
                    <AuthInput
                      icon={<Lock className="h-4 w-4" />}
                      placeholder="请输入密码"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      rightButton={(
                        <button
                          type="button"
                          onClick={() => setShowPassword((visible) => !visible)}
                          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
                          aria-label={showPassword ? '隐藏密码' : '显示密码'}
                        >
                          {showPassword ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        </button>
                      )}
                    />
                  )}

                  {mode === 'login' && authMethod === 'account' && (
                    <div className="flex items-center justify-between">
                      <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-500">
                        <input
                          type="checkbox"
                          checked={rememberMe}
                          onChange={(event) => setRememberMe(event.target.checked)}
                          className="h-4 w-4 rounded border-gray-300 accent-[#4ade80]"
                        />
                        记住我
                      </label>
                      <button
                        type="button"
                        onClick={() => setError('请联系管理员重置密码')}
                        className="text-sm font-medium text-[#16a34a] transition-colors hover:text-[#4ade80]"
                      >
                        忘记密码?
                      </button>
                    </div>
                  )}

                  {error && (
                    <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                      {error}
                    </p>
                  )}

                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex h-12 w-full items-center justify-center rounded-xl bg-[#4ade80] text-base font-bold text-white shadow-sm shadow-green-200 transition-colors hover:bg-[#22c55e] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting ? '处理中...' : mode === 'login' ? '登录' : '注册并登录'}
                  </button>
                </form>

                <p className="text-center text-sm text-gray-400">
                  {mode === 'login' ? '还没有账号?' : '已有账号?'}{' '}
                  <button
                    type="button"
                    onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); setAuthMethod('account'); }}
                    className="font-semibold text-[#16a34a] transition-colors hover:text-[#4ade80]"
                  >
                    {mode === 'login' ? '注册账号' : '去登录'}
                  </button>
                </p>

                <button
                  type="button"
                  onClick={() => setError('企业 SSO 暂未接入，请使用账号登录')}
                  className="flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white text-sm font-semibold text-gray-600 transition-colors hover:border-[#4ade80] hover:text-[#16a34a]"
                >
                  <Building2 className="h-4 w-4" />
                  企业登录 / SSO
                </button>

                <p className="text-center text-xs leading-relaxed text-gray-400">
                  登录即代表您同意
                  <button type="button" className="mx-1 text-[#16a34a] hover:underline">《用户协议》</button>
                  与
                  <button type="button" className="mx-1 text-[#16a34a] hover:underline">《隐私政策》</button>
                </p>
              </div>
            </section>

            <section className="relative m-0 min-h-[320px] overflow-hidden lg:m-3 lg:min-h-0 lg:rounded-[1.5rem]">
              <img
                src="/images/login-harness-panel.png"
                alt="Harness工程 AI驱动一键生成专业PPT"
                className="absolute inset-0 h-full w-full object-cover object-center"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent" />
              <div className="absolute bottom-6 left-6 right-6">
                <h2 className="text-2xl font-bold leading-tight text-white drop-shadow-lg">
                  Harness工程
                </h2>
                <p className="text-xl font-bold leading-tight text-[#4ade80] drop-shadow-lg">
                  一键生成专业 PPT
                </p>
                <p className="mt-2 text-sm leading-relaxed text-white/80 drop-shadow">
                  AI 驱动 · 智能理解 · 高效输出 · 专业呈现
                </p>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}

function AuthInput({
  icon,
  rightButton,
  className,
  inputClassName,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  icon?: React.ReactNode;
  rightButton?: React.ReactNode;
  inputClassName?: string;
}) {
  return (
    <label className={`relative block ${className || ''}`}>
      {icon && (
        <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
          {icon}
        </span>
      )}
      <input
        className={`h-12 w-full rounded-xl border border-[#d1fae5] bg-[#f4faf4] px-4 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-[#4ade80] focus:ring-2 focus:ring-[#4ade80]/20 ${icon ? 'pl-10' : ''} ${rightButton ? 'pr-10' : ''} ${inputClassName || ''}`}
        {...props}
      />
      {rightButton}
    </label>
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
