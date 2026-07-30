import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PptEditor } from '@/pages/PptEditor';
import { normalizeSpec } from '@/utils/specState';

const mocks = vi.hoisted(() => ({
  understandProject: vi.fn(),
  understandProjectStream: vi.fn(),
  updateProject: vi.fn(),
  generateOutlineStream: vi.fn(),
  uploadTemplate: vi.fn(),
  show: vi.fn(),
}));

vi.mock('@/api/endpoints', async () => {
  const actual = await vi.importActual<any>('@/api/endpoints');
  return {
    ...actual,
    understandProject: mocks.understandProject,
    understandProjectStream: mocks.understandProjectStream,
    updateProject: mocks.updateProject,
    generateOutlineStream: mocks.generateOutlineStream,
    uploadTemplate: mocks.uploadTemplate,
    uploadReferenceFile: vi.fn(),
    triggerFileParse: vi.fn(),
    getReferenceFile: vi.fn(),
  };
});

vi.mock('@/components/shared', () => ({
  Button: ({ children, icon, loading: _loading, variant: _variant, size: _size, ...props }: any) => <button {...props}>{icon}{children}</button>,
  useToast: () => ({ show: mocks.show, ToastContainer: () => null }),
}));

vi.mock('@/components/shared/TemplateSelector', () => ({
  TemplateSelector: ({ onSelect, selectedPresetTemplateId }: any) => (
    <div>
      <button type="button" onClick={() => onSelect(null, '1')}>预设模板</button>
      <span>{selectedPresetTemplateId ? '已选择' : '未选择'}</span>
    </div>
  ),
}));

