import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { EducationPortal } from './Portal';
import { create, patch, data, type Snapshot } from './api';
import { uploadReferenceFile, triggerFileParse } from '../api/endpoints';
vi.mock('./api', async () => ({ ...(await vi.importActual<typeof import('./api')>('./api')), create: vi.fn(), patch: vi.fn(), data: vi.fn() }));
vi.mock('../api/endpoints', () => ({ uploadReferenceFile: vi.fn(), triggerFileParse: vi.fn() }));
const snapshot = () => ({ project_id: 'new-project', revision: 1, content: { profile: { name: '', roles: [] }, preferences: {}, reference_file_ids: [], raw_material: '' } }) as unknown as Snapshot;
beforeEach(() => {
  vi.clearAllMocks(); vi.mocked(create).mockImplementation(async () => snapshot());
  vi.mocked(patch).mockImplementation(async (_id, revision, content) => ({ ...snapshot(), revision: revision + 1, content }));
  vi.mocked(data).mockImplementation(async () => snapshot());
});
function setup(url: string, section = 'create') {
  return render(<MemoryRouter initialEntries={[url]}><Routes><Route path="/education" element={<EducationPortal section={section} projects={[{ project_id:'existing', project_title:'已有作品' }]} onCreated={async()=>{}}/>}/><Route path="/education/project/:id" element={<h1>已进入工作台</h1>}/></Routes></MemoryRouter>);
}
it('homepage links lead to real input modes and existing projects', () => {
  setup('/education', 'home');
  expect(screen.getByRole('link', { name:/上传文件生成/ })).toHaveAttribute('href','/education/create?mode=file');
  expect(screen.getByRole('link', { name:/导入已有稿件/ })).toHaveAttribute('href','/education/create?mode=import');
  expect(screen.getByRole('link', { name:/已有作品/ })).toHaveAttribute('href','/education/project/existing');
});
it('saves material, competition context and template before opening the workbench', async () => {
  setup('/education?mode=text&style=ecology');
  fireEvent.change(screen.getByLabelText('作品名称'), { target:{value:'餐饮服务项目'} });
  fireEvent.change(screen.getByLabelText('项目材料'), { target:{value:'现场摆台、服务与核验。'} });
  fireEvent.change(screen.getByLabelText('赛道'), { target:{value:'餐饮服务'} });
  fireEvent.click(screen.getByRole('button', { name:'进入内容工作台' }));
  await screen.findByRole('heading',{name:'已进入工作台'});
  const content = vi.mocked(patch).mock.calls[0][2];
  expect(content.profile).toMatchObject({name:'餐饮服务项目',track:'餐饮服务',education_level:'高职专科'});
  expect(content.raw_material).toBe('现场摆台、服务与核验。'); expect(content.preferences.style).toBe('ecology');
  expect(data).not.toHaveBeenCalled();
});
it('imports the exact user outline and description without starting generation', async () => {
  setup('/education?mode=import');
  fireEvent.change(screen.getByLabelText('已有大纲'), {target:{value:'## 第1页 团队\n- 原稿不改'}});
  fireEvent.change(screen.getByLabelText('逐页描述（选填）'), {target:{value:'## 第1页 团队\n保留四列布局。'}});
  fireEvent.click(screen.getByRole('button',{name:'进入内容工作台'}));
  await screen.findByRole('heading',{name:'已进入工作台'});
  expect(data).toHaveBeenCalledWith('post','/api/projects/new-project/competition/import',{revision:2,outline:'## 第1页 团队\n- 原稿不改',descriptions:'## 第1页 团队\n保留四列布局。'});
});
it('keeps a created project recoverable when file parsing fails instead of duplicating it', async () => {
  vi.mocked(uploadReferenceFile).mockResolvedValue({data:{file:{id:'source'}}} as never);
  vi.mocked(triggerFileParse).mockRejectedValue(new Error('解析连接失败'));
  const {container}=setup('/education');
  const file = new File(['材料'],'方案.txt',{type:'text/plain'});
  fireEvent.change(container.querySelector('input[type=file]')!,{target:{files:[file]}});
  fireEvent.click(screen.getByRole('button',{name:'进入内容工作台'}));
  await screen.findByRole('alert');
  expect(vi.mocked(patch).mock.calls[1][2].reference_file_ids).toEqual(['source']);
  fireEvent.click(screen.getByRole('button',{name:'继续已创建项目'}));
  await waitFor(()=>expect(create).toHaveBeenCalledTimes(1));
  await screen.findByRole('heading',{name:'已进入工作台'});
});
