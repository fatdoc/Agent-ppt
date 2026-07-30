import type { DigitalEmployee } from './types';

export const DIGITAL_EMPLOYEES: DigitalEmployee[] = [
  {
    id: 'chief-planner',
    name: '竞赛总策划',
    role: '总控与流程编排',
    description: '理解赛事支持范围，分析项目材料并编排可控的 PPT 生产流程。',
    icon: 'sparkles',
    capabilities: ['赛事判断', '材料分析', '任务拆解', '结果汇总'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'UNDERSTAND_PROJECT', endpoint: '/api/projects/understand' },
      { type: 'GET_PROJECT', endpoint: '/api/projects/:projectId' },
    ],
    enabled: true,
  },
  {
    id: 'outline-architect',
    name: '大纲架构师',
    role: '大纲与页面计划',
    description: '匹配大纲模板、规划章节页数并把评分维度落实到页面。',
    icon: 'list-tree',
    capabilities: ['模板匹配', '生成大纲', '页面规划', '保存模板'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'GENERATE_OUTLINE', endpoint: '/api/projects/:projectId/generate/outline' },
      { type: 'REFINE_OUTLINE', endpoint: '/api/projects/:projectId/refine/outline' },
    ],
    enabled: true,
  },
  {
    id: 'content-analyst',
    name: '内容分析师',
    role: '材料理解与证据提炼',
    description: '从逐字稿和项目材料中提炼背景、痛点、方案、价值与创新证据。',
    icon: 'file-search',
    capabilities: ['材料解析', '痛点提炼', '证据检查', '缺失项识别'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'PARSE_FILE', endpoint: '/api/reference-files/:fileId/parse' },
      { type: 'UNDERSTAND_PROJECT', endpoint: '/api/projects/understand' },
    ],
    enabled: true,
  },
  {
    id: 'visual-designer',
    name: 'PPT视觉设计师',
    role: '模板、版式与视觉一致性',
    description: '推荐视觉模板、调整版式与信息密度，并调用现有页面修改能力。',
    icon: 'palette',
    capabilities: ['模板推荐', '版式选择', '风格统一', '页面重设计'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'LIST_TEMPLATES', endpoint: '/api/user-style-templates' },
      { type: 'EDIT_IMAGE', endpoint: '/api/projects/:projectId/pages/:pageId/edit/image' },
    ],
    enabled: true,
  },
  {
    id: 'asset-creator',
    name: '素材生成师',
    role: '项目相关视觉素材',
    description: '结合赛事、赛道、主题、章节和图片用途生成与处理素材。',
    icon: 'image-plus',
    capabilities: ['AI生图', '图片抠图', '更换背景', '保存素材'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'GENERATE_MATERIAL', endpoint: '/api/projects/:projectId/materials/generate' },
      { type: 'PROCESS_MATERIAL', endpoint: '/api/projects/:projectId/materials/process' },
      { type: 'UPLOAD_MATERIAL', endpoint: '/api/projects/:projectId/materials/upload' },
    ],
    enabled: true,
  },
  {
    id: 'score-inspector',
    name: '评分检查员',
    role: '评分覆盖与整改',
    description: '仅在具备专属评分配置时检查覆盖证据并给出整改建议。',
    icon: 'badge-check',
    capabilities: ['评分覆盖', '证据检查', '缺失页面', '整改建议'],
    supportedCompetitions: ['wvcc'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'REFINE_OUTLINE', endpoint: '/api/projects/:projectId/refine/outline' },
      { type: 'REFINE_DESCRIPTIONS', endpoint: '/api/projects/:projectId/refine/descriptions' },
    ],
    enabled: true,
  },
  {
    id: 'speechwriter',
    name: '演讲稿助手',
    role: '逐页讲解与时长控制',
    description: '根据页面与角色分工生成绑定到具体页面的讲解稿。',
    icon: 'mic-2',
    capabilities: ['逐页讲稿', '时长控制', '衔接优化', '学生口吻'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'GENERATE_NARRATION', endpoint: '/api/projects/:projectId/pages/:pageId/generate/narration' },
      { type: 'GENERATE_NARRATIONS', endpoint: '/api/projects/:projectId/generate/narrations' },
    ],
    enabled: true,
  },
  {
    id: 'delivery-engineer',
    name: '交付工程师',
    role: '质量预检与文件交付',
    description: '检查页面完整性并调用现有 PPTX、PDF、图片和视频导出服务。',
    icon: 'package-check',
    capabilities: ['溢出检查', '图片检查', '页面预检', '多格式导出'],
    invocationMode: 'BOTH',
    serviceMapping: [
      { type: 'EXPORT_PPTX', endpoint: '/api/projects/:projectId/export/pptx' },
      { type: 'EXPORT_EDITABLE_PPTX', endpoint: '/api/projects/:projectId/export/editable-pptx' },
      { type: 'EXPORT_PDF', endpoint: '/api/projects/:projectId/export/pdf' },
    ],
    enabled: true,
  },
];

export const getDigitalEmployeesForCompetition = (competitionId: string) =>
  DIGITAL_EMPLOYEES.filter(
    (employee) =>
      employee.enabled
      && (!employee.supportedCompetitions
        || employee.supportedCompetitions.includes(competitionId)),
  );
