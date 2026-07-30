import type { AgentWorkflow, CompetitionSupportLevel } from './types';

export const AGENT_WORKFLOWS: AgentWorkflow[] = [
  {
    id: 'full-ppt-production',
    name: '完整 PPT 生产准备',
    description: '按固定步骤分析项目、读取材料、生成大纲、检查评分、匹配视觉资源并生成讲解稿。',
    supportedLevels: ['FULL'],
    steps: [
      { id: 'project-plan', employeeId: 'chief-planner', taskType: 'GET_PROJECT', label: '读取项目与赛事上下文' },
      { id: 'material-analysis', employeeId: 'content-analyst', taskType: 'LIST_REFERENCE_FILES', label: '分析项目材料完整性' },
      { id: 'outline-generation', employeeId: 'outline-architect', taskType: 'GENERATE_OUTLINE', label: '生成赛事大纲' },
      { id: 'score-inspection', employeeId: 'score-inspector', taskType: 'INSPECT_SCORE_COVERAGE', label: '检查五项评分覆盖' },
      { id: 'visual-match', employeeId: 'visual-designer', taskType: 'LIST_STYLE_TEMPLATES', label: '匹配可用视觉模板' },
      { id: 'asset-audit', employeeId: 'asset-creator', taskType: 'LIST_MATERIALS', label: '检查项目素材' },
      { id: 'narration-generation', employeeId: 'speechwriter', taskType: 'GENERATE_NARRATIONS', label: '生成逐页讲解稿' },
      { id: 'delivery-check', employeeId: 'delivery-engineer', taskType: 'DELIVERY_CHECK', label: '检查交付准备状态' },
    ],
  },
  {
    id: 'generic-ppt-production',
    name: '通用 PPT 生产准备',
    description: '使用平台通用能力完成材料读取、大纲、视觉资源、素材和交付检查，不启用赛事专属评分。',
    supportedLevels: ['GENERIC'],
    steps: [
      { id: 'project-plan', employeeId: 'chief-planner', taskType: 'GET_PROJECT', label: '读取项目上下文' },
      { id: 'material-analysis', employeeId: 'content-analyst', taskType: 'LIST_REFERENCE_FILES', label: '分析项目材料完整性' },
      { id: 'outline-generation', employeeId: 'outline-architect', taskType: 'GENERATE_OUTLINE', label: '生成通用大纲' },
      { id: 'visual-match', employeeId: 'visual-designer', taskType: 'LIST_STYLE_TEMPLATES', label: '读取通用视觉模板' },
      { id: 'asset-audit', employeeId: 'asset-creator', taskType: 'LIST_MATERIALS', label: '检查项目素材' },
      { id: 'delivery-check', employeeId: 'delivery-engineer', taskType: 'DELIVERY_CHECK', label: '检查交付准备状态' },
    ],
  },
];

export const getWorkflowForSupportLevel = (level: CompetitionSupportLevel) =>
  AGENT_WORKFLOWS.find((workflow) => workflow.supportedLevels.includes(level));
