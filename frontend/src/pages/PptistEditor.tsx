import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useExportTasksStore } from '../store/useExportTasksStore';
import { apiClient } from '../api/client';
import { message, receive } from '../../../shared/pptistProtocol';
type Doc = { revision: number; slides: unknown[]; width: number; height: number; readonly?: boolean; reason?: string };
export default function PptistEditor() {
  const { projectId }=useParams();
  const [params]=useSearchParams();
  // A reused route must not retain the previous project's draft or handshake.
  return <PptistEditorSession key={`${projectId}:${params.get('fixture')==='1'}`} />;
}
function PptistEditorSession() {
  const { projectId }=useParams(); const navigate=useNavigate();const [params]=useSearchParams();
  const fixture=import.meta.env.DEV && params.get('fixture')==='1';
  const frame=useRef<HTMLIFrameElement>(null);
  const [doc,setDoc]=useState<Doc|null>(null),[status,setStatus]=useState('正在加载语义文档…'),[error,setError]=useState('');
  const [history,setHistory]=useState<{revision:number;created_at:string}[]|null>(null);
  const [taskId,setTaskId]=useState(''),[download,setDownload]=useState('');
  const [session,setSession]=useState(()=>crypto.randomUUID());
  const ready=useRef(false),loaded=useRef(false),dirty=useRef(false),saving=useRef(false),sequence=useRef(0),latest=useRef<unknown[]>([]),revision=useRef(0),timer=useRef<ReturnType<typeof setTimeout>>();
  const activeSession=useRef<string>(session);activeSession.current=session;
  useEffect(()=>{activeSession.current=session;return()=>{activeSession.current='';clearTimeout(timer.current);};},[]);
  async function save() {
    if(saving.current || !dirty.current) return;
    if(fixture){setStatus('人工测试样例 · 修改仅在当前会话，未保存到项目');return;}
    const seq=sequence.current, sid=activeSession.current, submitted=latest.current; saving.current=true;setStatus('正在保存…');
    let succeeded=false;
    try {
      const result=await apiClient.put(`/api/projects/${projectId}/editor-document`,{base_revision:revision.current,slides:submitted});
      if(activeSession.current!==sid)return;
      revision.current=result.data.data.revision;succeeded=true;setError('');
      // Reload only acknowledged content, never the initial document or a newer
      // in-flight draft. Keep latest/dirty independently for serial saves.
      setDoc(previous=>previous ? {...previous,...result.data.data,slides:result.data.data.slides??submitted} : previous);
      dirty.current=sequence.current!==seq;
      setStatus(dirty.current?'有新修改，等待保存':`已保存 · 版本 ${revision.current}`);
      frame.current?.contentWindow?.postMessage(message(sid,'SAVE_RESULT',{ok:true,sequence:seq,revision:revision.current}),location.origin);
    } catch(e: any) {
      if(activeSession.current!==sid)return;
      setError(e.response?.data?.error?.message || '保存失败，当前草稿仍保留，请重试');setStatus('未保存');
      frame.current?.contentWindow?.postMessage(message(sid,'SAVE_RESULT',{ok:false,sequence:seq,message:'保存失败；草稿已保留'}),location.origin);
    } finally {if(activeSession.current===sid){saving.current=false;if(succeeded&&dirty.current)timer.current=setTimeout(()=>void save(),300);}}
  }
  async function restoreVersion(target:number) {
    if(dirty.current||saving.current){setError('请先保存当前修改，或下载草稿后重新加载，再恢复历史版本。');return;}
    try {
      const r=await apiClient.post(`/api/projects/${projectId}/editor-document/restore`,{base_revision:revision.current,revision:target});
      revision.current=r.data.data.revision;latest.current=r.data.data.slides;setDoc(r.data.data);setHistory(null);retry();setStatus(`已恢复为新版本 ${revision.current}`);
    } catch(e:any){setError(e.response?.data?.error?.message||'恢复失败');}
  }
  function downloadDraft(){
    const url=URL.createObjectURL(new Blob([JSON.stringify({base_revision:revision.current,slides:latest.current},null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`editor-draft-${projectId}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function exportCurrent() {
    if(fixture)return;
    await save();
    if(dirty.current||saving.current){setError('请等待保存成功后再导出。');return;}
    try {
      const r=await apiClient.post(`/api/projects/${projectId}/editor-document/export`,{revision:revision.current});
      useExportTasksStore.getState().addTask({id:r.data.data.task_id,taskId:r.data.data.task_id,projectId:projectId!,type:'semantic-editor',status:r.data.data.status});
      void useExportTasksStore.getState().pollTask(r.data.data.task_id,projectId!,r.data.data.task_id);
      setTaskId(r.data.data.task_id);setDownload('');setStatus(`正在导出版本 ${revision.current}`);
    } catch(e:any){setError(e.response?.data?.error?.message||'导出提交失败');}
  }
  useEffect(()=>{
    if(!taskId)return;
    let stopped=false;
    const poll=async()=>{
      try {
        const r=await apiClient.get(`/api/projects/${projectId}/editor-document/export-tasks/${taskId}`);
        if(stopped)return;const t=r.data.data;
        if(t.status==='COMPLETED'){setDownload(t.progress.download_url);setStatus(`版本 ${t.progress.revision} 导出完成`);clearInterval(id);}
        else if(t.status==='FAILED'){setError('语义导出失败，可保留当前修改后重试。');clearInterval(id);}
      } catch {if(!stopped){setError('导出状态读取失败');clearInterval(id);}}
    };
    const id=setInterval(()=>void poll(),1000);void poll();
    return()=>{stopped=true;clearInterval(id);};
  },[taskId,projectId]);
  useEffect(()=>{
    let cancelled=false;
    (fixture?fetch('/editor-fixture/document.json').then(r=>r.json()):apiClient.get(`/api/projects/${projectId}/editor-document`).then(r=>r.data.data))
      .then(d=>{if(cancelled)return;setDoc(d);revision.current=d.revision;latest.current=d.slides;setStatus(fixture?'人工测试样例 · 不保存到项目':`已加载 · 版本 ${d.revision}`);})
      .catch((e)=>{if(!cancelled)setError(e.response?.data?.error?.message || '无法加载语义文档');});
    return ()=>{cancelled=true;};
  },[projectId,fixture]);
  useEffect(()=>{
    function load(){if(doc&&ready.current&&!loaded.current&&!doc.readonly){loaded.current=true;frame.current?.contentWindow?.postMessage(message(session,'LOAD_DOCUMENT',{...doc,fixture}),location.origin);}}
    function onMessage(event:MessageEvent){
      const m=receive(event,frame.current?.contentWindow||null,session,location.origin);if(!m)return;
      if(m.type==='READY'&&!ready.current){ready.current=true;load();}
      if(m.type==='DOCUMENT_CHANGED'&&loaded.current&&(m.payload.sequence as number)>sequence.current){
        sequence.current=m.payload.sequence as number;latest.current=m.payload.slides as unknown[];dirty.current=true;setStatus('有未保存修改');setError('');clearTimeout(timer.current);timer.current=setTimeout(()=>void save(),1000);
      }
      if(m.type==='ERROR')setError(String(m.payload.message));
      if(m.type==='REQUEST_EXPORT'&&loaded.current)void exportCurrent();
    }
    window.addEventListener('message',onMessage);load();
    const timeout=setTimeout(()=>{if(!ready.current)setError('编辑器未响应，请检查 /editor-app/ 构建或重试。');},15000);
    return()=>{window.removeEventListener('message',onMessage);clearTimeout(timeout);};
  },[session,doc]);
  useEffect(()=>{const warn=(e:BeforeUnloadEvent)=>{if(dirty.current){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[]);
  function retry(){ready.current=false;loaded.current=false;sequence.current=0;setError('');setSession(crypto.randomUUID());}
  return <main className="h-screen flex flex-col bg-gray-50">
    <header className="h-14 px-5 flex items-center gap-5 border-b bg-white">
      <button onClick={()=>{if(!dirty.current||window.confirm('有未保存修改，确认离开？'))navigate(`/project/${projectId}/preview`);}}>返回预览</button>
      <strong>在线编辑</strong><span role="status" className="text-sm text-gray-500 flex-1">{status}</span>
      <button onClick={()=>void save()} disabled={fixture} className="px-4 py-2 bg-yellow-400 rounded">保存</button>
      <button disabled={fixture||!doc} onClick={()=>void apiClient.get(`/api/projects/${projectId}/editor-document/revisions`).then(r=>setHistory(r.data.data)).catch(()=>setError('历史版本读取失败'))}>历史版本</button>
      <button disabled={fixture||!!doc?.readonly} onClick={()=>frame.current?.contentWindow?.postMessage(message(session,'REQUEST_EXPORT'),location.origin)} className="px-3 py-2 border rounded">导出当前版本</button>
      {download&&<a href={download} className="text-blue-700">下载 PPTX</a>}
    </header>
    {fixture&&<div className="px-5 py-2 bg-amber-100">人工测试样例：不代表图片自动转换，不会保存到项目。</div>}
    {!fixture&&doc&&<div className="px-5 py-2 bg-amber-50 text-sm text-amber-900">可编辑版本独立于原图片保存。自动识别内容请核对文字、位置和素材；编辑后请在此导出当前版本。</div>}
    {history&&<div className="px-5 py-3 bg-white border-b flex gap-3 flex-wrap"><button onClick={()=>setHistory(null)}>关闭历史</button>{history.map(h=><button key={h.revision} onClick={()=>void restoreVersion(h.revision)} className="border rounded px-2">恢复版本 {h.revision}</button>)}</div>}
    {error&&<div role="alert" className="px-5 py-3 bg-red-50 text-red-800">{error} {dirty.current&&<button onClick={downloadDraft}>下载未保存草稿</button>} {doc&&!dirty.current&&<button onClick={retry}>重新加载编辑器</button>}</div>}
    {doc?.readonly?<div className="p-8">此语义文档暂为只读：{doc.reason}。原文档保持不变。</div>:doc&&<iframe key={session} ref={frame} title="PPTist 在线编辑器" src={`/editor-app/?session=${session}`} className="w-full flex-1 border-0" />}
    {!doc&&error&&<p className="p-8 text-gray-600">请返回图片预览，点击“生成可编辑 PPT”。全部页面转换成功后会自动进入此处；历史图片和原导出不受影响。</p>}
  </main>;
}
