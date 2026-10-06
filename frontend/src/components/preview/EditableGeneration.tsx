import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';

type GenerationState = {
  ready: boolean;
  credit_estimate?: { amount: number };
  validation_page_number?: number | null;
  validation_credit_estimate?: { amount: number } | null;
  task?: { task_id: string; status: string; error_message?: string; progress: { total?: number; completed?: number; current_step?: string; validation_only?: boolean; validation_passed?: boolean; diagnostic_id?: string } } | null;
};
const active = (value: GenerationState | null) => ['PENDING', 'PROCESSING'].includes(value?.task?.status || '');

// Keyed wrapper prevents late responses from one project navigating another.
export function EditableGeneration(props: { projectId: string; allImagesReady: boolean }) {
  return <GenerationSession key={props.projectId} {...props} />;
}

function GenerationSession({ projectId, allImagesReady }: { projectId: string; allImagesReady: boolean }) {
  const navigate = useNavigate();
  const [state, setState] = useState<GenerationState | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [validateOnly, setValidateOnly] = useState(false);
  const mounted = useRef(false), followCompletion = useRef(false), requestSequence = useRef(0), submitting = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const url = `/api/projects/${projectId}/editable-generation`;
  const openEditor = () => navigate(`/project/${projectId}/editor`);

  function accept(next: GenerationState) {
    setState(next); setError('');
    if (next.ready) {
      if (followCompletion.current) openEditor();
      return;
    }
    if (active(next)) {
      followCompletion.current = !next.task?.progress.validation_only;
      timer.current = setTimeout(() => void refresh(), 1500);
    }
  }
  async function refresh() {
    clearTimeout(timer.current);
    const sequence = ++requestSequence.current;
    try {
      const response = await apiClient.get(url);
      if (mounted.current && requestSequence.current === sequence) accept(response.data.data);
    } catch {
      if (mounted.current && requestSequence.current === sequence) setError('无法读取转换状态。任务可能仍在后台进行，请重新检查。');
    }
  }
  useEffect(() => {
    mounted.current = true; void refresh();
    return () => { mounted.current = false; requestSequence.current++; clearTimeout(timer.current); };
  }, [projectId]);

  async function start() {
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setConfirm(false); setError('');
    clearTimeout(timer.current); requestSequence.current++;
    followCompletion.current = !validateOnly;
    try {
      const response = await apiClient.post(url, validateOnly ? { mode: 'validate_failed_page' } : {});
      if (mounted.current) accept(response.data.data);
    } catch (e: any) {
      if (mounted.current) setError(e.response?.data?.error?.message || '提交失败或响应中断，请先重新检查任务状态，避免重复提交。');
    } finally { submitting.current = false; if (mounted.current) setBusy(false); }
  }
  const running = active(state);
  return <div className="relative">
    <button type="button" className="px-3 py-2 text-sm border rounded-lg border-yellow-500 bg-yellow-50 text-gray-900 disabled:opacity-50"
      disabled={busy || running || !state || !!error || (!state.ready && !allImagesReady)}
      title={!allImagesReady && !state?.ready ? '请先完成所有页面图片；当前图片仍可使用原导出功能' : '图片生成后可直接导出，也可继续转换为可编辑对象'}
      onClick={() => { if (state?.ready) openEditor(); else { setValidateOnly(false); setConfirm(true); } }}>
      {state?.ready ? '进入在线编辑' : busy ? '正在提交…' : running ? (state?.task?.progress.validation_only ? '正在验证失败页…' : '正在生成可编辑 PPT…') : '生成可编辑 PPT'}
    </button>
    {(running || error || state?.task?.status === 'FAILED' || state?.task?.progress.validation_passed) && <div className="absolute right-0 top-full mt-2 z-[100] w-80 p-4 border rounded-lg bg-white text-gray-900 shadow-lg">
      {running && <p role="status">{state?.task?.progress.current_step || '等待转换'}（{state?.task?.progress.completed || 0}/{state?.task?.progress.total || 0} 页）</p>}
      {state?.task?.status === 'FAILED' && <p role="alert">{state.task.error_message || '转换失败'} 原图与普通导出仍可使用，可重试转换。</p>}
      {state?.task?.progress.diagnostic_id && <p className="text-xs mt-2 break-all">诊断编号：{state.task.progress.diagnostic_id}</p>}
      {state?.validation_page_number && !running && <button className="underline mt-2" disabled={busy || !!error || !allImagesReady} onClick={() => { setValidateOnly(true); setConfirm(true); }}>仅验证第 {state.validation_page_number} 页</button>}
      {state?.task?.progress.validation_passed && <p role="status">{state.task.progress.current_step}。尚未生成整套编辑文档；点击“生成可编辑 PPT”继续。</p>}
      {error && <p role="alert">{error}</p>}
      {error && <button className="underline mt-2" onClick={() => void refresh()}>重新检查状态</button>}
      <p className="text-xs mt-2 text-gray-500">{state?.task?.progress.validation_only ? '单页验证不自动继续整套转换，也不进入编辑器。' : '全部页面转换和文件检查成功后自动进入在线编辑。'}刷新页面可以恢复任务进度。</p>
    </div>}
    {confirm && createPortal(<div role="dialog" aria-modal="true" aria-label="生成可编辑 PPT" className="fixed inset-0 z-[200] bg-black/40 flex items-center justify-center p-5" onKeyDown={e => {
      if (e.key === 'Escape') setConfirm(false);
      if (e.key === 'Tab') {
        const buttons = e.currentTarget.querySelectorAll<HTMLButtonElement>('button');
        if (e.shiftKey && document.activeElement === buttons[0]) { e.preventDefault(); buttons[buttons.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === buttons[buttons.length - 1]) { e.preventDefault(); buttons[0].focus(); }
      }
    }}>
      <div className="bg-white text-gray-900 rounded-xl p-6 max-w-lg shadow-xl">
        <h2 className="font-semibold text-lg mb-3">{validateOnly ? `仅验证第 ${state?.validation_page_number} 页` : '生成可编辑 PPT'}</h2>
        <p>{validateOnly ? '只验证这页的识别、对象和 PPTX 结构；成功后保留缓存，不发布半套文档，不自动转换其他页。' : '将整套页面图片识别为文字、卡片、图片和表格对象，生成成功后自动进入在线编辑。'}</p>
        <p className="text-sm text-gray-600 mt-3">这一步会调用你配置的图片识别模型，预估 {(validateOnly ? state?.validation_credit_estimate : state?.credit_estimate)?.amount ?? '—'} 积分（管理员按现有规则免扣，但模型服务商仍可能收费）。{validateOnly ? '之后整套转换仍按整套积分计费；缓存复用不保证跨服务重启有效。' : '识别可能存在偏差，进入编辑器后请核对。'}原图片和普通导出不受影响。</p>
        <div className="flex justify-end gap-4 mt-5"><button autoFocus onClick={() => setConfirm(false)}>取消</button><button className="bg-yellow-400 rounded-lg px-4 py-2" onClick={() => void start()}>{validateOnly ? '确认仅验证这一页' : '开始生成并进入编辑'}</button></div>
      </div>
    </div>, document.body)}
  </div>;
}
