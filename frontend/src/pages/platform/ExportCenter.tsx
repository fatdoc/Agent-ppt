import { useEffect, useState } from 'react';
import {
  CheckCircle2,
  Download,
  FileImage,
  FileText,
  Loader2,
  Presentation,
  RefreshCw,
  Video,
} from 'lucide-react';
import {
  exportEditablePPTX,
  exportImages,
  exportPDF,
  exportPPTX,
  exportVideo,
  getProject,
  listExports,
} from '@/api/endpoints';
import { usePlatform } from '@/platform';
import type { Project } from '@/types';

type ExportRecord = {
  filename: string;
  type: string;
  size: number;
  modified_at: string;
  download_url: string;
};

export const ExportCenter = () => {
  const { competition, projectContext } = usePlatform();
  const [project, setProject] = useState<Project | null>(null);
  const [records, setRecords] = useState<ExportRecord[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const projectId = projectContext.projectId;

  const load = async () => {
    if (!projectId) return;
    const [projectResponse, exportsResponse] = await Promise.all([getProject(projectId), listExports(projectId)]);
    setProject(projectResponse.data ?? null);
    setRecords(exportsResponse.data?.files ?? []);
  };

  useEffect(() => { load(); }, [projectId]);

  const downloadResult = (url?: string) => {
    if (!url) return;
    window.location.assign(url);
  };

  const run = async (type: string) => {
    if (!projectId) return;
    setBusy(type);
    setMessage('');
    try {
      if (type === 'pptx') {
        const response = await exportPPTX(projectId);
        downloadResult(response.data?.download_url_absolute || response.data?.download_url);
      } else if (type === 'pdf') {
        const response = await exportPDF(projectId);
        downloadResult(response.data?.download_url_absolute || response.data?.download_url);
      } else if (type === 'images') {
        const response = await exportImages(projectId);
        downloadResult(response.data?.download_url_absolute || response.data?.download_url);
      } else if (type === 'editable') {
        const response = await exportEditablePPTX(projectId, `${projectContext.projectName || '参赛版'}_可编辑.pptx`);
        setMessage(`可编辑 PPT 已进入真实导出队列：${response.data?.task_id || '任务已创建'}`);
      } else if (type === 'video') {
        const response = await exportVideo(projectId, { generateNarration: true });
        setMessage(`讲解视频已进入真实导出队列：${response.data?.task_id || '任务已创建'}`);
      }
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '导出失败');
    } finally {
      setBusy(null);
    }
  };

  const pageCount = project?.pages.length ?? 0;
  const ready = Boolean(project && pageCount > 0 && project.pages.every((page) => page.generated_image_url || page.generated_image_path));

  return (
    <div className="mx-auto max-w-[1500px] px-8 py-7">
      <header>
        <p className="text-sm font-semibold text-blue-600">交付与质量预检</p>
        <h1 className="mt-1 text-3xl font-extrabold text-slate-950">导出中心</h1>
      </header>

      <section className="mt-6 flex items-center gap-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <span className={`grid h-20 w-20 shrink-0 place-items-center rounded-full ${ready ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'}`}>
          {project ? <CheckCircle2 size={34} /> : <Loader2 size={30} className="animate-spin" />}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-bold text-slate-950">{ready ? '导出准备完成' : '可导出，建议先完成页面检查'}</h2>
          <p className="mt-1 text-sm text-slate-500">{projectContext.projectName || '未关联项目'} · {competition.shortName} · {pageCount} 页</p>
        </div>
        <div className="grid grid-cols-3 divide-x divide-slate-100 text-center">
          <div className="px-6"><p className="text-xs text-slate-500">页面</p><p className="mt-1 text-lg font-bold">{pageCount}</p></div>
          <div className="px-6"><p className="text-xs text-slate-500">模板</p><p className="mt-1 text-sm font-bold">{projectContext.style}</p></div>
          <div className="px-6"><p className="text-xs text-slate-500">状态</p><p className="mt-1 text-sm font-bold text-emerald-600">可导出</p></div>
        </div>
      </section>

      {message && <p className="mt-4 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">{message}</p>}

      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-bold text-slate-950">导出方式</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {[
            { id: 'pptx', label: '标准 PPTX', desc: '用于汇报演示', icon: Presentation },
            { id: 'editable', label: '可编辑 PPT', desc: '保留可编辑元素', icon: FileText },
            { id: 'pdf', label: 'PDF 预览', desc: '便于审核分享', icon: FileText },
            { id: 'images', label: '页面图片', desc: '逐页图片或 ZIP', icon: FileImage },
            { id: 'video', label: '讲解视频', desc: '页面与讲解稿合成', icon: Video },
          ].map(({ id, label, desc, icon: Icon }) => (
            <button type="button" disabled={!projectId || busy !== null} key={id} onClick={() => run(id)} className="rounded-xl border border-slate-200 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50/40 disabled:opacity-50">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600">{busy === id ? <Loader2 size={19} className="animate-spin" /> : <Icon size={19} />}</span>
              <span className="mt-3 block text-sm font-bold text-slate-900">{label}</span>
              <span className="mt-1 block text-xs text-slate-500">{desc}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-slate-950">历史导出记录</h2>
          <button type="button" onClick={load} className="flex items-center gap-2 text-sm font-semibold text-blue-600"><RefreshCw size={16} /> 刷新</button>
        </div>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-4 py-3">文件名</th><th className="px-4 py-3">格式</th><th className="px-4 py-3">大小</th><th className="px-4 py-3">导出时间</th><th className="px-4 py-3">操作</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {records.length === 0 ? <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500">暂无真实导出记录</td></tr> : records.map((record) => (
                <tr key={`${record.filename}-${record.modified_at}`}>
                  <td className="px-4 py-3 font-medium text-slate-800">{record.filename}</td>
                  <td className="px-4 py-3 text-slate-500">{record.type}</td>
                  <td className="px-4 py-3 text-slate-500">{(record.size / 1024 / 1024).toFixed(1)} MB</td>
                  <td className="px-4 py-3 text-slate-500">{new Date(record.modified_at).toLocaleString()}</td>
                  <td className="px-4 py-3"><a href={record.download_url} className="inline-flex items-center gap-1 font-semibold text-blue-600"><Download size={15} /> 下载</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
