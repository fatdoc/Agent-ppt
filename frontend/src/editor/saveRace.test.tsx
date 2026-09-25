import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi, it, expect, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
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
 const session=new URL(frame.src).searchParams.get('session')!;
 const send=(type:Parameters<typeof message>[1],payload={})=>act(()=>{window.dispatchEvent(new MessageEvent('message',{origin:location.origin,source:frame.contentWindow,data:message(session,type,payload)}));});
 send('READY');return {send};
}
it('serializes saving and retains edits made while the first save is in flight',async()=>{
 let finish:(v:unknown)=>void=()=>{};
 vi.mocked(apiClient.put).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockResolvedValueOnce({data:{data:{revision:3}}});
 const {send}=await mount();
 send('DOCUMENT_CHANGED',{sequence:1,slides:[{id:'p',content:'first'}]});fireEvent.click(screen.getByText('保存'));
 send('DOCUMENT_CHANGED',{sequence:2,slides:[{id:'p',content:'second'}]});
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
