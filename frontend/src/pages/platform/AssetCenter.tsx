import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Loader2, RefreshCw, Trash2, Upload } from 'lucide-react';
import { deleteMaterial, listMaterials, uploadMaterial, type Material } from '@/api/endpoints';
import { getImageUrl } from '@/api/client';
import { MaterialCenterModal, MaterialGeneratorModal } from '@/components/shared';
import { usePlatform } from '@/platform';

export const AssetCenter = () => {
  const fileRef = useRef<HTMLInputElement>(null);
  const { competition, projectContext } = usePlatform();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(false);
  const [toolboxOpen, setToolboxOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await listMaterials(projectContext.projectId || 'none');
      setMaterials(response.data?.materials ?? []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [projectContext.projectId]);

  const upload = async (file?: File) => {
    if (!file) return;
    await uploadMaterial(file, projectContext.projectId);
    await load();
    if (fileRef.current) fileRef.current.value = '';
  };

  const remove = async (material: Material) => {
    await deleteMaterial(material.id);
    setMaterials((current) => current.filter((item) => item.id !== material.id));
  };

  return (
    <div className="mx-auto max-w-[1500px] px-8 py-7">
      <header className="flex items-end justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-600">项目视觉资产</p>
          <h1 className="mt-1 text-3xl font-extrabold text-slate-950">素材中心</h1>
          <p className="mt-2 text-sm text-slate-500">{competition.shortName} · {projectContext.projectName || '全局素材'} · {materials.length} 项</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => setLibraryOpen(true)} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700">管理全部素材</button>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(event) => upload(event.target.files?.[0])} />
          <button type="button" onClick={() => fileRef.current?.click()} className="flex items-center gap-2 rounded-xl border border-blue-200 bg-white px-4 py-2.5 text-sm font-semibold text-blue-700"><Upload size={17} /> 上传</button>
          <button type="button" onClick={() => setToolboxOpen(true)} className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"><ImagePlus size={17} /> AI 生成与处理</button>
        </div>
      </header>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <h2 className="font-bold text-slate-950">当前项目素材</h2>
            <p className="mt-1 text-xs text-slate-500">AI 生图、整图编辑、框选编辑和智能擦除结果会自动保存到这里。</p>
          </div>
          <button type="button" onClick={load} className="flex items-center gap-2 text-sm font-semibold text-blue-600"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> 刷新</button>
        </div>

        {loading && materials.length === 0 ? (
          <div className="grid min-h-80 place-items-center"><Loader2 className="animate-spin text-blue-600" /></div>
        ) : materials.length === 0 ? (
          <div className="grid min-h-80 place-items-center text-center">
            <div>
              <ImagePlus className="mx-auto text-slate-300" size={40} />
              <p className="mt-3 text-sm font-semibold text-slate-700">暂无项目素材</p>
              <p className="mt-1 text-xs text-slate-500">上传真实项目图片，或使用 AI 工具生成与赛事上下文相关的素材。</p>
            </div>
          </div>
        ) : (
          <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
            {materials.map((material) => (
              <article key={material.id} className="group overflow-hidden rounded-xl border border-slate-200 bg-white">
                <div className="relative aspect-square bg-slate-100">
                  <img src={getImageUrl(material.url)} alt={material.name || material.filename} className="h-full w-full object-cover" loading="lazy" />
                  <button type="button" onClick={() => remove(material)} aria-label="删除素材" className="absolute right-2 top-2 rounded-lg bg-white/90 p-2 text-slate-500 opacity-0 shadow transition group-hover:opacity-100 hover:text-rose-600"><Trash2 size={16} /></button>
                </div>
                <div className="p-3">
                  <p className="truncate text-sm font-semibold text-slate-800">{material.name || material.original_filename || material.filename}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">{material.prompt || material.caption || '上传素材'}</p>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <MaterialGeneratorModal projectId={projectContext.projectId} isOpen={toolboxOpen} onClose={() => { setToolboxOpen(false); load(); }} />
      <MaterialCenterModal isOpen={libraryOpen} onClose={() => { setLibraryOpen(false); load(); }} />
    </div>
  );
};
