import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  FileStack,
  Layers3,
  PenTool,
  Sparkles,
  Trophy,
} from 'lucide-react';
import { listProjects } from '@/api/endpoints';
import {
  canStartCompetitionWorkflow,
  findBestOutlineTemplate,
  supportLevelLabel,
  SYSTEM_OUTLINE_TEMPLATES,
  usePlatform,
} from '@/platform';
import type { Project } from '@/types';

const workflow = ['选择赛事', '选择主题', '上传资料', '生成大纲', '编辑导出'];

export const Workbench = () => {
  const navigate = useNavigate();
  const {
    competition,
    competitions,
    projectContext,
    selectCompetition,
    updateProjectContext,
  } = usePlatform();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);

  useEffect(() => {
    listProjects(50, 0)
      .then((response) => setProjects(response.data?.projects ?? []))
      .finally(() => setLoadingProjects(false));
  }, []);

  const matchedTemplate = useMemo(
    () => findBestOutlineTemplate(SYSTEM_OUTLINE_TEMPLATES, {
      competitionId: competition.id,
      competitionTypeId: projectContext.competitionTypeId,
      trackId: projectContext.trackId,
      themeId: projectContext.themeId,
    }),
    [
      competition.id,
      projectContext.competitionTypeId,
      projectContext.themeId,
      projectContext.trackId,
    ],
  );

  const startEnabled = canStartCompetitionWorkflow(competition.id);
  const currentProject = projects.find((project) => project.project_id === projectContext.projectId);
  const currentStep = projectContext.projectId ? 3 : projectContext.themeId ? 2 : 1;

  return (
    <div className="mx-auto max-w-[1480px] px-8 py-7">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-600">PPT 工作台</p>
          <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-slate-950">
            从赛事规则到可编辑交付
          </h1>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700">
          <CheckCircle2 size={16} /> 项目上下文已保存
        </div>
      </header>

      <section className="mt-7 grid grid-cols-5 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        {workflow.map((label, index) => {
          const number = index + 1;
          const active = number <= currentStep;
          return (
            <div key={label} className="flex items-center">
              <span className={`grid h-8 w-8 place-items-center rounded-full text-sm font-bold ${
                active ? 'bg-blue-600 text-white' : 'border border-slate-300 text-slate-500'
              }`}>
                {number}
              </span>
              <span className={`ml-3 text-sm font-semibold ${active ? 'text-slate-900' : 'text-slate-400'}`}>
                {label}
              </span>
              {index < workflow.length - 1 && <span className="mx-4 h-px flex-1 bg-slate-200" />}
            </div>
          );
        })}
      </section>

      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <span className="h-5 w-1 rounded-full bg-blue-600" />
          <h2 className="font-bold text-slate-950">赛事与主题配置</h2>
          <span className={`ml-auto rounded-full px-3 py-1 text-xs font-semibold ${
            competition.supportLevel === 'FULL'
              ? 'bg-emerald-50 text-emerald-700'
              : competition.supportLevel === 'GENERIC'
                ? 'bg-blue-50 text-blue-700'
                : 'bg-amber-50 text-amber-700'
          }`}>
            {supportLevelLabel[competition.supportLevel]}
          </span>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr_1fr_1.6fr]">
          <label className="block text-xs font-semibold text-slate-500">
            赛事名称
            <select
              value={competition.id}
              onChange={(event) => selectCompetition(event.target.value)}
              className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-900 outline-none focus:border-blue-500"
            >
              {competitions.filter((item) => item.enabled).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {supportLevelLabel[item.supportLevel]}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-semibold text-slate-500">
            比赛类型
            <select
              value={projectContext.competitionTypeId ?? ''}
              disabled={!competition.competitionTypes.length}
              onChange={(event) => updateProjectContext({ competitionTypeId: event.target.value })}
              className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold outline-none disabled:bg-slate-50 disabled:text-slate-400"
            >
              {competition.competitionTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="block text-xs font-semibold text-slate-500">
            赛道类别
            <select
              value={projectContext.trackId ?? ''}
              disabled={!competition.tracks.length}
              onChange={(event) => updateProjectContext({ trackId: event.target.value })}
              className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold outline-none disabled:bg-slate-50 disabled:text-slate-400"
            >
              {competition.tracks.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="block text-xs font-semibold text-slate-500">
            大赛主题
            <select
              value={projectContext.themeId ?? ''}
              disabled={!competition.themes.length}
              onChange={(event) => updateProjectContext({ themeId: event.target.value })}
              className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold outline-none disabled:bg-slate-50 disabled:text-slate-400"
            >
              {competition.themes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
        </div>

        {competition.supportLevel !== 'FULL' && (
          <p className={`mt-4 rounded-xl px-4 py-3 text-sm ${
            competition.supportLevel === 'COMING_SOON'
              ? 'bg-amber-50 text-amber-800'
              : 'bg-blue-50 text-blue-800'
          }`}>
            {competition.unsupportedMessage}
          </p>
        )}
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.08fr_.92fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">当前项目</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">
                {currentProject?.project_title || projectContext.projectName || '关联已有项目'}
              </h2>
            </div>
            <Trophy className="text-blue-600" size={28} />
          </div>

          <label className="mt-5 block text-xs font-semibold text-slate-500">
            项目
            <select
              value={projectContext.projectId ?? ''}
              disabled={loadingProjects}
              onChange={(event) => {
                const project = projects.find((item) => item.project_id === event.target.value);
                updateProjectContext({
                  projectId: event.target.value || undefined,
                  projectName: project?.project_title || project?.idea_prompt || '',
                });
              }}
              className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-500"
            >
              <option value="">{loadingProjects ? '正在读取真实项目…' : '请选择已有项目'}</option>
              {projects.map((project) => (
                <option key={project.project_id} value={project.project_id}>
                  {project.project_title || project.idea_prompt || project.project_id}
                </option>
              ))}
            </select>
          </label>

          <div className="mt-5 grid grid-cols-3 divide-x divide-slate-100 border-y border-slate-100 py-4">
            <div className="px-3 first:pl-0">
              <p className="text-xs text-slate-500">目标页数</p>
              <p className="mt-1 text-2xl font-bold text-blue-600">{projectContext.targetPageCount}<span className="ml-1 text-sm">页</span></p>
            </div>
            <div className="px-3">
              <p className="text-xs text-slate-500">大纲模板</p>
              <p className="mt-1 truncate text-sm font-semibold text-slate-900">{matchedTemplate?.name ?? '暂无匹配'}</p>
            </div>
            <div className="px-3">
              <p className="text-xs text-slate-500">视觉风格</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{projectContext.style}</p>
            </div>
          </div>

          <button
            type="button"
            disabled={!startEnabled}
            onClick={() => navigate('/generate')}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <Sparkles size={18} /> {projectContext.projectId ? '继续生成与完善' : '开始创建 PPT'}
          </button>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <Layers3 size={20} className="text-blue-600" />
            <h2 className="font-bold text-slate-950">当前支持能力</h2>
          </div>
          <div className="mt-4 divide-y divide-slate-100">
            {(competition.supportLevel === 'FULL'
              ? ['专属大纲与 39 页页面计划', '五项评分维度贯穿生成与检查', '专属逐页讲解稿角色与交接逻辑', '赛事/赛道/主题相关素材提示']
              : ['通用 PPT 生成与编辑', '通用视觉模板', 'AI 生图、抠图与图片处理', '可编辑 PPT 与 PDF 导出']
            ).map((capability) => (
              <div key={capability} className="flex items-center gap-3 py-3 text-sm text-slate-700">
                <CheckCircle2 size={17} className="text-emerald-600" />
                {capability}
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-slate-950">快捷操作</h2>
          <span className="text-xs text-slate-500">所有操作进入真实业务页面</span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {[
            { label: '选择大纲模板', description: matchedTemplate?.name ?? '平台通用模板', to: '/outline-templates', icon: FileStack },
            { label: '规划项目大纲', description: '章节、页数与评分映射', to: '/outline', icon: Layers3 },
            { label: '进入在线编辑', description: '页面、图片与讲解稿', to: '/editor', icon: PenTool },
            { label: '准备交付文件', description: '预检并导出参赛版', to: '/exports', icon: ArrowRight },
          ].map(({ label, description, to, icon: Icon }) => (
            <button
              type="button"
              key={to}
              onClick={() => navigate(to)}
              className="group flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-4 text-left transition hover:border-blue-300 hover:bg-blue-50/40"
            >
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600">
                <Icon size={19} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-slate-900">{label}</span>
                <span className="mt-0.5 block truncate text-xs text-slate-500">{description}</span>
              </span>
              <ChevronRight size={17} className="text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-blue-600" />
            </button>
          ))}
        </div>
      </section>
    </div>
  );
};
