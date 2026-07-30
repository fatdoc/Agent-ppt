import { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  ImagePlus,
  Loader2,
  Palette,
  Search,
  Trash2,
  Upload,
} from 'lucide-react';
import {
  createUserStyleTemplate,
  deleteUserStyleTemplate,
  deleteUserTemplate,
  listUserStyleTemplates,
  listUserTemplates,
  uploadTemplate,
  uploadUserTemplate,
  type UserStyleTemplate,
  type UserTemplate,
} from '@/api/endpoints';
import { getImageUrl } from '@/api/client';
import { getTemplateFile } from '@/components/shared/TemplateSelector';
import { supportLevelLabel, usePlatform } from '@/platform';

const presets: UserTemplate[] = [
  { template_id: '1', name: '复古卷轴', template_image_url: '/templates/template_y.png', thumb_url: '/templates/template_y-thumb.webp' },
  { template_id: '2', name: '矢量插画', template_image_url: '/templates/template_vector_illustration.png', thumb_url: '/templates/template_vector_illustration-thumb.webp' },
  { template_id: '3', name: '拟物玻璃', template_image_url: '/templates/template_glass.png', thumb_url: '/templates/template_glass-thumb.webp' },
];

export const TemplateLibrary = () => {
  const fileRef = useRef<HTMLInputElement>(null);
  const { competition, projectContext, updateProjectContext } = usePlatform();
  const [templates, setTemplates] = useState<UserTemplate[]>([]);
  const [styles, setStyles] = useState<UserStyleTemplate[]>([]);
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState(projectContext.pptTemplateId ?? '1');
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [styleDraft, setStyleDraft] = useState({ name: '', description: '', color: '#2563eb' });

  const load = async () => {
    const [imageResponse, styleResponse] = await Promise.all([
      listUserTemplates(),
      listUserStyleTemplates(),
    ]);
    setTemplates(imageResponse.data?.templates ?? []);
    setStyles(styleResponse.data?.templates ?? []);
  };

  useEffect(() => { load(); }, []);

  const allTemplates = [...presets, ...templates].filter((template) =>
    (template.name || '未命名模板').toLowerCase().includes(query.toLowerCase()));

  const apply = async (template: UserTemplate) => {
    if (!projectContext.projectId) {
      setMessage('请先在 PPT 工作台关联项目。');
      return;
    }
    setBusy(template.template_id);
    setMessage('');
    try {
      const file = await getTemplateFile(template.template_id, templates);
      if (!file) throw new Error('无法读取模板文件');
      await uploadTemplate(projectContext.projectId, file);
      setSelectedId(template.template_id);
      updateProjectContext({ pptTemplateId: template.template_id });
      setMessage('模板已应用到当前真实项目。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '应用模板失败');
    } finally {
      setBusy(null);
    }
  };

  const upload = async (file?: File) => {
    if (!file) return;
    setBusy('upload');
    try {
      const response = await uploadUserTemplate(file, file.name.replace(/\.[^.]+$/, ''));
      if (response.data) setTemplates((current) => [response.data!, ...current]);
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const remove = async (template: UserTemplate) => {
    if (presets.some((item) => item.template_id === template.template_id)) return;
    await deleteUserTemplate(template.template_id);
    setTemplates((current) => current.filter((item) => item.template_id !== template.template_id));
  };

  const saveStyle = async () => {
    if (!styleDraft.name.trim() || !styleDraft.description.trim()) return;
    const response = await createUserStyleTemplate(styleDraft);
    if (response.data) {
      setStyles((current) => [response.data!, ...current]);
      setStyleDraft({ name: '', description: '', color: '#2563eb' });
    }
  };

  return (
    <div className="mx-auto max-w-[1500px] px-8 py-7">
      <header className="flex items-end justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-600">视觉模板资产</p>
          <h1 className="mt-1 text-3xl font-extrabold text-slate-950">PPT 模板库</h1>
          <p className="mt-2 text-sm text-slate-500">
            {competition.name} · {supportLevelLabel[competition.supportLevel]}
          </p>
        </div>
        <div className="flex gap-2">
          <label className="relative">
            <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索模板" className="h-11 rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm outline-none focus:border-blue-500" />
          </label>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(event) => upload(event.target.files?.[0])} />
          <button type="button" onClick={() => fileRef.current?.click()} className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700">
            {busy === 'upload' ? <Loader2 size={17} className="animate-spin" /> : <Upload size={17} />} 上传模板
          </button>
        </div>
      </header>

      {competition.supportLevel !== 'FULL' && (
        <p className="mt-5 rounded-xl bg-blue-50 px-4 py-3 text-sm text-blue-800">
          当前赛事没有专属模板推荐，仅展示平台通用模板与用户上传模板。
        </p>
      )}
      {message && <p className="mt-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">{message}</p>}

      <div className="mt-6 grid gap-5 xl:grid-cols-[1fr_360px]">
        <section className="grid content-start grid-cols-2 gap-4 lg:grid-cols-3">
          {allTemplates.map((template) => {
            const selected = selectedId === template.template_id;
            const image = getImageUrl(template.thumb_url || template.template_image_url);
            const preset = presets.some((item) => item.template_id === template.template_id);
            return (
              <article key={`${preset ? 'preset' : 'user'}-${template.template_id}`} className={`group overflow-hidden rounded-2xl border bg-white transition ${selected ? 'border-blue-500 shadow-md' : 'border-slate-200 hover:border-blue-300'}`}>
                <button type="button" onClick={() => apply(template)} className="block w-full text-left">
                  <div className="relative aspect-[16/10] overflow-hidden bg-slate-100">
                    <img src={image} alt={template.name || 'PPT 模板'} className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]" />
                    {selected && <span className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-blue-600 text-white"><CheckCircle2 size={18} /></span>}
                    {busy === template.template_id && <span className="absolute inset-0 grid place-items-center bg-white/70"><Loader2 className="animate-spin text-blue-600" /></span>}
                  </div>
                  <div className="flex items-center justify-between p-4">
                    <div>
                      <p className="text-sm font-bold text-slate-900">{template.name || '我的模板'}</p>
                      <p className="mt-1 text-xs text-slate-500">{preset ? '平台通用' : '我的模板'} · 点击应用</p>
                    </div>
                    <ImagePlus size={18} className="text-blue-600" />
                  </div>
                </button>
                {!preset && selectedId !== template.template_id && (
                  <button type="button" onClick={() => remove(template)} className="absolute opacity-0 group-hover:opacity-100" aria-label={`删除${template.name}`}><Trash2 /></button>
                )}
              </article>
            );
          })}
        </section>

        <aside className="h-fit rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <Palette size={20} className="text-blue-600" />
            <h2 className="font-bold text-slate-950">文字风格模板</h2>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-500">用文字描述字体、配色和版式偏好，供现有生成服务直接使用。</p>
          <input value={styleDraft.name} onChange={(event) => setStyleDraft({ ...styleDraft, name: event.target.value })} placeholder="风格名称" className="mt-4 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-500" />
          <textarea value={styleDraft.description} onChange={(event) => setStyleDraft({ ...styleDraft, description: event.target.value })} placeholder="例如：科技蓝、克制留白、信息图优先…" className="mt-2 min-h-24 w-full resize-none rounded-lg border border-slate-200 p-3 text-sm outline-none focus:border-blue-500" />
          <div className="mt-2 flex gap-2">
            <input type="color" value={styleDraft.color} onChange={(event) => setStyleDraft({ ...styleDraft, color: event.target.value })} className="h-10 w-12 rounded border border-slate-200 bg-white p-1" />
            <button type="button" onClick={saveStyle} className="flex-1 rounded-lg bg-blue-600 text-sm font-semibold text-white hover:bg-blue-700">保存风格</button>
          </div>
          <div className="mt-5 divide-y divide-slate-100">
            {styles.map((style) => (
              <div key={style.id} className="flex items-start gap-3 py-3">
                <span className="mt-1 h-4 w-4 shrink-0 rounded-full" style={{ backgroundColor: style.color || '#2563eb' }} />
                <button type="button" onClick={() => updateProjectContext({ style: style.description })} className="min-w-0 flex-1 text-left">
                  <p className="text-sm font-semibold text-slate-800">{style.name}</p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{style.description}</p>
                </button>
                <button type="button" onClick={async () => { await deleteUserStyleTemplate(style.id); setStyles((current) => current.filter((item) => item.id !== style.id)); }} className="p-1 text-slate-300 hover:text-rose-600"><Trash2 size={15} /></button>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
};
