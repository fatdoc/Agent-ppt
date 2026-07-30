import type {
  CompetitionConfig,
  CompetitionSupportLevel,
} from './types';

export const WVCC_SCORE_DIMENSIONS = [
  { id: 'skill-level', name: '技能水平', description: '操作规范、工具熟练、任务完整与技术难度', weight: 60 },
  { id: 'professionalism', name: '职业素养', description: '行业规范、知识产权、数据与设备安全', weight: 10 },
  { id: 'application-value', name: '应用价值', description: '真实场景、降本增效、绿色低碳与推广价值', weight: 10 },
  { id: 'teamwork', name: '团队合作', description: '上下游交付、协同确认、联调验收与异常处置', weight: 10 },
  { id: 'innovation', name: '创新创意', description: '技术、流程、产品和服务创新', weight: 10 },
] as const;

export const COMPETITIONS: CompetitionConfig[] = [
  {
    id: 'wvcc',
    name: '世界职业院校技能大赛',
    shortName: '世职赛',
    supportLevel: 'FULL',
    enabled: true,
    competitionTypes: [
      { id: 'championship', name: '争夺赛' },
      { id: 'ranking', name: '排位赛' },
      { id: 'custom', name: '自定义' },
    ],
    tracks: [
      { id: 'electronic-information', name: '电子信息' },
      { id: 'equipment-manufacturing', name: '装备制造' },
      { id: 'agriculture', name: '农林牧渔' },
      { id: 'healthcare', name: '医药卫生' },
      { id: 'eldercare', name: '康养服务' },
      { id: 'modern-agriculture', name: '现代农业' },
      { id: 'ai-application', name: '人工智能应用' },
      { id: 'other', name: '其他' },
    ],
    themes: [
      { id: 'smart-manufacturing', name: '智能制造与产业升级' },
      { id: 'smart-agriculture', name: '智慧农业与乡村振兴' },
      { id: 'smart-eldercare', name: '智慧养老与健康服务' },
      { id: 'ai-industry', name: '人工智能赋能产业应用' },
      { id: 'custom', name: '自定义主题' },
    ],
    scoreDimensions: [...WVCC_SCORE_DIMENSIONS],
    recommendedPageCount: 39,
    promptProfileId: 'wvcc-v1',
    narrationProfileId: 'wvcc-39-page-v1',
    outlineTemplateIds: ['wvcc-championship-39'],
    pptTemplateIds: [],
    caseLibraryId: 'wvcc',
  },
  {
    id: 'challenge-cup',
    name: '挑战杯',
    shortName: '挑战杯',
    supportLevel: 'GENERIC',
    enabled: true,
    competitionTypes: [{ id: 'custom', name: '自定义' }],
    tracks: [{ id: 'custom', name: '自定义赛道' }],
    themes: [{ id: 'custom', name: '自定义主题' }],
    recommendedPageCount: 20,
    unsupportedMessage: '当前赛事暂未配置专属规则与案例，将使用通用PPT生成模式。',
  },
  {
    id: 'innovation-competition',
    name: '中国国际大学生创新大赛',
    shortName: '创新大赛',
    supportLevel: 'GENERIC',
    enabled: true,
    competitionTypes: [{ id: 'custom', name: '自定义' }],
    tracks: [{ id: 'custom', name: '自定义赛道' }],
    themes: [{ id: 'custom', name: '自定义主题' }],
    recommendedPageCount: 20,
    unsupportedMessage: '当前赛事暂未配置专属规则与案例，将使用通用PPT生成模式。',
  },
  {
    id: 'career-planning',
    name: '全国大学生职业规划大赛',
    shortName: '职业规划大赛',
    supportLevel: 'COMING_SOON',
    enabled: true,
    competitionTypes: [],
    tracks: [],
    themes: [],
    unsupportedMessage: '正在建设专属能力，暂不能进入正式生成流程。',
  },
  {
    id: 'teaching-ability',
    name: '职业院校技能大赛教学能力比赛',
    shortName: '教学能力比赛',
    supportLevel: 'COMING_SOON',
    enabled: true,
    competitionTypes: [],
    tracks: [],
    themes: [],
    unsupportedMessage: '正在建设专属能力，暂不能进入正式生成流程。',
  },
  {
    id: 'custom',
    name: '自定义赛事',
    shortName: '自定义赛事',
    supportLevel: 'GENERIC',
    enabled: true,
    competitionTypes: [{ id: 'custom', name: '自定义' }],
    tracks: [{ id: 'custom', name: '自定义赛道' }],
    themes: [{ id: 'custom', name: '自定义主题' }],
    recommendedPageCount: 15,
    unsupportedMessage: '自定义赛事使用通用PPT能力，不启用专属规则、评分或案例。',
  },
];

export const enabledCompetitions = () => COMPETITIONS.filter((item) => item.enabled);

export const getCompetitionConfig = (competitionId?: string) =>
  COMPETITIONS.find((item) => item.id === competitionId) ?? COMPETITIONS[0];

export const supportLevelLabel: Record<CompetitionSupportLevel, string> = {
  FULL: '完整支持',
  GENERIC: '通用支持',
  COMING_SOON: '专属能力建设中',
};

export const canStartCompetitionWorkflow = (competitionId?: string) =>
  getCompetitionConfig(competitionId).supportLevel !== 'COMING_SOON';
