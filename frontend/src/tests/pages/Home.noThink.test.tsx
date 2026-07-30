import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Home } from '@/pages/Home';

const mocks = vi.hoisted(() => ({
  initializeProject: vi.fn(),
  show: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: {
      language: 'zh',
      changeLanguage: vi.fn(),
    },
  }),
}));

vi.mock('@/hooks/useT', () => ({
  useT: () => (key: string) => {
    const values: Record<string, string> = {
      'nav.materialGenerate': '素材生成',
      'nav.materialCenter': '素材中心',
      'nav.preciseGenerate': '精准生成',
      'nav.history': '历史项目',
      'nav.settings': '设置',
      'settings.language.label': '界面语言',
      'settings.theme.label': '主题模式',
      'settings.theme.light': '浅色',
      'settings.theme.dark': '深色',
      'settings.theme.system': '跟随系统',
      'home.title': '启发',
      'home.subtitle': 'Vibe your slides like vibe coding',
      'home.tagline': '基于 nano banana pro 的原生 AI PPT 生成器',
      'home.features.oneClick': '一句话生成 PPT',
      'home.features.naturalEdit': '自然语言修改',
      'home.features.regionEdit': '指定区域编辑',
      'home.features.export': '一键导出 PPTX/PDF',
      'home.tabs.no_think': '快速开始',
      'home.tabs.idea': '一句话生成',
      'home.tabs.outline': '从内容生成 PPT',
      'home.tabs.description': '从描述生成',
      'home.tabs.ppt_renovation': 'PPT 翻新',
      'home.tabs.ppt_to_ppt': '借鉴优秀 PPT 生成',
      'home.tabDescriptions.no_think': '简单说说你的项目，AI 会先理解项目，再生成争夺赛 PPT 初稿',
      'home.tabDescriptions.idea': '输入你的想法，AI 将为你生成完整的 PPT',
      'home.tabDescriptions.outline': '已有大纲？直接粘贴，逐页描述可选填写，也可以稍后由 AI 生成',
      'home.tabDescriptions.description': '已有完整描述？AI 将自动解析并直接生成图片，跳过大纲步骤',
      'home.tabDescriptions.ppt_renovation': '上传已有的 PDF/PPTX 文件，AI 将解析内容并重新生成翻新后的PPT',
      'home.tabDescriptions.ppt_to_ppt': '上传参考 PPT，再输入你的内容，AI 学习结构和表达方式生成新 PPT',
      'home.placeholders.no_think': '例如：我们做一个智慧养老项目，场景是养老院，解决老人跌倒风险，四个学生分别负责评估、护理、记录和成果展示。',
      'home.placeholders.idea': '例如：生成一份关于 AI 发展史的演讲 PPT',
      'home.placeholders.outline': '粘贴你的 PPT 大纲（必填）...',
      'home.placeholders.description': '粘贴你的完整页面描述...',
      'home.placeholders.ppt_to_ppt': '粘贴你的项目内容、工作材料或比赛说明...',
      'home.content.descriptionLabel': '逐页描述（选填）',
      'home.content.descriptionPlaceholder': '如果你已经有每页内容、布局、图表或素材说明，可以直接填到这里',
      'home.content.descriptionHint': '逐页描述用于补充每页内容、布局、图表和素材说明；全局视觉风格由上方风格模板控制。',
      'home.content.emptyOutlineTip': '还没有大纲？可以使用 NoThinkPPT 先生成完整结构',
      'home.content.generateDescriptions': '根据大纲生成逐页描述',
      'home.examples.outline': '大纲示例',
      'home.examples.description': '描述示例',
      'home.noThink.title': '场景定位',
      'home.noThink.subtitle': '固定绑定世界职业院校技能大赛/争夺赛主线，把项目任务、岗位现场和服务对象转成现场展示语义。',
      'home.noThink.projectDescription': '项目想法',
      'home.noThink.projectName': '项目名称',
      'home.noThink.projectNamePlaceholder': '可不填',
      'home.noThink.industryOrTrack': '赛道 / 专业方向',
      'home.noThink.realScene': '真实场景',
      'home.noThink.realScenePlaceholder': '养老院、温室大棚、数控车间...',
      'home.noThink.targetUser': '服务对象',
      'home.noThink.targetUserPlaceholder': '老人、种植户、设备操作员、游客...',
      'home.noThink.teamTaskDescription': '四名选手分工',
      'home.noThink.teamTaskPlaceholder': '可用自然语言描述，不要求结构化。',
      'home.template.title': '选择风格模板',
      'home.template.useTextStyle': '使用文字描述风格',
      'home.actions.selectFile': '选择参考文件',
      'home.actions.parsing': '解析中...',
      'home.pptToPpt.uploadHint': '点击或拖拽上传参考 PDF / PPTX 文件',
      'home.pptToPpt.formatHint': '参考文件用于学习结构、版式和表达方式',
      'home.pptToPpt.styleSource': '生成风格',
      'home.pptToPpt.reuseReferenceStyle': '复用参考 PPT 风格',
      'home.pptToPpt.chooseStyleTemplate': '选择风格模板',
      'common.next': '下一步',
    };
    return values[key] || key;
  },
}));

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({
    theme: 'light',
    isDark: false,
    setTheme: vi.fn(),
  }),
}));

vi.mock('@/store/useProjectStore', () => ({
  useProjectStore: () => ({
    initializeProject: mocks.initializeProject,
    isGlobalLoading: false,
  }),
}));