vi.mock('@/components/shared/TextStyleSelector', () => ({
  TextStyleSelector: ({ value, onChange }: any) => (
    <textarea
      aria-label="文字风格说明"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

const responseSpec = {
  competition_context: {
    competition_name: '世界职业院校技能大赛/争夺赛',
    generation_goal: '1小时现场技能展示作战稿',
    presentation_mode: '现场展示',
    audience: ['评委'],
  },
  source_material: { raw_text: '', file_id: null, filename: null },
  project_positioning: {
    project_name: '智慧养老守护系统',
    subtitle: '',
    track: '人工智能',
    industry: '',
    real_scene: '养老院护理站',
    service_object: '老人和护理员',
    final_deliverable: '评估系统和记录表',
    one_sentence_intro: '',
  },
  problem_definition: {
    pain_points: ['跌倒风险高'],
    need_source: '',
    current_method: '',
    problem_consequences: '',
    project_goal: '现场完成评估和复核',
  },
  team_roles: ['A', 'B', 'C', 'D'].map((member) => ({
    member,
    name: '',
    role: '角色',
    responsibility: '负责内容',
    onsite_action: '现场动作',
    related_skill_modules: [],
  })),
  skill_modules: [
    {
      skill_name: '风险评估',
      responsible_role: 'A',
      work_task: '',
      verification_method: '记录表',
      onsite_demo_action: '现场评估',
      expected_evidence: '',
      tools_or_equipment: '',
    },
  ],
  result_validation: {
    deliverables: ['评估表'],
    evidence_materials: ['测试记录'],
    test_data: '',
    before_after_comparison: '',
    user_feedback: '',
    quality_evaluation: '',
  },
  value_innovation: {
    practical_value: '可用于养老照护实训',
    innovation_points: [],
    teaching_value: '',
    vocational_scene_value: '',
    sustainability: '',
  },
  constraints: { avoid: [], must_show: [] },
};

const responseData = (
  spec: any,
  inputMode: 'raw_text' | 'structured_input' | 'patch' = 'raw_text',
  overrides: Record<string, any> = {},
) => ({
  project_id: 'project-1',
  generation_mode: 'precise',
  input_mode: inputMode,
  project_title: '智慧养老守护系统',
  competition_project_spec: spec,
  missing_fields: [],
  risk_flags: [],
  confidence: { project_positioning: 1 },
  input_quality: 'ready',
  next_action: 'edit_structured_spec',
  ops: inputMode === 'raw_text'
    ? [{ type: 'set', block_id: 'project_positioning', path: 'project_positioning.project_name', value: '智慧养老守护系统', source: 'ai' }]
    : [],
  rejected_ops: [],
  ...overrides,
});

describe('PptEditor precise generation', () => {
  beforeEach(() => {
    mocks.understandProject.mockReset();
    mocks.understandProjectStream.mockReset();
    mocks.updateProject.mockReset();
    mocks.generateOutlineStream.mockReset();
    mocks.uploadTemplate.mockReset();
    mocks.show.mockReset();
    mocks.updateProject.mockResolvedValue({ success: true, data: {} });
    mocks.uploadTemplate.mockResolvedValue({ success: true, data: {} });
    window.localStorage.clear();
  });

  it('renders the dialogue co-creation workbench and confirmation actions', () => {
    render(<PptEditor />, { wrapper: MemoryRouter });

    expect(screen.getByRole('heading', { name: '大赛文档对话共创' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '共创流程' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '对话共创' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '实时稿件编辑板' })).toBeInTheDocument();
    expect(screen.getByText(/AI 和手工编辑都通过字段补丁更新/)).toBeInTheDocument();
    expect(screen.getByText(/结构化字段已同步/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '大赛展示项目稿件' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: /技能模块/ })).toHaveLength(4);
    fireEvent.click(screen.getByRole('button', { name: '关闭实时稿件编辑板' }));
    expect(screen.queryByRole('heading', { name: '实时稿件编辑板' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '展开稿件板' }));
    expect(screen.getByRole('heading', { name: '实时稿件编辑板' })).toBeInTheDocument();
    expect(screen.getByText(/把项目想法、基础资料或修改意见发给我/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/输入项目资料或修改意见/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '复制模板' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '全屏写提示词' })).toBeInTheDocument();
    expect(screen.queryByText('PPT 风格')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认稿子' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '生成 PPT 大纲' })).toBeDisabled();
  });

  it('opens and exits the fullscreen prompt editor while preserving input', () => {
    render(<PptEditor />, { wrapper: MemoryRouter });

    fireEvent.change(screen.getByPlaceholderText(/输入项目资料或修改意见/), {
      target: { value: '补充应用价值和创新点' },
    });
    fireEvent.click(screen.getByRole('button', { name: '全屏写提示词' }));

    const dialog = screen.getByRole('dialog', { name: '全屏写提示词' });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByDisplayValue('补充应用价值和创新点')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    expect(screen.queryByRole('dialog', { name: '全屏写提示词' })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(/输入项目资料或修改意见/)).toHaveValue('补充应用价值和创新点');
  });

  it('sends dialogue input to the precise understanding API and updates the preview', async () => {
    mocks.understandProjectStream.mockImplementation(async (_data, callbacks) => {
      callbacks.onStatus?.('正在理解本轮输入');
      callbacks.onDraft(responseData(responseSpec));
      callbacks.onDelta('已更新《智慧养老守护系统》的结构化稿件。');
      callbacks.onDone?.({ project_id: 'project-1' });
    });

    render(<PptEditor />, { wrapper: MemoryRouter });

    fireEvent.change(screen.getByPlaceholderText(/输入项目资料或修改意见/), {
      target: { value: '项目名称：智慧养老守护系统\n真实场景：养老院护理站' },
    });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    await waitFor(() => {
      expect(mocks.understandProjectStream).toHaveBeenCalledWith(expect.objectContaining({
        generation_mode: 'precise',
        input_mode: 'raw_text',
        raw_text: '项目名称：智慧养老守护系统\n真实场景：养老院护理站',
      }), expect.any(Object));
    });

    expect(await screen.findByDisplayValue('智慧养老守护系统')).toBeInTheDocument();
    expect(screen.getByText(/已更新《智慧养老守护系统》的结构化稿件/)).toBeInTheDocument();
    expect(screen.getByLabelText('赛道/专业方向')).toHaveValue('人工智能');
    expect(screen.getByLabelText('真实场景')).toHaveValue('养老院护理站');
    expect(screen.getByRole('button', { name: '确认稿子' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: '生成 PPT 大纲' })).toBeDisabled();
  });

  it('does not update the preview when AI returns no accepted ops and shows patch reason', async () => {
    mocks.understandProjectStream.mockImplementation(async (_data, callbacks) => {
      callbacks.onDraft(responseData(responseSpec, 'raw_text', {
        reply: '已补全内容。',
        ops: [],
        rejected_ops: [
          {
            op: { type: 'set', path: 'project_positioning.project_name' },
            code: 'FIELD_LOCKED',
            message: '该字段已锁定：project_positioning.project_name',
          },
        ],
      }));
      callbacks.onDelta('已补全内容。');
      callbacks.onDone?.({ project_id: 'project-1' });
    });

    render(<PptEditor />, { wrapper: MemoryRouter });

    fireEvent.change(screen.getByPlaceholderText(/输入项目资料或修改意见/), {
      target: { value: '请补全项目名称' },
    });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    expect(await screen.findByText('已补全内容。')).toBeInTheDocument();
    expect(await screen.findByText('本轮 AI 未产生字段修改', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('以下字段未能更新：项目名称 — 该字段已锁定：project_positioning.project_name', { exact: false })).toBeInTheDocument();
    expect(screen.queryByDisplayValue('智慧养老守护系统')).not.toBeInTheDocument();
  });

  it('patches a right-side field, locks it, and can unlock it', async () => {
    const lockedSpec = normalizeSpec(responseSpec);
    lockedSpec.project_positioning.project_name.value = '手动项目';
    lockedSpec.project_positioning.project_name.state = 'locked';
    lockedSpec.project_positioning.project_name.last_modified_by = 'user';

    render(<PptEditor />, { wrapper: MemoryRouter });

    mocks.understandProject.mockResolvedValueOnce({
      success: true,
      data: responseData(lockedSpec, 'patch'),
    });

    fireEvent.change(screen.getByLabelText('项目名称'), {
      target: { value: '手动项目' },
    });
    fireEvent.blur(screen.getByLabelText('项目名称'));

    await waitFor(() => {
      expect(mocks.understandProject).toHaveBeenCalledWith(expect.objectContaining({
        input_mode: 'patch',
        patch_ops: [expect.objectContaining({
          type: 'set',
          path: 'project_positioning.project_name',
          value: '手动项目',
          source: 'user',
        })],
      }));
    });

    expect(await screen.findByRole('button', { name: '解锁项目名称' })).toBeInTheDocument();

    const unlockedSpec = normalizeSpec(lockedSpec);
    unlockedSpec.project_positioning.project_name.state = 'soft';
    mocks.understandProject.mockResolvedValueOnce({
      success: true,
      data: responseData(unlockedSpec, 'structured_input'),
    });
    fireEvent.click(screen.getByRole('button', { name: '解锁项目名称' }));

    await waitFor(() => {
      expect(mocks.understandProject).toHaveBeenCalledWith(expect.objectContaining({
        input_mode: 'structured_input',
      }));
    });
    expect(screen.queryByRole('button', { name: '解锁项目名称' })).not.toBeInTheDocument();
  });

  it('restores the live draft board to the default template', async () => {
    mocks.understandProjectStream.mockImplementation(async (_data, callbacks) => {
      callbacks.onDraft(responseData(responseSpec));
      callbacks.onDone?.({ project_id: 'project-1' });
    });

    render(<PptEditor />, { wrapper: MemoryRouter });

    fireEvent.change(screen.getByPlaceholderText(/输入项目资料或修改意见/), {
      target: { value: '项目名称：智慧养老守护系统' },
    });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    expect(await screen.findByDisplayValue('智慧养老守护系统')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认稿子' })).not.toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: '恢复默认' }));

    expect(screen.getByLabelText('项目名称')).toHaveValue('');
    expect(screen.queryByDisplayValue('智慧养老守护系统')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认稿子' })).toBeDisabled();
    expect(screen.getByText(/结构化字段已同步/)).toBeInTheDocument();
    expect(window.localStorage.getItem('banana-ppt-editor-precise-draft')).toBeNull();
    expect(mocks.show).toHaveBeenCalledWith({ type: 'info', message: '已恢复默认稿件模板' });
  });

  it('confirms the draft before generating an outline', async () => {
    mocks.understandProject.mockResolvedValue({
      success: true,
      data: {
        ...responseData(responseSpec, 'structured_input'),
      },
    });
    mocks.understandProjectStream.mockImplementation(async (_data, callbacks) => {
      callbacks.onDraft(responseData(responseSpec));
      callbacks.onDelta('已更新《智慧养老守护系统》的结构化稿件。');
      callbacks.onDone?.({ project_id: 'project-1' });
    });
    mocks.updateProject.mockResolvedValue({ success: true, data: {} });
    mocks.generateOutlineStream.mockImplementation(async (_projectId, callbacks) => {
      callbacks.onPage({ index: 0, title: '封面', points: ['项目名称'] });
      callbacks.onDone({ total: 1, pages: [] });
    });

    render(<PptEditor />, { wrapper: MemoryRouter });

    fireEvent.change(screen.getByPlaceholderText(/输入项目资料或修改意见/), {
      target: { value: '项目名称：智慧养老守护系统\n真实场景：养老院护理站' },
    });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    await screen.findByDisplayValue('智慧养老守护系统');
    fireEvent.click(screen.getByRole('button', { name: '确认稿子' }));

    await waitFor(() => {
      expect(mocks.understandProject).toHaveBeenCalledWith(expect.objectContaining({
        generation_mode: 'precise',
        input_mode: 'structured_input',
      }));
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '生成 PPT 大纲' })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole('button', { name: '生成 PPT 大纲' }));

    await waitFor(() => {
      expect(mocks.generateOutlineStream).toHaveBeenCalledWith('project-1', expect.any(Object));
    });
  });
});
