import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, Bot, Check, CheckCircle2, Download, Expand, FileText, Loader2, PanelRightClose, PanelRightOpen, Paperclip, RotateCcw, Send, UserRound, Wand2, X } from 'lucide-react';
import {
  CompetitionProjectSpec,
  RejectedPatchOp,
  UnderstandProjectResponse,
  ReferenceFile,
  generateOutlineStream,
  getProject,
  getReferenceFile,
  triggerFileParse,
  understandProject,
  understandProjectStream,
  uploadReferenceFile,
} from '@/api/endpoints';
import type { PatchOp } from '@/types/patch';
import { SpecEditor } from '@/components/spec-editor/SpecEditor';
import { Button, useToast } from '@/components/shared';
import { createEmptySpec } from '@/utils/initSpec';
import { fieldValue, listValue, normalizeSpec, unlockSpecField } from '@/utils/specState';

type InputMode = 'raw_text' | 'uploaded_file' | 'structured_input';

const preciseDraftStorageKey = 'banana-ppt-editor-precise-draft';

type StoredPreciseDraft = {
  projectId: string;
  spec: CompetitionProjectSpec;
  missingFields?: string[];
  riskFlags?: string[];
  confidence?: Record<string, number>;
  inputQuality?: 'ready' | 'needs_review' | 'insufficient';
  outlineInFlight?: boolean;
  updatedAt: number;
};

const projectMaterialTemplate = `【世界职业院校技能大赛/争夺赛 PPT 精准生成项目资料模板】

一、项目定位
项目名称：
副标题：
赛道/专业方向：
所属专业/课程：
真实场景：
服务对象/使用对象：
最终成果形态：
一句话介绍：

填写提示：
- 真实场景要写具体岗位现场或课程工位，例如护理站、温室大棚、数控车间、营销服务现场。
- 服务对象不要写泛泛人群，尽量写实际用户、企业导师、设备操作员、客户、老人、种植户等。
- 最终成果形态可以是系统、装置、服务流程、记录表、任务清单、评分材料包等。

二、真实问题
需求来源：
当前做法：
痛点1：
痛点2：
痛点3：
问题后果：
项目目标：

填写提示：
- 痛点要来自岗位任务或课程实训，不要只写市场机会。
- 项目目标要能转化为现场展示动作，例如完成评估、检测、调试、干预、记录、复核。

三、四名选手分工
A选手
角色：
负责内容：
现场动作：
关联技能模块：

B选手
角色：
负责内容：
现场动作：
关联技能模块：

C选手
角色：
负责内容：
现场动作：
关联技能模块：

D选手
角色：
负责内容：
现场动作：
关联技能模块：

填写提示：
- 每名选手必须有角色、负责内容、现场动作。
- 现场动作建议写“现场采集/检测/评估/调试/干预/处置/记录/归档/复核”。

四、技能展示模块
技能模块1
技能名称：
负责角色：
工作任务：
现场演示动作：
验证方式：
预期证据：
工具/设备/材料：

技能模块2
技能名称：
负责角色：
工作任务：
现场演示动作：
验证方式：
预期证据：
工具/设备/材料：

技能模块3
技能名称：
负责角色：
工作任务：
现场演示动作：
验证方式：
预期证据：
工具/设备/材料：

技能模块4
技能名称：
负责角色：
工作任务：
现场演示动作：
验证方式：
预期证据：
工具/设备/材料：

填写提示：
- 技能展示必须映射到现场可演示动作，不要只写理论说明。
- 验证方式优先写记录表、评分材料、测试结果、现场比对、操作清单。

五、成果验证
成果清单：
1.
2.
3.

证据材料：
1.
2.
3.

测试数据：
优化前后对比：
用户反馈：
质量评价：

填写提示：
- 成果验证以可核验证据为主，例如记录表、评分材料、演示清单、测试记录、截图、用户反馈。
- 不建议填写没有依据的收益数字或夸张指标。

六、价值创新
实用性：
创新点：
1.
2.
3.

教学应用价值：
职业场景落地价值：
经济性：
可持续性：

填写提示：
- 价值创新强调教学应用价值和职业场景落地价值。
- 不要写融资、商业模式、市场规模、投资回报等营销型内容。

七、现场展示补充
评委需要重点看到什么：
现场展示顺序：
需要避免的表达：
补充材料说明：
`;

const getPptEditorErrorMessage = (error: any, fallback: string) => {
  const apiError = error?.response?.data?.error;
  const message = apiError?.message || error?.message || '';
  const code = apiError?.code || '';

  if (
    code === 'AI_SERVICE_AUTH_ERROR'
    || /invalid api key/i.test(message)
    || /incorrect api key/i.test(message)
    || /401/.test(message)
  ) {
    return 'AI 服务密钥无效或已过期。请先到设置页更新模型 API Key，或修改 .env 后重启后端。';
  }

  return message || fallback;
};

const apiErrorText = (error: string | undefined, fallback: string) => error || fallback;

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const shouldAnimateAssistantStream = import.meta.env.MODE !== 'test';

