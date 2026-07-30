import { useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Archive,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  FilePlus2,
  FileUp,
  History,
  Plus,
  Save,
  Search,
  Trash2,
} from 'lucide-react';
import {
  enabledCompetitions,
  getCompetitionConfig,
  supportLevelLabel,
  useOutlineTemplateRepository,
  usePlatform,
  type OutlineTemplate,
  type OutlineTemplateScope,
  type OutlineTemplateSection,
  type OutlineTemplateStatus,
} from '@/platform';

const blankTemplate = (competitionId: string): OutlineTemplate => {
  const now = new Date().toISOString();
  return {
    id: `outline-${Date.now()}`,
    name: '未命名大纲模板',
    description: '',
    competitionId,
    supportScope: 'PRIVATE',
    status: 'DRAFT',
    version: 1,
    targetPageCount: 1,
    styleTags: [],
    sections: [{
      id: `section-${Date.now()}`,
      title: '新章节',
      recommendedPageCount: 1,
      purpose: '',
    }],
    versions: [],
    createdBy: 'CURRENT_USER',
    createdAt: now,
    updatedAt: now,
  };
};

const downloadJson = (template: OutlineTemplate) => {
  const blob = new Blob([JSON.stringify(template, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${template.name}.outline-template.json`;
  anchor.click();
  URL.revokeObjectURL(url);
};

export const OutlineTemplateCenter = () => {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const {
    templates,
    createTemplate,
    updateTemplate,
    duplicateTemplate,
    deleteTemplate,
    importTemplates,
  } = useOutlineTemplateRepository();
  const { competition, projectContext, updateProjectContext } = usePlatform();
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<'ALL' | OutlineTemplateScope>('ALL');
  const [status, setStatus] = useState<'ALL' | OutlineTemplateStatus>('ALL');
  const [selectedId, setSelectedId] = useState(templates[0]?.id ?? '');
  const [draft, setDraft] = useState<OutlineTemplate | null>(templates[0] ?? null);
  const [versionOpen, setVersionOpen] = useState(false);

  const filtered = useMemo(
    () => templates.filter((template) => {
      const matchesQuery = !query || `${template.name} ${template.description ?? ''} ${(template.styleTags ?? []).join(' ')}`
        .toLowerCase()
        .includes(query.toLowerCase());
      return matchesQuery
        && (scope === 'ALL' || template.supportScope === scope)
        && (status === 'ALL' || template.status === status);
    }),
    [query, scope, status, templates],
  );

  const selected = templates.find((item) => item.id === selectedId);
  const systemOwned = selected?.createdBy === 'SYSTEM';

  const select = (template: OutlineTemplate) => {
    setSelectedId(template.id);
    setDraft(structuredClone(template));
    setVersionOpen(false);
  };

  const create = async () => {
    const next = blankTemplate(competition.id);
    select(await createTemplate(next));
  };

  const save = async () => {
    if (!draft || systemOwned) return;
    select(await updateTemplate(draft));
  };

  const updateSection = (index: number, patch: Partial<OutlineTemplateSection>) => {
    if (!draft) return;
    setDraft({
      ...draft,
      sections: draft.sections.map((section, currentIndex) =>
        currentIndex === index ? { ...section, ...patch } : section),
    });
  };

  const addSection = () => {
    if (!draft) return;
    setDraft({
      ...draft,
      sections: [
        ...draft.sections,
        {
          id: `section-${Date.now()}`,
          title: '新章节',
          recommendedPageCount: 1,
          purpose: '',
        },
      ],
    });
  };

  const importFile = async (file?: File) => {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const incoming = Array.isArray(parsed) ? parsed : [parsed];
      const imported = await importTemplates(incoming);
      if (imported[0]) select(imported[0]);
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const applyTemplate = () => {
    if (!selected) return;
    updateProjectContext({
      outlineTemplateId: selected.id,
      targetPageCount: selected.targetPageCount ?? projectContext.targetPageCount,
    });
    navigate('/outline');
  };

  return (
    <div className="mx-auto max-w-[1520px] px-8 py-7">
      <header className="flex items-end justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-600">业务模板资产</p>
          <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-slate-950">大纲模板中心</h1>
          <p className="mt-2 text-sm text-slate-500">创建、版本化并复用赛事大纲；视觉模板在“模板库”中独立管理。</p>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(event) => importFile(event.target.files?.[0])}
          />
          <button type="button" onClick={() => fileRef.current?.click()} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:border-blue-300">
            <FileUp size={17} /> 导入
          </button>
          <button type="button" onClick={create} className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">
            <FilePlus2 size={17} /> 新建模板
          </button>
        </div>
      </header>

      <section className="mt-6 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <label className="relative min-w-0 flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索模板名称、说明或标签" className="h-11 w-full rounded-xl border border-slate-200 pl-10 pr-3 text-sm outline-none focus:border-blue-500" />
        </label>
        <select value={scope} onChange={(event) => setScope(event.target.value as typeof scope)} className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium">
          <option value="ALL">全部权限</option>
          <option value="SYSTEM">系统模板</option>
          <option value="TEAM">团队模板</option>
          <option value="PRIVATE">我的模板</option>
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value as typeof status)} className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium">
          <option value="ALL">全部状态</option>
          <option value="DRAFT">草稿</option>
          <option value="PUBLISHED">已发布</option>
          <option value="ARCHIVED">已归档</option>
        </select>
      </section>

      <div className="mt-5 grid min-h-[680px] grid-cols-[390px_1fr] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <aside className="overflow-y-auto border-r border-slate-200 bg-slate-50/60 p-3">
          <p className="px-2 py-2 text-xs font-semibold text-slate-500">{filtered.length} 个模板</p>
          {filtered.map((template) => {
            const templateCompetition = template.competitionId
              ? getCompetitionConfig(template.competitionId)
              : null;
            return (
              <button
                type="button"
                key={template.id}
                onClick={() => select(template)}
                className={`mb-2 w-full rounded-xl border p-4 text-left transition ${
                  selectedId === template.id
                    ? 'border-blue-300 bg-white shadow-sm'
                    : 'border-transparent hover:border-slate-200 hover:bg-white'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate text-sm font-bold text-slate-900">{template.name}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    template.status === 'PUBLISHED' ? 'bg-emerald-50 text-emerald-700' : template.status === 'ARCHIVED' ? 'bg-slate-200 text-slate-600' : 'bg-amber-50 text-amber-700'
                  }`}>
                    {template.status === 'PUBLISHED' ? '已发布' : template.status === 'ARCHIVED' ? '已归档' : '草稿'}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{template.description || '暂无说明'}</p>
                <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                  <span>{templateCompetition?.shortName ?? '平台通用'} · {template.targetPageCount ?? '自适应'} 页</span>
                  <span>v{template.version}</span>
                </div>
              </button>
            );
          })}
        </aside>

        {draft ? (
          <section className="overflow-y-auto p-7">
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0 flex-1">
                <input
                  value={draft.name}
                  readOnly={systemOwned}
                  onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                  className="w-full border-0 bg-transparent p-0 text-2xl font-bold text-slate-950 outline-none read-only:cursor-default"
                />
                <textarea
                  value={draft.description ?? ''}
                  readOnly={systemOwned}
                  onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                  className="mt-2 min-h-12 w-full resize-none border-0 bg-transparent p-0 text-sm leading-6 text-slate-500 outline-none"
                />
              </div>
              <div className="flex shrink-0 gap-2">
                <button type="button" onClick={() => downloadJson(selected ?? draft)} title="导出模板" className="rounded-xl border border-slate-200 p-2.5 text-slate-600 hover:border-blue-300 hover:text-blue-600"><Download size={18} /></button>
                <button type="button" onClick={async () => select(await duplicateTemplate(selected ?? draft))} title="复制模板" className="rounded-xl border border-slate-200 p-2.5 text-slate-600 hover:border-blue-300 hover:text-blue-600"><Copy size={18} /></button>
                {!systemOwned && (
                  <>
                    <button type="button" onClick={() => setDraft({ ...draft, status: 'ARCHIVED' })} title="归档模板" className="rounded-xl border border-slate-200 p-2.5 text-slate-600 hover:border-amber-300 hover:text-amber-600"><Archive size={18} /></button>
                    <button type="button" onClick={async () => { await deleteTemplate(draft.id); setDraft(null); }} title="删除模板" className="rounded-xl border border-slate-200 p-2.5 text-slate-600 hover:border-rose-300 hover:text-rose-600"><Trash2 size={18} /></button>
                  </>
                )}
              </div>
            </div>

            <div className="mt-6 grid grid-cols-4 gap-3 border-y border-slate-100 py-5">
              <label className="text-xs font-semibold text-slate-500">
                适用赛事
                <select
                  value={draft.competitionId ?? ''}
                  disabled={systemOwned}
                  onChange={(event) => setDraft({ ...draft, competitionId: event.target.value || undefined })}
                  className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-800 disabled:bg-slate-50"
                >
                  <option value="">平台通用</option>
                  {enabledCompetitions().map((item) => <option key={item.id} value={item.id}>{item.shortName} · {supportLevelLabel[item.supportLevel]}</option>)}
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-500">
                权限
                <select value={draft.supportScope} disabled={systemOwned} onChange={(event) => setDraft({ ...draft, supportScope: event.target.value as OutlineTemplateScope })} className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm disabled:bg-slate-50">
                  <option value="SYSTEM">系统模板</option>
                  <option value="TEAM">团队模板</option>
                  <option value="PRIVATE">我的模板</option>
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-500">
                状态
                <select value={draft.status} disabled={systemOwned} onChange={(event) => setDraft({ ...draft, status: event.target.value as OutlineTemplateStatus })} className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm disabled:bg-slate-50">
                  <option value="DRAFT">草稿</option>
                  <option value="PUBLISHED">已发布</option>
                  <option value="ARCHIVED">已归档</option>
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-500">
                目标页数
                <input type="number" min={1} max={100} readOnly={systemOwned} value={draft.targetPageCount ?? 1} onChange={(event) => setDraft({ ...draft, targetPageCount: Number(event.target.value) })} className="mt-2 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm read-only:bg-slate-50" />
              </label>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <h3 className="font-bold text-slate-950">章节结构</h3>
              {!systemOwned && <button type="button" onClick={addSection} className="flex items-center gap-1 text-sm font-semibold text-blue-600"><Plus size={16} /> 添加章节</button>}
            </div>
            <div className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200">
              {draft.sections.map((section, index) => (
                <div key={section.id} className="p-4">
                  <div className="flex items-center gap-3">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-blue-600 text-xs font-bold text-white">{index + 1}</span>
                    <input value={section.title} readOnly={systemOwned} onChange={(event) => updateSection(index, { title: event.target.value })} className="min-w-0 flex-1 bg-transparent text-sm font-bold outline-none" />
                    <label className="flex items-center gap-2 text-xs text-slate-500">
                      页数
                      <input type="number" min={1} readOnly={systemOwned} value={section.recommendedPageCount} onChange={(event) => updateSection(index, { recommendedPageCount: Number(event.target.value) })} className="h-8 w-16 rounded-lg border border-slate-200 px-2 text-center text-sm" />
                    </label>
                    <ChevronRight size={16} className="text-slate-300" />
                  </div>
                  <input value={section.purpose ?? ''} readOnly={systemOwned} onChange={(event) => updateSection(index, { purpose: event.target.value })} placeholder="本章节的页面目的" className="mt-2 w-full bg-transparent pl-10 text-xs text-slate-500 outline-none" />
                  {section.children?.length ? (
                    <p className="mt-2 pl-10 text-xs text-blue-600">{section.children.length} 个已规划页面 · 含逐页目的、评分点和讲解角色</p>
                  ) : null}
                </div>
              ))}
            </div>

            <button type="button" onClick={() => setVersionOpen((open) => !open)} className="mt-5 flex w-full items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-left text-sm font-semibold text-slate-800">
              <span className="flex items-center gap-2"><History size={17} className="text-blue-600" /> 版本管理 · 当前 v{draft.version}</span>
              <ChevronDown size={17} className={`transition ${versionOpen ? 'rotate-180' : ''}`} />
            </button>
            {versionOpen && (
              <div className="mt-2 rounded-xl bg-slate-50 px-4 py-2">
                {(draft.versions ?? []).length === 0 ? (
                  <p className="py-3 text-xs text-slate-500">当前为首个版本。每次保存编辑都会保留上一版本快照。</p>
                ) : (
                  [...(draft.versions ?? [])].reverse().map((version) => (
                    <div key={version.version} className="flex items-center justify-between border-b border-slate-200 py-3 last:border-0">
                      <div>
                        <p className="text-sm font-semibold text-slate-800">v{version.version}</p>
                        <p className="text-xs text-slate-500">{version.changeNote} · {new Date(version.createdAt).toLocaleString()}</p>
                      </div>
                      {!systemOwned && <button type="button" onClick={() => setDraft({ ...draft, sections: version.sections })} className="text-xs font-semibold text-blue-600">恢复此结构</button>}
                    </div>
                  ))
                )}
              </div>
            )}

            <div className="sticky bottom-0 mt-6 flex items-center justify-end gap-3 border-t border-slate-200 bg-white/95 py-4 backdrop-blur">
              {!systemOwned && (
                <button type="button" onClick={save} className="flex items-center gap-2 rounded-xl border border-blue-200 px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50">
                  <Save size={17} /> 保存新版本
                </button>
              )}
              <button type="button" onClick={applyTemplate} className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">
                <Check size={17} /> 应用到当前项目
              </button>
            </div>
          </section>
        ) : (
          <div className="grid place-items-center text-sm text-slate-500">请选择或新建模板</div>
        )}
      </div>
    </div>
  );
};
