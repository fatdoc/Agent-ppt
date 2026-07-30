import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  Bot,
  Boxes,
  Download,
  FileStack,
  Image,
  LayoutDashboard,
  ListTree,
  Palette,
  PenTool,
  Sparkles,
} from 'lucide-react';
import { DigitalEmployeeConsole } from './DigitalEmployeeConsole';

const navigation = [
  { to: '/workspace', label: 'PPT工作台', icon: LayoutDashboard },
  { to: '/generate', label: 'AI生成', icon: Sparkles },
  { to: '/outline', label: '大纲规划', icon: ListTree },
  { to: '/outline-templates', label: '大纲模板', icon: FileStack },
  { to: '/templates', label: '模板库', icon: Palette },
  { to: '/editor', label: '在线编辑', icon: PenTool },
  { to: '/assets', label: '素材中心', icon: Image },
  { to: '/exports', label: '导出中心', icon: Download },
];

export const PlatformShell = () => {
  const [consoleOpen, setConsoleOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#f5f8fd] text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="flex h-20 items-center gap-3 border-b border-slate-100 px-6">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-600 text-white">
            <Boxes size={22} />
          </span>
          <div>
            <p className="text-base font-extrabold tracking-tight">世职赛PPT平台</p>
            <p className="text-[11px] text-slate-500">职业教育竞赛智能交付</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'
                }`
              }
            >
              <Icon size={19} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-100 p-4">
          <button
            type="button"
            onClick={() => setConsoleOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-md"
          >
            <Bot size={18} /> 召唤数字员工
          </button>
        </div>
      </aside>

      <main className="min-h-screen pl-64">
        <Outlet />
      </main>

      <button
        type="button"
        aria-label="召唤数字员工"
        onClick={() => setConsoleOpen(true)}
        className="fixed bottom-6 right-6 z-30 grid h-14 w-14 place-items-center rounded-full bg-blue-600 text-white shadow-lg transition hover:-translate-y-1 hover:bg-blue-700"
      >
        <Bot size={24} />
      </button>
      <DigitalEmployeeConsole open={consoleOpen} onClose={() => setConsoleOpen(false)} />
    </div>
  );
};
