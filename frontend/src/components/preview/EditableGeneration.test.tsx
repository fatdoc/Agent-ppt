import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { EditableGeneration } from './EditableGeneration';
import { apiClient } from '../../api/client';
vi.mock('../../api/client',()=>({apiClient:{get:vi.fn(),post:vi.fn()}}));
afterEach(()=>{vi.clearAllMocks();});
const response=(data:unknown)=>({data:{data}});
function mount(ready=true){return render(<MemoryRouter initialEntries={['/preview']}><Routes><Route path="/preview" element={<EditableGeneration projectId="p" allImagesReady={ready}/>}/><Route path="/project/p/editor" element={<p>编辑页已打开</p>}/></Routes></MemoryRouter>);}
it('requires images and confirmation before starting the billable stage',async()=>{
 vi.mocked(apiClient.get).mockResolvedValue(response({ready:false,task:null,credit_estimate:{amount:110}}));
 mount(false);await waitFor(()=>expect(apiClient.get).toHaveBeenCalled());
 expect(screen.getByRole('button',{name:'生成可编辑 PPT'})).toBeDisabled();expect(apiClient.post).not.toHaveBeenCalled();
});
it('starts then polls until document ready and automatically opens editor',async()=>{
 vi.mocked(apiClient.get).mockResolvedValueOnce(response({ready:false,task:null,credit_estimate:{amount:110}})).mockResolvedValue(response({ready:true}));
 vi.mocked(apiClient.post).mockResolvedValue(response({ready:false,task:{task_id:'t',status:'PENDING',progress:{total:2,completed:0}}}));
 mount();await waitFor(()=>expect(screen.getByRole('button',{name:'生成可编辑 PPT'})).toBeEnabled());
 fireEvent.click(screen.getByRole('button',{name:'生成可编辑 PPT'}));expect(screen.getByRole('dialog')).toHaveTextContent('110');
 expect(apiClient.post).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'开始生成并进入编辑'}));
 await screen.findByText('编辑页已打开',{}, {timeout:3000});
 expect(apiClient.post).toHaveBeenCalledWith('/api/projects/p/editable-generation',{});
});
it('does not redirect an already editable preview until user opens editor',async()=>{
 vi.mocked(apiClient.get).mockResolvedValue(response({ready:true}));mount();
 await screen.findByText('进入在线编辑');expect(screen.queryByText('编辑页已打开')).toBeNull();
 fireEvent.click(screen.getByText('进入在线编辑'));await screen.findByText('编辑页已打开');
});
it('resumes a pending task after refresh without submitting another conversion',async()=>{
 vi.mocked(apiClient.get).mockResolvedValueOnce(response({ready:false,task:{task_id:'existing',status:'PROCESSING',progress:{total:4,completed:2}}})).mockResolvedValue(response({ready:true}));
 mount();expect(await screen.findByRole('status')).toHaveTextContent('2/4');
 await screen.findByText('编辑页已打开',{}, {timeout:3000});expect(apiClient.post).not.toHaveBeenCalled();
});
it('a polling error asks to check status and never starts a duplicate job',async()=>{
 vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('offline')).mockResolvedValue(response({ready:true}));
 mount();await screen.findByText('重新检查状态');
 expect(screen.getByRole('button',{name:'生成可编辑 PPT'})).toBeDisabled();
 fireEvent.click(screen.getByText('重新检查状态'));await screen.findByText('进入在线编辑');expect(apiClient.post).not.toHaveBeenCalled();
});
it('failed conversion stays on preview and preserves retry rather than opening editor',async()=>{
 vi.mocked(apiClient.get).mockResolvedValue(response({ready:false,task:{status:'FAILED',error_message:'识别失败',progress:{}}}));mount();
 expect(await screen.findByRole('alert')).toHaveTextContent('原图与普通导出仍可使用');
 expect(screen.queryByText('编辑页已打开')).toBeNull();expect(screen.getByRole('button',{name:'生成可编辑 PPT'})).toBeEnabled();
});
it('late completion after leaving preview does not navigate',async()=>{
 let resolve:(v:unknown)=>void=()=>{};
 vi.mocked(apiClient.get).mockImplementation(()=>new Promise(r=>{resolve=r;}));
 const view=mount();view.unmount();await act(async()=>resolve(response({ready:true})));
 expect(screen.queryByText('编辑页已打开')).toBeNull();
});