vi.mock('@/platform', () => ({
  usePlatform: () => ({
    competition: {
      id: 'wvcc',
      name: '世界职业院校技能大赛',
      shortName: '世职赛',
      supportLevel: 'FULL',
      enabled: true,
      competitionTypes: [],
      tracks: [],
      themes: [],
      recommendedPageCount: 39,
      scoreDimensions: [],
    },
    projectContext: {
      projectName: '',
      competitionId: 'wvcc',
      targetPageCount: 39,
      style: '科技蓝',
      activeScoreDimensionIds: [],
    },
    updateProjectContext: vi.fn(),
  }),
}));

vi.mock('@/api/endpoints', () => ({
  listUserTemplates: vi.fn().mockResolvedValue({ data: {} }),
  uploadReferenceFile: vi.fn(),
  associateFileToProject: vi.fn(),
  triggerFileParse: vi.fn(),
  associateMaterialsToProject: vi.fn(),
  createPptRenovationProject: vi.fn(),
  createPptToPptProject: vi.fn(),
  persistPlatformContext: vi.fn(),
}));

vi.mock('@/components/shared/MarkdownTextarea', () => ({
  MarkdownTextarea: React.forwardRef((props: any, _ref) => (
    <div>
      <textarea
        placeholder={props.placeholder}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      />
      {props.toolbarLeft}
      {props.toolbarRight}
    </div>
  )),
}));

vi.mock('@/components/shared/TemplateSelector', () => ({
  TemplateSelector: () => <div data-testid="template-selector" />,
  getTemplateFile: vi.fn(),
}));

vi.mock('@/components/shared', () => ({
  Button: ({ children, icon, loading: _loading, variant: _variant, size: _size, ...props }: any) => <button {...props}>{icon}{children}</button>,
  Card: ({ children, className }: any) => <section className={className}>{children}</section>,
  useToast: () => ({ show: mocks.show, ToastContainer: () => null }),
  MaterialGeneratorModal: () => null,
  MaterialCenterModal: () => null,
  MaterialSelector: () => null,
  ReferenceFileList: () => null,
  ReferenceFileSelector: () => null,
  FilePreviewModal: () => null,
  Footer: () => null,
  GithubRepoCard: () => null,
  TextStyleSelector: () => null,
}));

describe('Home no-think mode', () => {
  beforeEach(() => {
    mocks.initializeProject.mockReset();
    mocks.show.mockReset();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('shows the vocational quick-start workbench and scenario fields by default', async () => {
    render(<Home />);

    expect(screen.getByRole('button', { name: '快速开始' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '启发 · 职业教育版' })).toBeInTheDocument();
    expect(screen.getByText('项目想法')).toBeInTheDocument();
    expect(screen.getByText('场景定位')).toBeInTheDocument();
    expect(screen.getByText('项目名称')).toBeInTheDocument();
    expect(screen.getByText('赛道 / 专业方向')).toBeInTheDocument();
    expect(screen.getByText('真实场景')).toBeInTheDocument();
    expect(screen.getByText('服务对象')).toBeInTheDocument();
    expect(screen.getByText('四名选手分工')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下一步' })).toBeInTheDocument();
  });

  it('does not render the header help entry', () => {
    render(<Home />);

    expect(screen.queryByRole('button', { name: '帮助' })).not.toBeInTheDocument();
  });

  it('shows the precise generation entry in the home header', () => {
    render(<Home />);

    expect(screen.getByRole('button', { name: '精准生成' })).toBeInTheDocument();
  });

  it('keeps focused top-level entries and includes PPT to PPT as its own mode', () => {
    render(<Home />);

    expect(screen.getByRole('button', { name: '快速开始' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '从内容生成 PPT' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '借鉴优秀 PPT 生成' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'PPT 翻新' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '一句话生成' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '从描述生成' })).not.toBeInTheDocument();
  });

  it('shows the PPT to PPT reference upload and user content input', () => {
    render(<Home />);

    fireEvent.click(screen.getByRole('button', { name: '借鉴优秀 PPT 生成' }));

    expect(screen.getByText('点击或拖拽上传参考 PDF / PPTX 文件')).toBeInTheDocument();
    expect(screen.getByText('参考文件用于学习结构、版式和表达方式')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('粘贴你的项目内容、工作材料或比赛说明...')).toBeInTheDocument();
  });

  it('lets PPT to PPT choose between reference style and a style template', () => {
    render(<Home />);

    fireEvent.click(screen.getByRole('button', { name: '借鉴优秀 PPT 生成' }));

    expect(screen.getByText('生成风格')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '复用参考 PPT 风格' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '选择风格模板' })).toBeInTheDocument();
    expect(screen.queryByTestId('template-selector')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '选择风格模板' }));

    expect(screen.getByTestId('template-selector')).toBeInTheDocument();
  });

  it('requires an outline in content generation and shows the NoThink empty-state hint', () => {
    render(<Home />);

    fireEvent.click(screen.getByRole('button', { name: '从内容生成 PPT' }));
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    expect(mocks.show).toHaveBeenCalledWith({
      message: '还没有大纲？可以使用 NoThinkPPT 先生成完整结构',
      type: 'error',
    });
    expect(mocks.initializeProject).not.toHaveBeenCalled();
  });

  it('shows optional page descriptions for content generation', () => {
    render(<Home />);

    fireEvent.click(screen.getByRole('button', { name: '从内容生成 PPT' }));

    expect(screen.getByText('逐页描述（选填）')).toBeInTheDocument();
    expect(screen.getByText('逐页描述用于补充每页内容、布局、图表和素材说明；全局视觉风格由上方风格模板控制。')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('如果你已经有每页内容、布局、图表或素材说明，可以直接填到这里')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '根据大纲生成逐页描述' })).toBeInTheDocument();
  });
});
