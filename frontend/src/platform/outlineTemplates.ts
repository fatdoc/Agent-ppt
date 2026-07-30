import type { OutlineTemplate, OutlineTemplateSection } from './types';

type WvccPageDefinition = {
  title: string;
  speaker: string;
  scoreDimensions: string[];
  purpose: string;
};

const wvccPages: WvccPageDefinition[] = [
  { title: '项目封面', speaker: '一号工程师', scoreDimensions: [], purpose: '建立项目定位、团队与赛项识别' },
  { title: '国家政策与时代背景', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '说明项目服务的国家战略与产业方向' },
  { title: '行业发展趋势', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '说明行业变化和新需求' },
  { title: '项目来源与真实任务', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '证明项目来自真实任务而非虚构案例' },
  { title: '团队介绍与协作任务划分', speaker: '全体工程师', scoreDimensions: ['teamwork'], purpose: '展示角色、输入输出和任务流转' },
  { title: '目录', speaker: '一号工程师', scoreDimensions: [], purpose: '建立汇报结构与节奏' },
  { title: '真实调研', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '呈现调研对象、方法与真实需求证据' },
  { title: '项目痛点总览', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '归纳数据、判断和决策三类核心问题' },
  { title: '痛点一：数据获取难', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '说明采集不连续、不精准、不及时' },
  { title: '痛点二：状态判断难', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '说明人工判断的滞后与风险' },
  { title: '痛点三：管理决策难', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '说明数据、知识和控制未闭环的问题' },
  { title: '项目建设目标', speaker: '一号工程师', scoreDimensions: ['application-value'], purpose: '定义可感知、可识别、可分析、可控制、可追溯目标' },
  { title: '总体思路', speaker: '一号工程师', scoreDimensions: ['innovation'], purpose: '概括感知—识别—分析—控制闭环' },
  { title: '解决方案总览', speaker: '一号工程师', scoreDimensions: ['skill-level', 'innovation'], purpose: '展示数据、识别、问答、控制和多端模块' },
  { title: '系统架构', speaker: '一号工程师', scoreDimensions: ['skill-level', 'innovation'], purpose: '呈现感知、传输、平台、应用和决策分层' },
  { title: '技能要点总览', speaker: '一号工程师', scoreDimensions: ['skill-level'], purpose: '进入占比三分之二以上的技能展示主体' },
  { title: '1号工程师任务卡', speaker: '一号工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '说明需求、架构与验收岗位任务' },
  { title: '1号技能点1：需求分析与任务拆解', speaker: '一号工程师', scoreDimensions: ['skill-level'], purpose: '展示痛点到功能与岗位任务的拆解过程' },
  { title: '1号技能点2：系统流程与架构设计', speaker: '一号工程师', scoreDimensions: ['skill-level', 'innovation'], purpose: '展示业务流程和接口关系' },
  { title: '1号技能点3：质量验收与风险控制', speaker: '一号工程师', scoreDimensions: ['skill-level', 'professionalism', 'teamwork'], purpose: '展示功能、接口、安全验收与交接' },
  { title: '2号工程师任务卡', speaker: '二号工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '说明数据采集、设备和通信岗位任务' },
  { title: '2号技能点1：设备接入与数据采集', speaker: '二号工程师', scoreDimensions: ['skill-level', 'professionalism'], purpose: '展示规范接入、实时采集和字段校验' },
  { title: '2号技能点2：数据清洗、标注与标准化', speaker: '二号工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '展示数据治理、复核并向算法岗位交付' },
  { title: '2号技能点3：通信控制与安全保护', speaker: '二号工程师', scoreDimensions: ['skill-level', 'professionalism'], purpose: '展示通信、阈值保护、报警和日志' },
  { title: '3号工程师任务卡', speaker: '三号工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '说明模型训练、优化、评估和部署任务' },
  { title: '3号技能点1：数据集构建与模型训练', speaker: '三号工程师', scoreDimensions: ['skill-level'], purpose: '展示数据划分、模型选择和训练过程' },
  { title: '3号技能点2：参数优化与难点突破', speaker: '三号工程师', scoreDimensions: ['skill-level', 'innovation'], purpose: '展示真实问题、优化动作与前后对比' },
  { title: '3号技能点3：模型评估与部署验证', speaker: '三号工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '展示独立指标、健壮性和接口交付' },
  { title: '4号工程师任务卡', speaker: '四号工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '说明知识库、应用与系统联调岗位任务' },
  { title: '4号技能点1：知识库与智能问答', speaker: '四号工程师', scoreDimensions: ['skill-level', 'innovation'], purpose: '展示切分、检索和有依据的专业回答' },
  { title: '4号技能点2：前后端开发与多端展示', speaker: '四号工程师', scoreDimensions: ['skill-level'], purpose: '展示真实接口与用户操作路径' },
  { title: '4号技能点3：全流程联调与现场演示', speaker: '四号工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '打通采集—识别—分析—控制—反馈闭环' },
  { title: '全链路验收', speaker: '全体工程师', scoreDimensions: ['skill-level', 'teamwork'], purpose: '以现场确认和异常处置证明协作与完成度' },
  { title: '职业素养与安全规范', speaker: '全体工程师', scoreDimensions: ['professionalism'], purpose: '呈现标准、知识产权、数据和设备安全' },
  { title: '项目成果展示', speaker: '全体工程师', scoreDimensions: ['application-value'], purpose: '用真实实物、数据、模型、系统和证明材料验证成果' },
  { title: '应用价值', speaker: '全体工程师', scoreDimensions: ['application-value'], purpose: '说明实用性、经济性、质量与可持续性' },
  { title: '项目创新', speaker: '全体工程师', scoreDimensions: ['innovation'], purpose: '说明技术、流程、产品和服务创新' },
  { title: '未来展望与国家战略升华', speaker: '全体工程师', scoreDimensions: ['innovation', 'application-value'], purpose: '提出有依据的后续优化与战略价值' },
  { title: '礼貌结束语', speaker: '全体工程师', scoreDimensions: ['teamwork'], purpose: '总结价值、团队目标并完成正式收束' },
];

const pageSection = (page: WvccPageDefinition, index: number): OutlineTemplateSection => ({
  id: `wvcc-page-${index + 1}`,
  title: `第 ${index + 1} 页：${page.title}`,
  recommendedPageCount: 1,
  pageType: index === 0 ? 'COVER' : index === 38 ? 'ENDING' : 'CONTENT',
  purpose: page.purpose,
  scoreDimensions: page.scoreDimensions,
  recommendedSpeaker: page.speaker,
  materialRequirements: ['项目真实材料', '可核验证据', '与本页目的相关的图片或数据'],
  generationInstructions: '使用项目材料填充【】占位内容；没有证据的数据不得生成。',
});

const rangeSection = (
  id: string,
  title: string,
  startPage: number,
  endPage: number,
  purpose: string,
): OutlineTemplateSection => ({
  id,
  title,
  description: purpose,
  recommendedPageCount: endPage - startPage + 1,
  purpose,
  children: wvccPages.slice(startPage - 1, endPage).map((page, offset) =>
    pageSection(page, startPage - 1 + offset)),
});

const now = '2026-07-30T00:00:00.000Z';

export const SYSTEM_OUTLINE_TEMPLATES: OutlineTemplate[] = [
  {
    id: 'wvcc-championship-39',
    name: '世职赛争夺赛 39 页通用模板',
    description: '根据用户提供的世职赛通用 PPT 与逐字稿模板整理，技能展示占主体并贯穿五项评分维度。',
    competitionId: 'wvcc',
    competitionTypeId: 'championship',
    supportScope: 'SYSTEM',
    status: 'PUBLISHED',
    version: 1,
    targetPageCount: 39,
    styleTags: ['争夺赛', '项目展示', '技能实操', '逐字稿联动'],
    sections: [
      rangeSection('opening', '项目定位与真实问题', 1, 12, '快速建立真实来源、问题和建设目标'),
      rangeSection('solution', '总体方案', 13, 16, '说明系统闭环、架构和技能展示路径'),
      rangeSection('skills', '核心技能展示', 17, 33, '按四个岗位展示任务、难点、操作、标准、结果和交付'),
      rangeSection('quality', '职业素养与成果', 34, 35, '呈现安全规范与可核验成果'),
      rangeSection('value', '应用价值与创新', 36, 38, '说明价值、创新和后续方向'),
      rangeSection('ending', '正式结束', 39, 39, '完成项目价值与团队表达的收束'),
    ],
    versions: [],
    createdBy: 'SYSTEM',
    createdAt: now,
    updatedAt: now,
  },
  {
    id: 'platform-generic',
    name: '平台通用项目汇报模板',
    description: '不包含任何赛事专属评分、规则或案例，适用于通用和自定义赛事。',
    supportScope: 'SYSTEM',
    status: 'PUBLISHED',
    version: 1,
    targetPageCount: 15,
    styleTags: ['通用', '项目汇报'],
    sections: [
      {
        id: 'generic-context',
        title: '背景与问题',
        recommendedPageCount: 3,
        purpose: '说明真实背景、用户和问题',
        materialRequirements: ['项目背景', '用户或场景证据'],
      },
      {
        id: 'generic-solution',
        title: '方案与实现',
        recommendedPageCount: 7,
        purpose: '说明方案、实现过程和结果',
        materialRequirements: ['架构或流程', '实现截图', '测试结果'],
      },
      {
        id: 'generic-value',
        title: '成果与价值',
        recommendedPageCount: 4,
        purpose: '展示成果、价值与后续计划',
        materialRequirements: ['成果证据', '用户反馈'],
      },
      {
        id: 'generic-ending',
        title: '结束页',
        recommendedPageCount: 1,
        pageType: 'ENDING',
        purpose: '总结与致谢',
      },
    ],
    versions: [],
    createdBy: 'SYSTEM',
    createdAt: now,
    updatedAt: now,
  },
];

export interface OutlineTemplateMatchContext {
  competitionId: string;
  competitionTypeId?: string;
  trackId?: string;
  themeId?: string;
}

const matchRank = (template: OutlineTemplate, context: OutlineTemplateMatchContext) => {
  if (template.status !== 'PUBLISHED') return -1;
  if (template.competitionId && template.competitionId !== context.competitionId) return -1;
  if (template.competitionTypeId && template.competitionTypeId !== context.competitionTypeId) return -1;
  if (template.trackId && template.trackId !== context.trackId) return -1;
  if (template.themeId && template.themeId !== context.themeId) return -1;
  if (template.competitionId && template.competitionTypeId && template.trackId && template.themeId) return 5;
  if (template.competitionId && template.competitionTypeId && template.trackId) return 4;
  if (template.competitionId && template.competitionTypeId) return 3;
  if (template.competitionId) return 2;
  return 1;
};

export const findBestOutlineTemplate = (
  templates: OutlineTemplate[],
  context: OutlineTemplateMatchContext,
) =>
  templates
    .map((template) => ({ template, rank: matchRank(template, context) }))
    .filter(({ rank }) => rank >= 0)
    .sort((a, b) => b.rank - a.rank)[0]?.template;