const readStoredPreciseDraft = (): StoredPreciseDraft | null => {
  try {
    const raw = window.localStorage.getItem(preciseDraftStorageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredPreciseDraft;
    if (!parsed.projectId || !parsed.spec || !parsed.updatedAt) return null;
    return parsed;
  } catch {
    return null;
  }
};

const writeStoredPreciseDraft = (draft: StoredPreciseDraft) => {
  window.localStorage.setItem(preciseDraftStorageKey, JSON.stringify(draft));
};

const clearStoredPreciseDraft = () => {
  window.localStorage.removeItem(preciseDraftStorageKey);
};

const outlineReadyStatuses = new Set(['OUTLINE_GENERATED', 'DESCRIPTIONS_GENERATED', 'COMPLETED']);

const emptySpec = createEmptySpec;

const isPollutedDraftText = (value?: string | null) => {
  const text = value?.trim() || '';
  if (!text) return false;
  if (text === '待补充' || text === '无' || text === '暂无') return true;
  if (text.startsWith('#')) return true;
  if (text.includes('【当前用户手动修订后的 Markdown 稿件】') || text.includes('【用户本轮修改意见或新增资料】')) return true;
  const fieldLabelCount = (text.match(/(项目名称|副标题|赛道|专业方向|真实场景|服务对象|最终成果形态|一句话介绍|痛点|技能模块|成果清单|证据材料)[：:]/g) || []).length;
  if (fieldLabelCount >= 2) return true;
  if (/^(我想|我要|计划|准备).{0,20}(做|建设|开发|设计).{0,20}(项目|系统)/.test(text)) return true;
  if (/(我想|我要|计划|准备|打算).{0,40}(方向|起名|取名|项目名称)/.test(text)) return true;
  if (/(帮我|请你|麻烦).{0,30}(起|取|推荐).{0,10}(项目)?名称/.test(text)) return true;
  if (/(项目名称|项目名|名称)(就)?(叫|是|为)/.test(text) || /赛道(是|为)/.test(text)) return true;
  if (/^真实场景(是|为)/.test(text)) return true;
  if (/^(优化前后对比|测试数据|用户反馈|质量评价)/.test(text)) return true;
  return false;
};

const cleanDraftList = (items?: string[]) => (items || [])
  .map((item) => item.trim().replace(/[。；;，,]+$/g, ''))
  .filter((item, index, array) => item && !isPollutedDraftText(item) && array.indexOf(item) === index);

const cleanSpecForDisplay = (rawSpec: CompetitionProjectSpec): CompetitionProjectSpec => {
  const spec = normalizeSpec(rawSpec);
  const positioning = spec.project_positioning;
  (['subtitle', 'real_scene', 'service_object', 'final_deliverable', 'one_sentence_intro'] as const).forEach((field) => {
    if (isPollutedDraftText(positioning[field].value)) positioning[field].value = '';
  });
  if (isPollutedDraftText(positioning.project_name.value)) {
    const match = positioning.project_name.value.match(/项目名称(?:叫|是|为)\s*([^，。；;\n]+)/);
    positioning.project_name.value = match?.[1]?.trim() || '';
  }
  if (isPollutedDraftText(positioning.track.value)) positioning.track.value = '';

  spec.problem_definition.pain_points.value = cleanDraftList(spec.problem_definition.pain_points.value);
  (['need_source', 'current_method', 'problem_consequences', 'project_goal'] as const).forEach((field) => {
    if (isPollutedDraftText(spec.problem_definition[field].value)) spec.problem_definition[field].value = '';
  });

  spec.skill_modules.forEach((module) => {
    (['skill_name', 'responsible_role', 'work_task', 'onsite_demo_action', 'verification_method', 'expected_evidence', 'tools_or_equipment'] as const).forEach((field) => {
      if (isPollutedDraftText(module[field].value)) module[field].value = '';
    });
  });

  spec.result_validation.deliverables.value = cleanDraftList(spec.result_validation.deliverables.value);
  spec.result_validation.evidence_materials.value = cleanDraftList(spec.result_validation.evidence_materials.value);
  (['test_data', 'before_after_comparison', 'user_feedback', 'quality_evaluation'] as const).forEach((field) => {
    if (isPollutedDraftText(spec.result_validation[field].value)) spec.result_validation[field].value = '';
  });

  spec.value_innovation.innovation_points.value = cleanDraftList(spec.value_innovation.innovation_points.value)
    .filter((item) => item !== '记录完整性' && !/交接准确性/.test(item));
  (['practical_value', 'teaching_value', 'vocational_scene_value', 'sustainability'] as const).forEach((field) => {
    if (isPollutedDraftText(spec.value_innovation[field].value)) spec.value_innovation[field].value = '';
  });

  return spec;
};

const fieldLabels: Record<string, string> = {
  'project_positioning.project_name': '项目名称',
  'project_positioning.subtitle': '副标题',
  'project_positioning.track': '赛道/专业方向',
  'project_positioning.track_or_industry': '赛道/专业方向',
  'project_positioning.real_scene': '真实场景',
  'project_positioning.service_object': '服务对象',
  'project_positioning.final_deliverable': '最终成果形态',
  'project_positioning.one_sentence_intro': '一句话介绍',
  'problem_definition.need_source': '需求来源',
  'problem_definition.current_method': '当前做法',
  'problem_definition.pain_points': '至少一个真实痛点',
  'problem_definition.problem_consequences': '问题后果',
  'problem_definition.project_goal': '项目目标',
  skill_modules: '技能展示模块',
  'result_validation.deliverables': '成果清单',
  'result_validation.evidence_materials': '证据材料',
  'result_validation.test_data': '测试数据',
  'result_validation.before_after_comparison': '优化前后对比',
  'result_validation.user_feedback': '用户反馈',
  'result_validation.quality_evaluation': '质量评价',
  'value_innovation.practical_value': '实用性',
  'value_innovation.innovation_points': '创新点',
  'value_innovation.practical_value_or_innovation_points': '实用性或创新点',
  'value_innovation.teaching_value': '教学应用价值',
  'value_innovation.vocational_scene_value': '职业场景落地价值',
  'value_innovation.sustainability': '可持续性',
  'minimum.project_core': '项目名称/一句话介绍/成果形态至少一项',
  'minimum.problem_or_goal': '真实问题或项目目标',
  'minimum.skill_or_team_action': '至少一个团队动作或技能动作',
};

const patchFieldLabel = (path?: unknown) => {
  if (typeof path !== 'string' || !path.trim()) return '未知字段';
  const normalized = path.trim();
  const direct = fieldLabels[normalized];
  if (direct) return direct;

  const teamMatch = normalized.match(/^team_roles\.([A-D])\.(role|responsibility|onsite_action|related_skill_modules)$/);
  if (teamMatch) {
    const labels = {
      role: '角色',
      responsibility: '负责内容',
      onsite_action: '现场动作',
      related_skill_modules: '关联技能模块',
    };
    return `${teamMatch[1]} 选手${labels[teamMatch[2] as keyof typeof labels]}`;
  }

  const skillMatch = normalized.match(/^skill_modules\[(sm_0([1-4]))\]\.(skill_name|responsible_role|work_task|onsite_demo_action|verification_method|expected_evidence|tools_or_equipment)$/);
  if (skillMatch) {
    const labels = {
      skill_name: '技能名称',
      responsible_role: '负责角色',
      work_task: '工作任务',
      onsite_demo_action: '现场演示动作',
      verification_method: '验证方式',
      expected_evidence: '预期证据',
      tools_or_equipment: '工具/设备/材料',
    };
    return `技能模块 ${skillMatch[2]} ${labels[skillMatch[3] as keyof typeof labels]}`;
  }

  return normalized;
};

const patchFailureNote = (rejectedOps?: RejectedPatchOp[]) => {
  const rejected = (rejectedOps || []).filter((item) => item && (item.message || item.code || item.op));
  if (!rejected.length) return '';
  const messages = rejected.map((item) => {
    const path = item.op?.path;
    const reason = item.message || item.code || '服务端拒绝更新';
    return `以下字段未能更新：${patchFieldLabel(path)} — ${reason}`;
  });
  return messages.join('\n');
};

const getAcceptedOps = (response?: UnderstandProjectResponse | null): PatchOp[] => (
  Array.isArray(response?.ops) ? response.ops : []
);

const filled = (value?: string | null) => Boolean(value?.trim());
const teamRoleValues = (spec: CompetitionProjectSpec) => (['A', 'B', 'C', 'D'] as const).map((key) => ({ key, role: spec.team_roles[key] }));

const collectGenerationMissingFields = (spec: CompetitionProjectSpec): string[] => {
  const missing: string[] = [];
  const positioning = spec.project_positioning;
  if (!filled(fieldValue(positioning.project_name))) missing.push('project_positioning.project_name');
  if (!filled(fieldValue(positioning.track))) missing.push('project_positioning.track_or_industry');
  if (!filled(fieldValue(positioning.real_scene))) missing.push('project_positioning.real_scene');
  if (!filled(fieldValue(positioning.service_object))) missing.push('project_positioning.service_object');
  if (!filled(fieldValue(positioning.final_deliverable))) missing.push('project_positioning.final_deliverable');

  const problem = spec.problem_definition;
  if (!listValue(problem.pain_points).some(filled)) missing.push('problem_definition.pain_points');
  if (!filled(fieldValue(problem.project_goal))) missing.push('problem_definition.project_goal');

  teamRoleValues(spec).forEach(({ key, role }) => {
    if (!filled(fieldValue(role.role))) missing.push(`team_roles.${key}.role`);
    if (!filled(fieldValue(role.responsibility))) missing.push(`team_roles.${key}.responsibility`);
    if (!filled(fieldValue(role.onsite_action))) missing.push(`team_roles.${key}.onsite_action`);
  });

  const modules = spec.skill_modules || [];
  if (modules.length !== 4) {
    missing.push('skill_modules');
  }
  modules.forEach((module, index) => {
    const label = index + 1;
    if (!filled(fieldValue(module.skill_name))) missing.push(`skill_modules.${label}.skill_name`);
    if (!filled(fieldValue(module.responsible_role))) missing.push(`skill_modules.${label}.responsible_role`);
    if (!filled(fieldValue(module.verification_method))) missing.push(`skill_modules.${label}.verification_method`);
    if (!filled(fieldValue(module.onsite_demo_action))) missing.push(`skill_modules.${label}.onsite_demo_action`);
  });

  const validation = spec.result_validation;
  if (!listValue(validation.deliverables).some(filled)) missing.push('result_validation.deliverables');
  if (!listValue(validation.evidence_materials).some(filled)) missing.push('result_validation.evidence_materials');

  const value = spec.value_innovation;
  if (!filled(fieldValue(value.practical_value)) && !listValue(value.innovation_points).some(filled)) {
    missing.push('value_innovation.practical_value_or_innovation_points');
  }

  return missing;
};

const collectMinimumGenerationMissingFields = (spec: CompetitionProjectSpec): string[] => {
  const missing: string[] = [];
  const positioning = spec.project_positioning;
  const hasProjectCore = filled(fieldValue(positioning.project_name)) || filled(fieldValue(positioning.one_sentence_intro)) || filled(fieldValue(positioning.final_deliverable));
  if (!hasProjectCore) missing.push('minimum.project_core');
  if (!filled(fieldValue(positioning.real_scene))) missing.push('project_positioning.real_scene');
  if (!filled(fieldValue(positioning.service_object))) missing.push('project_positioning.service_object');

  const problem = spec.problem_definition;
  const hasProblemOrGoal = filled(fieldValue(problem.project_goal)) || listValue(problem.pain_points).some(filled);
  if (!hasProblemOrGoal) missing.push('minimum.problem_or_goal');

  const hasTeamAction = teamRoleValues(spec).some(({ role }) => (
    filled(fieldValue(role.role)) || filled(fieldValue(role.responsibility)) || filled(fieldValue(role.onsite_action))
  ));
  const hasSkillAction = spec.skill_modules?.some((module) =>
    filled(fieldValue(module.skill_name)) || filled(fieldValue(module.work_task)) || filled(fieldValue(module.onsite_demo_action))
  );
  if (!hasTeamAction && !hasSkillAction) missing.push('minimum.skill_or_team_action');

  return missing;
};

const hasAnyStructuredInput = (spec: CompetitionProjectSpec): boolean => {
  return [
    fieldValue(spec.project_positioning.project_name),
    fieldValue(spec.project_positioning.track),
    fieldValue(spec.project_positioning.real_scene),
    fieldValue(spec.project_positioning.service_object),
    fieldValue(spec.project_positioning.final_deliverable),
    fieldValue(spec.project_positioning.one_sentence_intro),
    fieldValue(spec.problem_definition.project_goal),
    fieldValue(spec.value_innovation.practical_value),
    ...listValue(spec.problem_definition.pain_points),
    ...listValue(spec.result_validation.deliverables),
    ...listValue(spec.result_validation.evidence_materials),
    ...listValue(spec.value_innovation.innovation_points),
    ...teamRoleValues(spec).flatMap(({ role }) => [fieldValue(role.role), fieldValue(role.responsibility), fieldValue(role.onsite_action)]),
    ...spec.skill_modules.flatMap((module) => [
      fieldValue(module.skill_name),
      fieldValue(module.responsible_role),
      fieldValue(module.verification_method),
      fieldValue(module.onsite_demo_action),
      fieldValue(module.work_task),
    ]),
  ].some(filled);
};

const qualityLabel = {
  ready: '可进入生成',
  needs_review: '建议补充后生成',
  insufficient: '关键信息不足',
};

const outlineProgressSteps = [
  '正在保存最新理解稿',
  '正在润色争夺赛主线',
  '正在规划四名选手岗位分工',
  '正在拆解技能展示模块',
  '正在分配任务、动作与证据',
  '正在生成 30-42 页 PPT 大纲',
  '正在校验现场演示逻辑',
  '正在整理成果验证与创新页',
];

type ChatMessage = {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  time: string;
  note?: string;
};

type DraftSyncState = 'synced' | 'streaming' | 'editing';

type InitialCoCreateState = {
  initialMessage?: string;
};

const nowLabel = () => {
  return new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
};

const newMessageId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const buildAssistantReply = (data: UnderstandProjectResponse, labels: string[]) => {
  if (data.reply?.trim()) {
    return data.reply.trim();
  }
  const responseSpec = normalizeSpec(data.competition_project_spec);
  const projectName = fieldValue(responseSpec.project_positioning.project_name) || data.project_title || '当前项目';
  const base = `已更新《${projectName}》的结构化稿件。`;
  if (data.input_quality === 'ready' && labels.length === 0) {
    return `${base}目前核心信息完整，可以确认稿子后生成 PPT 大纲。`;
  }
  const nextFields = labels.slice(0, 4).join('、');
  return `${base}${nextFields ? `建议下一轮补充：${nextFields}。` : '可以继续补充团队动作、技能证据或成果验证。'}`;
};

const completionMetrics = (draft: CompetitionProjectSpec) => {
  const sections = [
    collectMinimumGenerationMissingFields(draft).length === 0,
    Boolean(fieldValue(draft.project_positioning.project_name) || fieldValue(draft.project_positioning.one_sentence_intro)),
    Boolean(listValue(draft.problem_definition.pain_points).length || fieldValue(draft.problem_definition.project_goal)),
    teamRoleValues(draft).some(({ role }) => filled(fieldValue(role.role)) && filled(fieldValue(role.onsite_action))),
    draft.skill_modules.some((module) => filled(fieldValue(module.skill_name)) && filled(fieldValue(module.onsite_demo_action))),
    Boolean(listValue(draft.result_validation.deliverables).length || listValue(draft.result_validation.evidence_materials).length),
    Boolean(fieldValue(draft.value_innovation.practical_value) || listValue(draft.value_innovation.innovation_points).length),
  ];
  const done = sections.filter(Boolean).length;
  return {
    done,
    total: sections.length,
    percent: Math.round((done / sections.length) * 100),
  };
};

export const PptEditor: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { show } = useToast();
  const routeState = location.state as InitialCoCreateState | null;
  const [chatInput, setChatInput] = useState(() => routeState?.initialMessage || '');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    {
      id: 'welcome',
      role: 'assistant',
      content: '把项目想法、基础资料或修改意见发给我。我会持续更新右侧结构化稿件；确认稿子后，再生成比赛展示 PPT 大纲。',
      time: nowLabel(),
    },
  ]);
  const [spec, setSpec] = useState<CompetitionProjectSpec>(emptySpec());
  const [projectId, setProjectId] = useState<string | null>(null);
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [riskFlags, setRiskFlags] = useState<string[]>([]);
  const [confidence, setConfidence] = useState<Record<string, number>>({});
  const [inputQuality, setInputQuality] = useState<'ready' | 'needs_review' | 'insufficient'>('insufficient');
  const [draftConfirmed, setDraftConfirmed] = useState(false);
  const [confirmedAt, setConfirmedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [outlineLoading, setOutlineLoading] = useState(false);
  const [outlineProgressIndex, setOutlineProgressIndex] = useState(0);
  const [uploadState, setUploadState] = useState<{ file?: ReferenceFile; status: string }>({ status: '' });
  const [draftSyncState, setDraftSyncState] = useState<DraftSyncState>('synced');
  const [isPreviewPanelOpen, setIsPreviewPanelOpen] = useState(true);
  const [isPromptFullscreenOpen, setIsPromptFullscreenOpen] = useState(false);
  const restoredDraftRef = useRef(false);

  const suggestedMissingFields = useMemo(() => collectGenerationMissingFields(spec), [spec]);
  const minimumMissingFields = useMemo(() => collectMinimumGenerationMissingFields(spec), [spec]);
  const canSaveStructuredDraft = useMemo(() => hasAnyStructuredInput(spec), [spec]);
  const hasParsedOrSavedDraft = Boolean(projectId);
  const canConfirmDraft = canSaveStructuredDraft && hasParsedOrSavedDraft;
  const canGenerateOutline = draftConfirmed && hasParsedOrSavedDraft && canSaveStructuredDraft && minimumMissingFields.length === 0;
  const visibleMissingFields = minimumMissingFields.length > 0 ? minimumMissingFields : suggestedMissingFields.length > 0 ? suggestedMissingFields : missingFields;
  const currentOutlineProgress = outlineProgressSteps[outlineProgressIndex % outlineProgressSteps.length];
  const completion = useMemo(() => completionMetrics(spec), [spec]);
  const lockedFieldCount = useMemo(() => JSON.stringify(spec).match(/"state":"locked"/g)?.length || 0, [spec]);
  const draftSyncMeta = useMemo(() => {
    if (draftSyncState === 'streaming') {
      return { label: '正在输出对话回复', className: 'bg-blue-50 text-blue-700' };
    }
    if (draftSyncState === 'editing') {
      return { label: '正在编辑方案稿', className: 'bg-indigo-50 text-indigo-700' };
    }
    return { label: '结构化字段已同步', className: 'bg-emerald-50 text-emerald-700' };
  }, [draftSyncState]);

  const waitForExistingOutline = async (targetProjectId: string) => {
    setOutlineLoading(true);
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const response = await getProject(targetProjectId);
      const project = response.data;

      if (project?.pages?.length && outlineReadyStatuses.has(project.status)) {
        clearStoredPreciseDraft();
        show({ type: 'success', message: '上次生成的大纲已完成，正在进入编辑页' });
        navigate(`/project/${targetProjectId}/outline`);
        return;
      }

      if (project && project.status !== 'GENERATING_OUTLINE' && attempt > 0) {
        setOutlineLoading(false);
        show({ type: 'info', message: '已恢复上次草稿，可以继续编辑或重新生成大纲' });
        return;
      }

      await new Promise((resolve) => setTimeout(resolve, 3000));
    }

    setOutlineLoading(false);
    show({ type: 'error', message: '等待上次大纲生成超时，请到历史项目查看状态' });
  };

  useEffect(() => {
    if (restoredDraftRef.current) return;
    restoredDraftRef.current = true;

    const stored = readStoredPreciseDraft();
    if (!stored) return;

    const cleanSpec = cleanSpecForDisplay(stored.spec);
    setProjectId(stored.projectId);
    setSpec(cleanSpec);
    setMissingFields(stored.missingFields || []);
    setRiskFlags(stored.riskFlags || []);
    setConfidence(stored.confidence || {});
    setInputQuality(stored.inputQuality || 'needs_review');
    setDraftSyncState('synced');
    if (JSON.stringify(cleanSpec) !== JSON.stringify(stored.spec)) {
      writeStoredPreciseDraft({ ...stored, spec: cleanSpec, updatedAt: Date.now() });
    }

    if (stored.outlineInFlight && Date.now() - stored.updatedAt < 30 * 60 * 1000) {
      show({
        type: 'info',
        message: '已恢复上次精准生成任务，正在等待大纲结果。',
      });
      waitForExistingOutline(stored.projectId);
    }
  }, [show]);

  useEffect(() => {
    if (!outlineLoading) {
      setOutlineProgressIndex(0);
      return undefined;
    }

    const timer = window.setInterval(() => {
      setOutlineProgressIndex((index) => index + 1);
    }, 5500);

    return () => window.clearInterval(timer);
  }, [outlineLoading]);

  useEffect(() => {
    if (!isPromptFullscreenOpen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsPromptFullscreenOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPromptFullscreenOpen]);

  const missingLabels = useMemo(() => {
    return visibleMissingFields.map((field) => {
      const teamMatch = field.match(/^team_roles\.([A-D])\.(role|responsibility|onsite_action)$/);
      if (teamMatch) {
        const labelMap = { role: '角色', responsibility: '负责内容', onsite_action: '现场动作' };
        return `${teamMatch[1]} 选手${labelMap[teamMatch[2] as keyof typeof labelMap]}`;
      }
      const moduleMatch = field.match(/^skill_modules\.(\d+)\.(skill_name|responsible_role|verification_method|onsite_demo_action)$/);
      if (moduleMatch) {
        const labelMap = {
          skill_name: '技能名称',
          responsible_role: '负责角色',
          verification_method: '验证方式',
          onsite_demo_action: '现场演示动作',
        };
        return `技能模块 ${moduleMatch[1]} ${labelMap[moduleMatch[2] as keyof typeof labelMap]}`;
      }
      return fieldLabels[field] || field;
    });
  }, [visibleMissingFields]);

  const applyResponse = (
    responseData: UnderstandProjectResponse,
    options: { keepConfirmation?: boolean } = {},
  ) => {
    const cleanSpec = cleanSpecForDisplay(responseData.competition_project_spec);
    setSpec(cleanSpec);
    setProjectId(responseData.project_id);
    setMissingFields(responseData.missing_fields || []);
    setRiskFlags(responseData.risk_flags || []);
    setConfidence(responseData.confidence || {});
    setInputQuality(responseData.input_quality || 'needs_review');
    setDraftSyncState('synced');
    if (!options.keepConfirmation) {
      setDraftConfirmed(false);
      setConfirmedAt(null);
    }
    writeStoredPreciseDraft({
      projectId: responseData.project_id,
      spec: cleanSpec,
      missingFields: responseData.missing_fields || [],
      riskFlags: responseData.risk_flags || [],
      confidence: responseData.confidence || {},
      inputQuality: responseData.input_quality || 'needs_review',
      updatedAt: Date.now(),
    });
  };

  const downloadProjectMaterialTemplate = () => {
    const blob = new Blob([`\ufeff${projectMaterialTemplate}`], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '世界职业院校技能大赛-精准生成项目资料模板.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const submitUnderstanding = async (mode: InputMode, overrides: Partial<{ raw_text: string; file_id: string }> = {}) => {
    if (mode === 'structured_input' && !canSaveStructuredDraft) {
      show({ type: 'error', message: '请先填写或解析项目资料，再保存理解草稿' });
      return;
    }
    setLoading(true);
    try {
      const response = await understandProject({
        generation_mode: 'precise',
        project_id: projectId || undefined,
        input_mode: mode,
        raw_text: overrides.raw_text,
        file_id: overrides.file_id,
        structured_input: spec,
      });
      if (response.success && response.data) {
        console.log('[AI RAW]', response.data);
        console.log('[PATCH SEND]', getAcceptedOps(response.data));
        console.log('[PATCH RESULT]', response.data);
        if ((mode === 'raw_text' || mode === 'uploaded_file') && getAcceptedOps(response.data).length === 0) {
          show({ type: 'info', message: '本轮 AI 未产生字段修改' });
          return;
        }
        applyResponse(response.data);
        show({ type: 'success', message: '已生成可编辑的竞赛输入草稿' });
      } else {
        show({ type: 'error', message: apiErrorText(response.error, '解析失败') });
      }
    } catch (error: any) {
      show({ type: 'error', message: error?.response?.data?.error?.message || '解析失败' });
    } finally {
      setLoading(false);
    }
  };

  const appendMessage = (message: Omit<ChatMessage, 'id' | 'time'>) => {
    setChatMessages((current) => [
      ...current,
      {
        ...message,
        id: newMessageId(),
        time: nowLabel(),
      },
    ]);
  };

  const handleSendMessage = async () => {
    const trimmed = chatInput.trim();
    if (!trimmed || loading || outlineLoading) return;
    setIsPromptFullscreenOpen(false);

    const userMessage: ChatMessage = {
      id: newMessageId(),
      role: 'user',
      content: trimmed,
      time: nowLabel(),
    };
    const assistantMessageId = newMessageId();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      time: nowLabel(),
    };

    const updateAssistantMessage = (updater: (message: ChatMessage) => ChatMessage) => {
      setChatMessages((current) => current.map((message) => (
        message.id === assistantMessageId
          ? updater(message)
          : message
      )));
    };

    const updateAssistantContent = (updater: (content: string) => string) => {
      updateAssistantMessage((message) => ({ ...message, content: updater(message.content) }));
    };

    const setAssistantNote = (note: string) => {
      updateAssistantMessage((message) => ({ ...message, note }));
    };

    let assistantTypingTask = Promise.resolve();
    const streamAssistantText = (text: string) => {
      if (!shouldAnimateAssistantStream) {
        updateAssistantContent((content) => `${content}${text}`);
        return assistantTypingTask;
      }
      assistantTypingTask = assistantTypingTask.then(async () => {
        for (const char of text) {
          updateAssistantContent((content) => `${content}${char}`);
          await wait(char.trim() ? 18 : 6);
        }
      });
      return assistantTypingTask;
    };

    setChatMessages((current) => [...current, userMessage, assistantMessage]);
    setChatInput('');
    setLoading(true);
    setDraftSyncState('streaming');
    setStreamStatus('正在理解本轮输入');

    try {
      let draftResponse: UnderstandProjectResponse | null = null;
      let receivedDelta = false;
      let streamErrorMessage = '';

      await understandProjectStream({
        generation_mode: 'precise',
        project_id: projectId || undefined,
        input_mode: 'raw_text',
        raw_text: trimmed,
        structured_input: spec,
      }, {
        onStatus: (message) => {
          setStreamStatus(message || '正在并列生成对话和结构化稿件');
        },
        onDelta: (text) => {
          if (!text) return;
          receivedDelta = true;
          streamAssistantText(text);
        },
        onDraft: (data) => {
          console.log('[AI RAW]', data);
          console.log('[PATCH SEND]', getAcceptedOps(data));
          draftResponse = data;
        },
        onError: (message, code) => {
          streamErrorMessage = code === 'AI_SERVICE_AUTH_ERROR'
            ? 'AI 服务密钥无效或已过期。请先到设置页更新模型 API Key，或修改 .env 后重启后端。'
            : message;
        },
      });

      if (streamErrorMessage) {
        if (!receivedDelta) {
          updateAssistantContent(() => streamErrorMessage);
        }
        show({ type: 'error', message: streamErrorMessage });
        return;
      }

      const finalDraftResponse = draftResponse as UnderstandProjectResponse | null;
      await assistantTypingTask;
      const acceptedOps = getAcceptedOps(finalDraftResponse);
      const note = [
        acceptedOps.length === 0 ? '本轮 AI 未产生字段修改' : '',
        patchFailureNote(finalDraftResponse?.rejected_ops),
      ].filter(Boolean).join('\n');

      if (!receivedDelta && finalDraftResponse) {
        const labels = finalDraftResponse.missing_fields.map((field: string) => fieldLabels[field] || field);
        await streamAssistantText(
          acceptedOps.length > 0
            ? buildAssistantReply(finalDraftResponse, labels)
            : (finalDraftResponse.reply?.trim() || '我已收到本轮内容。')
        );
      }
      if (finalDraftResponse) {
        if (note) {
          setAssistantNote(note);
        }
        console.log('[PATCH RESULT]', finalDraftResponse);
        if (acceptedOps.length > 0) {
          setDraftSyncState('editing');
          setStreamStatus('正在编辑方案稿');
          if (shouldAnimateAssistantStream) {
            await wait(900);
          }
          applyResponse(finalDraftResponse);
        }
      }
    } catch (error: any) {
      updateAssistantContent(() => getPptEditorErrorMessage(error, '本轮分析失败，请检查后端服务或 API 配置。'));
    } finally {
      setDraftSyncState((current) => (
        current === 'streaming' || current === 'editing'
          ? 'synced'
          : current
      ));
      setLoading(false);
      setStreamStatus(null);
    }
  };

  const handleConfirmDraft = async () => {
    if (!canSaveStructuredDraft || loading || outlineLoading) {
      show({ type: 'error', message: '请先通过对话生成结构化稿件后再确认' });
      return;
    }

    setLoading(true);
    try {
      const response = await understandProject({
        generation_mode: 'precise',
        project_id: projectId || undefined,
        input_mode: 'structured_input',
        structured_input: spec,
      });

      if (!response.success || !response.data) {
        show({ type: 'error', message: apiErrorText(response.error, '确认稿子失败') });
        return;
      }

      applyResponse(response.data, { keepConfirmation: true });
      setDraftConfirmed(true);
      setConfirmedAt(nowLabel());
      appendMessage({
        role: 'assistant',
        content: '已锁定当前结构化稿件为确认版本。现在可以基于这份稿件生成 PPT 大纲。',
      });
      show({ type: 'success', message: '稿件已确认' });
    } catch (error: any) {
      show({ type: 'error', message: getPptEditorErrorMessage(error, '确认稿子失败') });
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateOutline = async () => {
    if (outlineLoading) return;

    if (!draftConfirmed) {
      show({ type: 'error', message: '请先点击「确认稿子」，再生成 PPT 大纲' });
      return;
    }

    if (!canGenerateOutline) {
      show({ type: 'error', message: '请先解析项目资料，并补齐最小必要信息后再生成 PPT 大纲' });
      return;
    }
    setOutlineLoading(true);
    try {
      const savedProjectId = projectId;
      if (!savedProjectId) {
        show({ type: 'error', message: '确认稿件缺少项目 ID，请重新确认稿子' });
        return;
      }
      writeStoredPreciseDraft({
        projectId: savedProjectId,
        spec,
        missingFields,
        riskFlags,
        confidence,
        inputQuality,
        outlineInFlight: true,
        updatedAt: Date.now(),
      });

      let streamError = '';
      let generatedPages = 0;
      await generateOutlineStream(savedProjectId, {
        onPage: () => {
          generatedPages += 1;
          setOutlineProgressIndex((index) => index + 1);
        },
        onDone: () => {
          clearStoredPreciseDraft();
          show({ type: 'success', message: `PPT 大纲已生成${generatedPages ? `（${generatedPages} 页）` : ''}` });
          navigate(`/project/${savedProjectId}/outline`);
        },
        onError: (message) => {
          streamError = message || '生成大纲失败';
        },
      });

      if (streamError) {
        show({ type: 'error', message: streamError });
      }
    } catch (error: any) {
      show({ type: 'error', message: getPptEditorErrorMessage(error, '生成大纲失败') });
    } finally {
      const stored = readStoredPreciseDraft();
      if (stored?.outlineInFlight) {
        writeStoredPreciseDraft({ ...stored, outlineInFlight: false, updatedAt: Date.now() });
      }
      setOutlineLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    setLoading(true);
    setUploadState({ status: '上传中...' });
    try {
      const uploaded = await uploadReferenceFile(file, null);
      const referenceFile = uploaded.data?.file;
      if (!referenceFile) {
        show({ type: 'error', message: '上传失败：未返回文件信息' });
        return;
      }
      setUploadState({ file: referenceFile, status: '解析文件中...' });
      await triggerFileParse(referenceFile.id);

      let parsedFile = referenceFile;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const polled = await getReferenceFile(referenceFile.id);
        if (!polled.data?.file) continue;
        parsedFile = polled.data.file;
        setUploadState({ file: parsedFile, status: `解析状态：${parsedFile.parse_status}` });
        if (parsedFile.parse_status === 'completed' || parsedFile.parse_status === 'failed') break;
      }

      if (parsedFile.parse_status !== 'completed') {
        show({ type: 'error', message: parsedFile.error_message || '文件解析未完成' });
        return;
      }

      await submitUnderstanding('uploaded_file', { file_id: parsedFile.id });
    } catch (error: any) {
      show({ type: 'error', message: error?.response?.data?.error?.message || '上传或解析失败' });
    } finally {
      setLoading(false);
    }
  };

  const handleSpecPatch = async (op: PatchOp) => {
    try {
      console.log('[PATCH SEND]', [op]);
      const response = await understandProject({
        generation_mode: 'precise',
        project_id: projectId || undefined,
        input_mode: 'patch',
        structured_input: spec,
        patch_ops: [op],
      });
      console.log('[PATCH RESULT]', response.data || response);
      if (!response.success || !response.data) {
        show({ type: 'error', message: apiErrorText(response.error, '字段更新失败') });
        return;
      }
      const failureNote = patchFailureNote(response.data.rejected_ops);
      if (failureNote) {
        show({ type: 'error', message: failureNote });
      }
      const acceptedOps = getAcceptedOps(response.data);
      applyResponse(response.data, { keepConfirmation: acceptedOps.length === 0 });
    } catch (error: any) {
      show({ type: 'error', message: getPptEditorErrorMessage(error, '字段更新失败') });
    }
  };

  const handleUnlockField = async (path: string) => {
    const previousSpec = spec;
    const nextSpec = unlockSpecField(previousSpec, path);

    try {
      const response = await understandProject({
        generation_mode: 'precise',
        project_id: projectId || undefined,
        input_mode: 'structured_input',
        structured_input: nextSpec,
      });
      if (!response.success || !response.data) {
        show({ type: 'error', message: apiErrorText(response.error, '解锁失败') });
        return;
      }
      applyResponse(response.data);
      setDraftConfirmed(false);
      setConfirmedAt(null);
      show({ type: 'success', message: '已允许 AI 修改该字段' });
    } catch (error: any) {
      show({ type: 'error', message: getPptEditorErrorMessage(error, '解锁失败') });
    }
  };

  const restoreDefaultDraft = () => {
    const nextSpec = emptySpec();
    setSpec(nextSpec);
    setProjectId(null);
    setMissingFields([]);
    setRiskFlags([]);
    setConfidence({});
    setInputQuality('insufficient');
    setDraftConfirmed(false);
    setConfirmedAt(null);
    setDraftSyncState('synced');
    clearStoredPreciseDraft();
    show({ type: 'info', message: '已恢复默认稿件模板' });
  };

  return (
    <div className="min-h-screen bg-[#F3F7FC] pb-24 text-[#14213D] dark:bg-background-primary dark:text-foreground-primary">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur dark:border-white/10 dark:bg-background-primary/90">
        <div className="mx-auto flex max-w-[1680px] items-center justify-between px-5 py-3">
          <div className="flex min-w-0 items-center gap-4">
            <Button variant="ghost" size="sm" icon={<ArrowLeft size={18} />} onClick={() => navigate('/app')}>
              返回
            </Button>
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-black tracking-normal">大赛文档对话共创</h1>
              <p className="text-sm font-medium text-slate-500">通过对话不断完善结构化稿件，确认后生成 PPT 大纲</p>
            </div>
          </div>
          <div className="hidden items-center gap-3 md:flex">
            <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-black text-blue-700">V3.2</span>
            <span className="inline-flex items-center gap-1.5 text-sm font-bold text-emerald-700">
              <CheckCircle2 size={16} />
              {projectId ? `已自动保存 ${nowLabel()}` : '等待首次对话'}
            </span>
          </div>
        </div>
      </header>

      <main
        className={`mx-auto grid max-w-[1680px] grid-cols-1 gap-4 px-5 py-5 transition-[grid-template-columns] duration-300 xl:h-[calc(100vh-140px)] xl:justify-center xl:overflow-hidden ${
          isPreviewPanelOpen
            ? 'xl:grid-cols-[300px_minmax(420px,1fr)_520px]'
            : 'xl:grid-cols-[300px_minmax(720px,1080px)]'
        }`}
      >
        <aside className="space-y-4 xl:min-h-0 xl:overflow-y-auto xl:pb-4">
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-background-secondary">
            <h2 className="text-lg font-black">共创流程</h2>
            <div className="mt-5 space-y-5">
              <FlowStep index={1} title="对话完善内容" desc="输入需求、资料或修改意见" active={!draftConfirmed} done={Boolean(projectId)} />
              <FlowStep index={2} title="结构化文档" desc="实时生成结构化稿件" active={Boolean(projectId) && !draftConfirmed} done={completion.percent >= 70} />
              <FlowStep index={3} title="确认稿子" desc="锁定当前稿件内容" active={!draftConfirmed && Boolean(projectId)} done={draftConfirmed} />
              <FlowStep index={4} title="生成PPT大纲" desc="基于确认稿件生成大纲" active={draftConfirmed} done={outlineLoading} />
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-background-secondary">
            <h2 className="text-lg font-black">稿件完成度</h2>
            <div className="mt-4 flex items-center gap-4">
              <div
                className="grid h-24 w-24 shrink-0 place-items-center rounded-full"
                style={{ background: `conic-gradient(#2563EB ${completion.percent * 3.6}deg, #E5EAF2 0deg)` }}
              >
                <div className="grid h-16 w-16 place-items-center rounded-full bg-white text-xl font-black dark:bg-background-secondary">
                  {completion.percent}%
                </div>
              </div>
              <div className="min-w-0 text-sm leading-6 text-slate-600 dark:text-foreground-secondary">
                <div className="font-black text-[#14213D] dark:text-foreground-primary">{completion.done}/{completion.total} 项已具备</div>
                <div>状态：{qualityLabel[inputQuality]}</div>
                {confirmedAt && <div>确认时间：{confirmedAt}</div>}
              </div>
            </div>
            {missingLabels.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-black">{minimumMissingFields.length > 0 ? '生成前最低需要' : '建议补充字段'}</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {missingLabels.slice(0, 10).map((item) => (
                    <span key={item} className="rounded-md bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-background-secondary">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-black">辅助材料</h2>
              <Button variant="secondary" size="sm" icon={<Download size={16} />} onClick={downloadProjectMaterialTemplate}>
                模板
              </Button>
            </div>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-600 dark:text-foreground-secondary">
              <GuideBlock title="最低需要" items={['项目/任务做什么', '真实岗位现场在哪里', '服务对象是谁', '现场能展示哪些技能动作']} />
              <GuideBlock title="推荐材料" items={['申报书、任务书、课程案例', '团队分工、训练记录', '成果清单、测试记录、评分材料']} />
            </div>
          </section>
        </aside>

        <section className="flex min-h-[calc(100vh-220px)] flex-col rounded-lg border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-background-secondary xl:h-full xl:min-h-0">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-white/10">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-full bg-blue-50 text-blue-700">
                <Bot size={22} />
              </div>
              <div>
                <h2 className="text-xl font-black">对话共创</h2>
                <p className="text-sm text-slate-500">发送一轮，右侧稿件同步更新一轮</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {!isPreviewPanelOpen && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<PanelRightOpen size={16} />}
                  onClick={() => setIsPreviewPanelOpen(true)}
                >
                  展开稿件板
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                icon={<X size={16} />}
                onClick={() => {
                  setChatMessages([chatMessages[0]]);
                  setChatInput('');
                }}
              >
                清空对话
              </Button>
            </div>
          </div>

          {outlineLoading && (
            <div className="mx-5 mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm font-bold text-blue-800" aria-live="polite">
              <Loader2 className="mr-2 inline animate-spin" size={16} />
              {currentOutlineProgress}
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6">
            <div className="mx-auto flex w-full max-w-[960px] flex-col gap-5">
              {chatMessages.map((message) => {
                const isUser = message.role === 'user';
                return (
                  <div key={message.id} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
                    {!isUser && (
                      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue-50 text-blue-700">
                        <Bot size={20} />
                      </div>
                    )}
                    <div className={`max-w-[78%] md:max-w-[760px] ${isUser ? 'text-right' : 'text-left'}`}>
                      <div className="mb-1 text-xs font-bold text-slate-400">
                        {isUser ? '用户' : 'AI专家助手'} · {message.time}
                      </div>
                      <div
                        className={`whitespace-pre-wrap rounded-lg px-4 py-3 text-sm leading-7 shadow-sm ${
                          isUser
                            ? 'bg-blue-600 text-white'
                            : 'border border-slate-200 bg-white text-slate-700 dark:border-white/10 dark:bg-background-primary dark:text-foreground-secondary'
                        }`}
                      >
                        {message.content}
                      </div>
                      {!isUser && message.note && (
                        <div className="mt-1 whitespace-pre-wrap px-1 text-xs leading-5 text-slate-400">
                          {message.note}
                        </div>
                      )}
                    </div>
                    {isUser && (
                      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-600">
                        <UserRound size={20} />
                      </div>
                    )}
                  </div>
                );
              })}
              {loading && (
                <div className="flex items-center gap-3 text-sm font-bold text-blue-700">
                  <Loader2 className="animate-spin" size={18} />
                  {streamStatus || '正在并列生成对话和结构化稿件...'}
                </div>
              )}
            </div>
          </div>

          <div className="shrink-0 border-t border-slate-200 p-4 dark:border-white/10">
            <div className="mx-auto w-full max-w-[960px]">
              {uploadState.status && (
                <div className="mb-3 rounded-md bg-blue-50 px-3 py-2 text-xs font-bold text-blue-800">
                  {loading && <Loader2 className="mr-2 inline animate-spin" size={14} />}
                  {uploadState.file?.filename ? `${uploadState.file.filename}：` : ''}{uploadState.status}
                </div>
              )}
              <div className="rounded-2xl border border-slate-200 bg-[#F8FAFD] p-3 shadow-sm dark:border-white/10 dark:bg-background-primary">
                <textarea
                  value={chatInput}
                  onChange={(event) => setChatInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                      event.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  className="min-h-[64px] w-full resize-none bg-transparent text-sm leading-7 outline-none placeholder:text-slate-400"
                  placeholder="输入项目资料或修改意见，例如：帮我完善这份大赛项目文档，突出真实场景和四人分工。"
                />
                <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md px-3 text-sm font-bold text-slate-500 hover:bg-white hover:text-blue-700">
                      <Paperclip size={16} />
                      附件
                      <input
                        type="file"
                        className="hidden"
                        accept=".pdf,.ppt,.pptx,.doc,.docx,.txt,.md"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) handleUpload(file);
                          event.target.value = '';
                        }}
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => setChatInput(projectMaterialTemplate)}
                      className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-bold text-slate-500 hover:bg-white hover:text-blue-700"
                    >
                      <FileText size={16} />
                      复制模板
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsPromptFullscreenOpen(true)}
                      className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-bold text-slate-500 hover:bg-white hover:text-blue-700"
                    >
                      <Expand size={16} />
                      全屏写提示词
                    </button>
                  </div>
                  <Button icon={<Send size={18} />} loading={loading} disabled={!chatInput.trim() || loading || outlineLoading} onClick={handleSendMessage}>
                    发送
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {isPreviewPanelOpen && (
        <aside className="space-y-4 xl:min-h-0 xl:overflow-y-auto xl:pb-4">
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-background-secondary">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-xl font-black">实时稿件编辑板</h2>
                <p className="text-sm text-slate-500">AI 和手工编辑都通过字段补丁更新</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<RotateCcw size={15} />}
                  disabled={loading || outlineLoading}
                  onClick={restoreDefaultDraft}
                >
                  恢复默认
                </Button>
                <span className={`rounded-full px-3 py-1 text-xs font-black ${draftConfirmed ? 'bg-emerald-50 text-emerald-700' : 'bg-orange-50 text-orange-700'}`}>
                  {draftConfirmed ? '已确认' : '待确认'}
                </span>
                <button
                  type="button"
                  aria-label="关闭实时稿件编辑板"
                  onClick={() => setIsPreviewPanelOpen(false)}
                  className="grid h-8 w-8 place-items-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  title="关闭实时稿件编辑板"
                >
                  <PanelRightClose size={17} />
                </button>
              </div>
            </div>

            <div className="relative mt-4 rounded-lg border border-slate-200 bg-[#F8FAFD] dark:border-white/10 dark:bg-background-primary">
              <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2 text-xs font-bold text-slate-500 dark:border-white/10">
                <span>4 条技能模块 · {lockedFieldCount} 个用户锁定字段</span>
                <span className={`rounded-full px-2 py-1 ${draftSyncMeta.className}`}>
                  {draftSyncMeta.label}
                </span>
              </div>
              {draftSyncState === 'editing' && (
                <div className="absolute inset-x-3 top-12 z-10 rounded-lg border border-indigo-200 bg-white/95 px-4 py-3 text-sm font-bold text-indigo-700 shadow-lg backdrop-blur dark:border-indigo-500/30 dark:bg-background-secondary/95">
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="animate-spin" size={16} />
                    AI 正在编辑方案稿，请稍候...
                  </span>
                </div>
              )}
              <div className="p-4">
                <SpecEditor spec={spec} onPatch={handleSpecPatch} onUnlock={handleUnlockField} />
              </div>
            </div>
          </section>
        </aside>
        )}
      </main>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-5 py-3 shadow-[0_-8px_24px_rgba(15,23,42,0.08)] backdrop-blur dark:border-white/10 dark:bg-background-primary/95">
        <div className="mx-auto flex max-w-[1680px] flex-col gap-3 md:flex-row md:items-center md:justify-center">
          <Button
            className="min-w-[220px]"
            variant="primary"
            icon={<CheckCircle2 size={18} />}
            loading={loading}
            disabled={!canConfirmDraft || loading || outlineLoading}
            onClick={handleConfirmDraft}
          >
            确认稿子
          </Button>
          <div className="hidden h-px w-16 bg-slate-200 md:block" />
          <Button
            className="min-w-[220px]"
            variant="secondary"
            icon={<Wand2 size={18} />}
            loading={outlineLoading}
            disabled={!canGenerateOutline || outlineLoading}
            onClick={handleGenerateOutline}
          >
            生成 PPT 大纲
          </Button>
          <div className="text-sm font-bold text-slate-500 md:ml-4">
            {draftConfirmed ? '确认稿子后即可生成PPT大纲' : '请先通过对话完善并确认当前稿件'}
          </div>
        </div>
      </div>

      {isPromptFullscreenOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 p-4 backdrop-blur-md md:p-8" role="dialog" aria-modal="true" aria-label="全屏写提示词">
          <div className="mx-auto flex h-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-white/15 bg-white shadow-2xl dark:bg-background-secondary">
            <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 dark:border-white/10">
              <div>
                <h2 className="text-xl font-black">沉浸式写提示词</h2>
                <p className="text-sm text-slate-500">在这里完整组织项目资料、修改要求或下一轮追问，退出后内容会保留。</p>
              </div>
              <button
                type="button"
                aria-label="退出全屏写提示词"
                onClick={() => setIsPromptFullscreenOpen(false)}
                className="grid h-10 w-10 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-white/10 dark:hover:text-white"
              >
                <X size={20} />
              </button>
            </div>
            <textarea
              autoFocus
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              className="min-h-0 flex-1 resize-none bg-[#F8FAFD] p-6 text-base leading-8 text-slate-800 outline-none placeholder:text-slate-400 dark:bg-background-primary dark:text-foreground-secondary"
              placeholder="写下完整提示词，例如：请基于当前方案稿，补充应用价值和创新点，突出四名选手现场动作、成果证据和评委可核验材料。"
            />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-5 py-4 dark:border-white/10">
              <div className="text-sm font-bold text-slate-500">
                Esc 可退出，内容会同步到底部对话框。
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" onClick={() => setIsPromptFullscreenOpen(false)}>
                  退出
                </Button>
                <Button icon={<Send size={18} />} loading={loading} disabled={!chatInput.trim() || loading || outlineLoading} onClick={handleSendMessage}>
                  发送
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const FlowStep: React.FC<{
  index: number;
  title: string;
  desc: string;
  active?: boolean;
  done?: boolean;
}> = ({ index, title, desc, active = false, done = false }) => (
  <div className={`flex gap-3 rounded-lg p-2 ${active ? 'bg-orange-50 text-orange-700' : ''}`}>
    <div
      className={`grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-black ${
        done
          ? 'bg-emerald-500 text-white'
          : active
            ? 'bg-orange-500 text-white'
            : 'bg-slate-200 text-slate-600'
      }`}
    >
      {done ? <Check size={16} /> : index}
    </div>
    <div className="min-w-0">
      <div className="font-black">{title}</div>
      <div className="text-sm text-slate-500">{desc}</div>
    </div>
  </div>
);

const GuideBlock: React.FC<{ title: string; items: string[] }> = ({ title, items }) => (
  <div>
    <h3 className="font-black text-[#182135] dark:text-foreground-primary">{title}</h3>
    <ul className="mt-2 space-y-1">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          <span className="mt-2 h-1.5 w-1.5 rounded-full bg-teal-500" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  </div>
);
