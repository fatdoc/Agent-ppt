import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi, it, expect, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes, Link } from 'react-router-dom';
import PptistEditor from '../pages/PptistEditor';
import { message } from '../../../shared/pptistProtocol';
import { apiClient } from '../api/client';
vi.mock('../api/client',()=>({apiClient:{get:vi.fn(),put:vi.fn(),post:vi.fn()}}));
afterEach(()=>{vi.clearAllMocks();});
const document={revision:1,width:1280,height:720,slides:[{id:'p',elements:[]}]};
async function mount(){
 vi.mocked(apiClient.get).mockResolvedValue({data:{data:document}});
 render(<MemoryRouter initialEntries={['/project/p/editor']}><Routes><Route path="/project/:projectId/editor" element={<PptistEditor/>}/></Routes></MemoryRouter>);
 const frame=await screen.findByTitle('PPTist 在线编辑器') as HTMLIFrameElement;
 expect(new URL(frame.src).pathname).toBe('/editor-app/index.html');
 const session=new URL(frame.src).searchParams.get('session')!;
 const send=(type:Parameters<typeof message>[1],payload={})=>act(()=>{window.dispatchEvent(new MessageEvent('message',{origin:location.origin,source:frame.contentWindow,data:message(session,type,payload)}));});
 send('READY');return {send,frame};
}
it('serializes saving and retains edits made while the first save is in flight',async()=>{
 let finish:(v:unknown)=>void=()=>{};
 vi.mocked(apiClient.put).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockResolvedValueOnce({data:{data:{revision:3}}});
 const {send}=await mount();
 send('DOCUMENT_CHANGED',{sequence:1,slides:[{id:'p',content:'first'}]});fireEvent.click(screen.getByText('保存'));
 send('DOCUMENT_CHANGED',{sequence:2,slides:[{id:'p',content:'second'}]});
 send('ERROR',{message:'error while draft pending'});
 expect(screen.queryByText('重新加载编辑器')).toBeNull();
 fireEvent.click(screen.getByText('保存'));expect(apiClient.put).toHaveBeenCalledTimes(1);
 await act(async()=>finish({data:{data:{revision:2}}}));
 await waitFor(()=>expect(apiClient.put).toHaveBeenCalledTimes(2),{timeout:2000});
 expect(vi.mocked(apiClient.put).mock.calls[1][1]).toEqual({base_revision:2,slides:[{id:'p',content:'second'}]});
 await screen.findByText('已保存 · 版本 3');
});
it('409 keeps unsaved contents and never announces saved',async()=>{
 vi.mocked(apiClient.put).mockRejectedValue({response:{status:409,data:{error:{message:'版本冲突，草稿保留'}}}});
 const {send}=await mount();send('DOCUMENT_CHANGED',{sequence:1,slides:[{id:'p',content:'draft'}]});
 fireEvent.click(screen.getByText('保存'));await screen.findByText('版本冲突，草稿保留');
 expect(screen.getByRole('status').textContent).toBe('未保存');
 expect(screen.queryByText(/已保存/)).toBeNull();
});

it('reloads the acknowledged snapshot after a clean editor error',async()=>{
 const changed=[{id:'p',content:'saved content'}];
 vi.mocked(apiClient.put).mockResolvedValue({data:{data:{...document,revision:2,slides:changed}}});
 const {send}=await mount();
 send('DOCUMENT_CHANGED',{sequence:1,slides:changed});fireEvent.click(screen.getByText('保存'));
 await screen.findByText('已保存 · 版本 2');send('ERROR',{message:'editor error'});
 fireEvent.click(screen.getByText('重新加载编辑器'));
 const fresh=await screen.findByTitle('PPTist 在线编辑器') as HTMLIFrameElement;
 const post=vi.spyOn(fresh.contentWindow!,'postMessage');
 const sid=new URL(fresh.src).searchParams.get('session')!;
 act(()=>window.dispatchEvent(new MessageEvent('message',{origin:location.origin,source:fresh.contentWindow,data:message(sid,'READY')})));
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'LOAD_DOCUMENT',payload:expect.objectContaining({revision:2,slides:changed})}),location.origin);
});

it('starts a fresh editor session when the project route changes',async()=>{
 const next={...document,revision:9,slides:[{id:'q',elements:[]}]};
 let finishOld:(v:unknown)=>void=()=>{};
 vi.mocked(apiClient.put).mockImplementationOnce(()=>new Promise(resolve=>{finishOld=resolve;})).mockResolvedValueOnce({data:{data:{...next,revision:10}}});
 vi.mocked(apiClient.get).mockResolvedValueOnce({data:{data:document}}).mockResolvedValueOnce({data:{data:next}});
 render(<MemoryRouter initialEntries={['/project/p/editor']}><Link to="/project/q/editor">switch project</Link><Routes><Route path="/project/:projectId/editor" element={<PptistEditor/>}/></Routes></MemoryRouter>);
 const first=await screen.findByTitle('PPTist 在线编辑器') as HTMLIFrameElement;
 const firstSession=new URL(first.src).searchParams.get('session')!;
 act(()=>window.dispatchEvent(new MessageEvent('message',{origin:location.origin,source:first.contentWindow,data:message(firstSession,'READY')})));
 act(()=>window.dispatchEvent(new MessageEvent('message',{origin:location.origin,source:first.contentWindow,data:message(firstSession,'DOCUMENT_CHANGED',{sequence:5,slides:[{id:'p',content:'old pending'}]})})));
 fireEvent.click(screen.getByText('保存'));
 fireEvent.click(screen.getByText('switch project'));
 await screen.findByText('已加载 · 版本 9');
 const second=screen.getByTitle('PPTist 在线编辑器') as HTMLIFrameElement;
 expect(second).not.toBe(first);
 const secondSession=new URL(second.src).searchParams.get('session')!;
 expect(secondSession).not.toBe(firstSession);
 const post=vi.spyOn(second.contentWindow!,'postMessage');
 act(()=>window.dispatchEvent(new MessageEvent('message',{origin:location.origin,source:second.contentWindow,data:message(secondSession,'READY')})));
 expect(post).toHaveBeenCalledWith(expect.objectContaining({type:'LOAD_DOCUMENT',payload:expect.objectContaining(next)}),location.origin);
 await act(async()=>finishOld({data:{data:{...document,revision:2}}}));
 expect(screen.getByRole('status').textContent).toBe('已加载 · 版本 9');
 act(()=>window.dispatchEvent(new MessageEvent('message',{origin:location.origin,source:second.contentWindow,data:message(secondSession,'DOCUMENT_CHANGED',{sequence:1,slides:[{id:'q',content:'new project'}]})})));
 fireEvent.click(screen.getByText('保存'));
 await screen.findByText('已保存 · 版本 10');
 expect(vi.mocked(apiClient.put).mock.calls[1]).toEqual(['/api/projects/q/editor-document',{base_revision:9,slides:[{id:'q',content:'new project'}]}]);
});
