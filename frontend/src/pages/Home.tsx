import React, { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Sparkles, FileText, FileEdit, ImagePlus, Paperclip, Palette, Lightbulb, Search, Settings, FolderOpen, HelpCircle, Sun, Moon, Globe, Monitor, ChevronDown, Upload, RefreshCw } from 'lucide-react';
import { Button, Card, useToast, MaterialGeneratorModal, MaterialCenterModal, MaterialSelector, ReferenceFileList, ReferenceFileSelector, FilePreviewModal, Footer, TextStyleSelector } from '@/components/shared';
import { MarkdownTextarea, type MarkdownTextareaRef } from '@/components/shared/MarkdownTextarea';
import { TemplateSelector, getTemplateFile } from '@/components/shared/TemplateSelector';
import { AgentModePanel } from '@/components/agent';
import { listUserTemplates, type UserTemplate, uploadReferenceFile, type ReferenceFile, associateFileToProject, triggerFileParse, associateMaterialsToProject, createPptRenovationProject, createPptToPptProject } from '@/api/endpoints';
import { useProjectStore } from '@/store/useProjectStore';
import { devLog } from '@/utils/logger';
import { useTheme } from '@/hooks/useTheme';
import { useImagePaste, buildMaterialsMarkdown } from '@/hooks/useImagePaste';
import type { GenerationMode, HarnessTemplate, Material } from '@/types';
import { useT } from '@/hooks/useT';
import { ASPECT_RATIO_OPTIONS } from '@/config/aspectRatio';

type CreationType = 'agent' | 'no_think' | 'idea' | 'outline' | 'description' | 'ppt_to_ppt' | 'ppt_renovation';
type VisibleCreationType = 'agent' | 'no_think' | 'outline' | 'ppt_to_ppt' | 'ppt_renovation';
type RenovationStyleSource = 'original' | 'template';
type PptToPptStyleSource = 'original' | 'template';

// 支持作为参考文件上传的文档扩展名（与后端 file_parser_service 保持一致）
const ALLOWED_DOC_EXTENSIONS = ['pdf', 'docx', 'pptx', 'doc', 'ppt', 'xlsx', 'xls', 'csv', 'txt', 'md'];

const NO_THINK_SELECT_OPTIONS = {
  scenario: ['工作汇报', '产品发布', '教学课件', '个人展示'],
  density: ['精炼要点版', '详细说明版'],
  styleTemplate: ['商务演示', '极简展示', '创意渐变'],
};

// 页面特有翻译 - AI 可以直接看到所有文案，保留原始 key 结构
const homeI18n = {
  zh: {
    nav: {
      materialGenerate: '素材生成', materialCenter: '素材中心',
      history: '历史项目', settings: '设置'
    },
    settings: {
      language: { label: '界面语言' },
      theme: { label: '主题模式', light: '浅色', dark: '深色', system: '跟随系统' }
    },
    home: {
      title: '兰台',
      subtitle: '把 PPT 生产变成可接入、可编排、可校验、可交付的 Harness 工程',
      tagline: '兰台·PPT Agent',
      features: {
        oneClick: '材料接入 Harness',
        naturalEdit: 'Agent 编排结构',
        regionEdit: '风格验证 Gate',
        export: '稳定交付 PPTX/PDF',
      },
      tabs: {
        no_think: '混乱材料模式',
        agent: 'Harness Agent',
        idea: '一句话生成',
        outline: '大纲 PPT生成模式',
        description: '从描述生成',
        ppt_to_ppt: '借鉴生成',
        ppt_renovation: '旧稿翻新',
      },
      tabDescriptions: {
        no_think: '输入主题和约束，兰台自动搭建结构、页面描述与视觉初稿',
        agent: '先生成可编辑计划和风格验证页，确认 Gate 后再批量生成图片',
        idea: '输入你的想法，AI 将为你生成完整的 PPT',
        outline: '已有大纲？直接粘贴，逐页描述可选填写，也可以稍后由 AI 生成',
        description: '已有完整描述？AI 将自动解析并直接生成图片，跳过大纲步骤',
        ppt_to_ppt: '上传参考 PPT，再输入你的内容，兰台将结构、表达和视觉约束接入生成链路',
        ppt_renovation: '上传已有的 PDF/PPTX 文件，兰台解析旧稿并按 Harness 链路重构页面',
      },
      placeholders: {
        no_think: '例如：AI 工具入门培训，要求先讲价值再讲操作',
        agent: '例如：面向投资人的 AI 教育产品融资路演',
        idea: '例如：生成一份关于 AI 发展史的演讲 PPT',
        outline: '粘贴你的 PPT 大纲（必填）...',
        description: '粘贴你的完整页面描述...',
        ppt_to_ppt: '粘贴你的项目内容、工作材料、比赛说明或交付约束...',
      },
      content: {
        descriptionLabel: '逐页描述（选填）',
        descriptionPlaceholder: '如果你已经有每页内容、布局、图表或素材说明，可以直接填到这里',
        descriptionHint: '逐页描述用于补充每页内容、布局、图表和素材说明；全局视觉风格由上方风格模板控制。',
        emptyOutlineTip: '还没有大纲？可以使用快速 Harness 先生成完整结构',
        generateDescriptions: '根据大纲生成逐页描述',
      },
      generation: {
        title: '生成模式',
        fast: '快速生成',
        fastHint: '更快进入大纲、描述和生图流程',
        harness: 'Harness 高质量模式',
        harnessHint: '接入标准化计划、校验和页面组织流程',
        templateLabel: 'Harness 模板',
        paperOperators: 'paper-operators',
      },
      examples: {
        outline: '推荐输入格式（可直接复制）：\n\n第 1 页：AI 的起源\n- 1956 达特茅斯会议\n- 早期研究者的愿景\n\n第 2 页：机器学习的发展\n- 从规则驱动到数据驱动\n- 经典算法介绍\n\n第 3 页：未来展望\n- 趋势与挑战\n\n可只写页标题，AI 会按页头自动切分并转为结构化大纲；要点可选填，不影响解析。',
        description: '推荐输入格式（可直接复制）：\n\n第 1 页：AI 的起源\n页面文字：\n- 1956 年达特茅斯会议开创了 AI 概念。\n- 建议封面用左文右图，突出“目标与问题定义”。\n\n第 2 页：机器学习的发展\n页面文字：\n- 讲解从规则驱动到数据驱动的转变。\n- 可放一张算法演进对比图，底部给出关键里程碑。\n\n第 3 页：未来展望\n页面文字：\n- 总结趋势与挑战。\n- 补充伦理合规与风险治理方向。',
        fillOutline: '填入示例大纲',
        copyOutline: '复制示例大纲',
        fillDescription: '填入示例逐页描述',
        copyDescription: '复制示例逐页描述',
      },
      template: {
        title: '选择风格模板',
        useTextStyle: '使用文字描述风格',
        useExternalSkill: '使用外部风格 Skill',
        externalSkillId: 'Skill ID',
        externalPrompt: '外部 Skill 输出',
        externalPromptPlaceholder: '粘贴外部 Skill 生成的视觉系统、风格 prompt 或 JSON payload',
        externalHelper: '启用后，模板图、文字风格和页面描述中的全局风格词都不会参与视觉控制。',
      },
      noThink: {
        scenario: '使用场景',
        density: '内容密度',
        pageCount: 'PPT页数',
        styleTemplate: '风格倾向',
        extraInstruction: '额外要求',
        extraPlaceholder: '例如：适合新员工，避免技术细节过深',
      },
      actions: {
        selectFile: '选择参考文件',
        parsing: '解析中...',
        createProject: '创建新项目',
      },
      renovation: {
        uploadHint: '点击或拖拽上传 PDF / PPTX 文件',
        formatHint: '支持 .pdf, .pptx, .ppt 格式（推荐上传 PDF）',
        styleSource: '翻新风格',
        reuseOriginalStyle: '复用原版风格',
        chooseStyleTemplate: '选择风格模板',
        onlyPdfPptx: '仅支持 PDF 和 PPTX 文件',
        uploadFile: '请先上传 PDF 或 PPTX 文件',
        selectStyleTemplate: '请先选择风格模板或填写文字风格',
      },
      pptToPpt: {
        uploadHint: '点击或拖拽上传参考 PDF / PPTX 文件',
        formatHint: '参考文件用于学习结构、版式和表达方式',
        styleSource: '生成风格',
        reuseReferenceStyle: '复用参考 PPT 风格',
        chooseStyleTemplate: '选择风格模板',
        onlyPdfPptx: '仅支持 PDF 和 PPTX 文件',
        uploadFile: '请先上传参考 PDF 或 PPTX 文件',
        selectStyleTemplate: '请先选择风格模板或填写文字风格',
      },
      messages: {
        enterContent: '请输入内容',
        filesParsing: '还有 {{count}} 个参考文件正在解析中，请等待解析完成',
        filesParseFailed: '有 {{count}} 个参考文件解析失败，请删除或重新解析后再创建项目',
        projectCreateFailed: '项目创建失败',
        uploadingImage: '正在上传图片并识别内容...',
        imageUploadSuccess: '图片上传成功！已插入到光标位置',
        imageUploadFailed: '图片上传失败',
        fileUploadSuccess: '文件上传成功',
        fileUploadFailed: '文件上传失败',
        fileTooLarge: '文件过大：{{size}}MB，最大支持 200MB',
        fileUploadInProgress: '正在上传文件，请等待当前上传完成后再试',
        unsupportedFileType: '不支持的文件类型: {{type}}',
        pptTip: '建议先在本地将 PPTX 转为 PDF 后再上传，可获得更好的兼容性和更快的处理速度',
        filesAdded: '已添加 {{count}} 个参考文件',
        imageRemoved: '已移除图片',
        outlineCopied: '示例大纲已复制到剪贴板',
        descriptionCopied: '示例主页描述已复制到剪贴板',
        copyFailed: '复制失败，请手动复制',
        serviceTestTip: '建议先到设置页底部进行服务测试，避免后续功能异常',
        verifying: '正在验证 API 配置...',
        verifyFailed: '请在设置页配置正确的 API Key，并在页面底部点击「服务测试」验证',
        externalSkillMissing: '请填写外部风格 Skill ID 或外部 Skill 输出',
      },
    },
  },
  en: {
    nav: {
      materialGenerate: 'Generate Material', materialCenter: 'Material Center',
      history: 'History', settings: 'Settings'
    },
    settings: {
      language: { label: 'Interface Language' },
      theme: { label: 'Theme', light: 'Light', dark: 'Dark', system: 'System' }
    },
    home: {
      title: 'Lantai',
      subtitle: 'Turn deck production into an ingest, plan, verify, and ship harness',
      tagline: 'Lantai PPT Agent',
      features: {
        oneClick: 'Material ingest harness',
        naturalEdit: 'Agent structure planning',
        regionEdit: 'Style verification gate',
        export: 'Stable PPTX/PDF delivery',
      },
      tabs: {
        no_think: 'Quick Harness',
        agent: 'Harness Agent',
        idea: 'From Idea',
        outline: 'Material to PPT',
        description: 'From Description',
        ppt_to_ppt: 'Reference Harness',
        ppt_renovation: 'Legacy Deck Rebuild',
      },
      tabDescriptions: {
        no_think: 'Enter a topic and constraints; Lantai builds structure, page descriptions, and a visual draft',
        agent: 'Generate an editable plan and style preview first, then batch-generate images after the verification gate',
        idea: 'Enter your idea, AI will generate a complete PPT for you',
        outline: 'Have an outline? Paste it directly; slide descriptions are optional and can be generated later',
        description: 'Have detailed descriptions? AI will parse and generate images directly, skipping the outline step',
        ppt_to_ppt: 'Upload a reference PPT, then enter your content; Lantai ingests its structure, expression, and visual constraints',
        ppt_renovation: 'Upload an existing PDF/PPTX file; Lantai parses the legacy deck and rebuilds it through the harness',
      },
      placeholders: {
        no_think: 'e.g., AI tools onboarding workshop, lead with value before operations',
        agent: 'e.g., AI education startup investor pitch',
        idea: 'e.g., Generate a presentation about the history of AI',
        outline: 'Paste your PPT outline (required)...',
        description: 'Paste your complete page descriptions...',
        ppt_to_ppt: 'Paste your project content, work material, competition brief, or delivery constraints...',
      },
      content: {
        descriptionLabel: 'Slide descriptions (optional)',
        descriptionPlaceholder: 'Paste slide-by-slide content, layout, chart, or asset notes here',
        descriptionHint: 'Slide descriptions are for page content, layout, charts, and assets; the global visual style is controlled by the style template above.',
        emptyOutlineTip: 'No outline yet? Use Quick Harness to generate a full structure first',
        generateDescriptions: 'Generate slide descriptions from outline',
      },
      generation: {
        title: 'Generation Mode',
        fast: 'Fast generation',
        fastHint: 'Move quickly into outline, descriptions, and image generation',
        harness: 'Harness high-quality mode',
        harnessHint: 'Use a structured planning, QA, and page organization process',
        templateLabel: 'Harness Template',
        paperOperators: 'paper-operators',
      },
      examples: {
        outline: 'Recommended input (click to insert):\n\nPage 1: AI Origins\n- 1956 Dartmouth Conference\n- Early researchers\' vision\n\nPage 2: Evolution of Machine Learning\n- Shift from rule-based to data-driven\n- Overview of classic algorithms\n\nPage 3: Future Outlook\n- Trends and opportunities\n- Challenges and risks\n\nPage titles only is also supported. The AI will split by page headers and build structured outlines.',
        description: 'Recommended input (click to insert):\n\nPage 1: AI Origins\nPage content:\n- The 1956 Dartmouth Conference launched AI as a research field.\n- Suggest a cover style with timeline on the left and machine illustration on the right.\n\nPage 2: Evolution of Machine Learning\nPage content:\n- Explain the shift from rule-based methods to data-driven methods.\n- Add a central comparison chart and key milestones below.\n\nPage 3: Future Outlook\nPage content:\n- Summarize trends and opportunities.\n- Include notes for ethics and governance risks.',
        fillOutline: 'Insert outline sample',
        copyOutline: 'Copy outline sample',
        fillDescription: 'Insert slide description sample',
        copyDescription: 'Copy slide description sample',
      },
      template: {
        title: 'Select Style Template',
        useTextStyle: 'Use text description for style',
        useExternalSkill: 'Use external style Skill',
        externalSkillId: 'Skill ID',
        externalPrompt: 'External Skill output',
        externalPromptPlaceholder: 'Paste the visual system, style prompt, or JSON payload generated by the external Skill',
        externalHelper: 'When enabled, template images, text style, and global style words in page descriptions will not control visuals.',
      },
      noThink: {
        scenario: 'Scenario',
        density: 'Content density',
        pageCount: 'PPT pages',
        styleTemplate: 'Style direction',
        extraInstruction: 'Extra instruction',
        extraPlaceholder: 'e.g., for new hires, keep technical details light',
      },
      actions: {
        selectFile: 'Select reference file',
        parsing: 'Parsing...',
        createProject: 'Create New Project',
      },
      renovation: {
        uploadHint: 'Click or drag to upload PDF / PPTX file',
        formatHint: 'Supports .pdf, .pptx, .ppt formats (PDF recommended)',
        styleSource: 'Renovation style',
        reuseOriginalStyle: 'Reuse original style',
        chooseStyleTemplate: 'Select style template',
        onlyPdfPptx: 'Only PDF and PPTX files are supported',
        uploadFile: 'Please upload a PDF or PPTX file first',
        selectStyleTemplate: 'Please select a style template or enter a text style',
      },
      pptToPpt: {
        uploadHint: 'Click or drag to upload reference PDF / PPTX file',
        formatHint: 'The reference file is used to learn structure, layout, and expression',
        styleSource: 'Generation style',
        reuseReferenceStyle: 'Reuse reference PPT style',
        chooseStyleTemplate: 'Select style template',
        onlyPdfPptx: 'Only PDF and PPTX files are supported',
        uploadFile: 'Please upload a reference PDF or PPTX file first',
        selectStyleTemplate: 'Please select a style template or enter a text style',
      },
      messages: {
        enterContent: 'Please enter content',
        filesParsing: '{{count}} reference file(s) are still parsing, please wait',
        filesParseFailed: '{{count}} reference file(s) failed to parse. Delete or reparse them before creating the project',
        projectCreateFailed: 'Failed to create project',
        uploadingImage: 'Uploading and recognizing image...',
        imageUploadSuccess: 'Image uploaded! Inserted at cursor position',
        imageUploadFailed: 'Failed to upload image',
        fileUploadSuccess: 'File uploaded successfully',
        fileUploadFailed: 'Failed to upload file',
        fileTooLarge: 'File too large: {{size}}MB, maximum 200MB',
        fileUploadInProgress: 'A file upload is already in progress — please wait for it to finish',
        unsupportedFileType: 'Unsupported file type: {{type}}',
        pptTip: 'We recommend converting your PPTX to PDF locally before uploading for better compatibility and faster processing',
        filesAdded: 'Added {{count}} reference file(s)',
        imageRemoved: 'Image removed',
        outlineCopied: 'Outline sample copied to clipboard',
        descriptionCopied: 'Page description sample copied to clipboard',
        copyFailed: 'Copy failed, please copy manually',
        serviceTestTip: 'Test services in Settings first to avoid issues',
        verifying: 'Verifying API configuration...',
        verifyFailed: 'Please configure a valid API Key in Settings and click "Service Test" at the bottom to verify',
        externalSkillMissing: 'Enter an external style Skill ID or external Skill output',
      },
    },
  },
};

type GenerationModePanelProps = {
  generationMode: GenerationMode;
  harnessTemplate: HarnessTemplate;
  onGenerationModeChange: (mode: GenerationMode) => void;
  onHarnessTemplateChange: (template: HarnessTemplate) => void;
  t: (key: string) => string;
};

const GenerationModePanel: React.FC<GenerationModePanelProps> = ({
  generationMode,
  harnessTemplate,
  onGenerationModeChange,
  onHarnessTemplateChange,
  t,
}) => (
  <div className="mb-4 rounded-xl border border-gray-100 bg-white/60 p-3 dark:border-border-primary dark:bg-background-tertiary/60">
    <div className="mb-3 flex items-center gap-2">
      <Settings size={16} className="text-banana-600 dark:text-banana" />
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
        {t('home.generation.title')}
      </h3>
    </div>
    <div className="grid gap-2 sm:grid-cols-2">
      {([
        { value: 'fast' as GenerationMode, label: t('home.generation.fast'), hint: t('home.generation.fastHint') },
        { value: 'harness' as GenerationMode, label: t('home.generation.harness'), hint: t('home.generation.harnessHint') },
      ]).map((option) => {
        const active = generationMode === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onGenerationModeChange(option.value)}
            className={`min-h-[72px] rounded-lg border px-3 py-2 text-left transition ${
              active
                ? 'border-banana-400 bg-banana-50 text-gray-950 ring-2 ring-banana-100 dark:border-banana dark:bg-banana/10 dark:text-white dark:ring-banana/20'
                : 'border-gray-200 bg-white text-gray-700 hover:border-banana-300 dark:border-border-primary dark:bg-background-elevated dark:text-foreground-secondary dark:hover:border-banana/60'
            }`}
          >
            <span className="block text-sm font-semibold">{option.label}</span>
            <span className="mt-1 block text-xs leading-relaxed text-gray-500 dark:text-foreground-tertiary">{option.hint}</span>
          </button>
        );
      })}
    </div>
    {generationMode === 'harness' && (
      <label className="mt-3 block">
        <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
          {t('home.generation.templateLabel')}
        </span>
        <select
          value={harnessTemplate}
          onChange={(event) => onHarnessTemplateChange(event.target.value as HarnessTemplate)}
          className="h-9 w-full rounded-lg border border-gray-200 bg-white px-2 text-sm text-gray-800 outline-none transition focus:border-banana-400 focus:ring-2 focus:ring-banana-200 dark:border-border-primary dark:bg-background-elevated dark:text-foreground-primary dark:focus:border-banana"
        >
          <option value="paper_operators">{t('home.generation.paperOperators')}</option>
        </select>
      </label>
    )}
  </div>
);

export const Home: React.FC = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const t = useT(homeI18n); // 组件内翻译 + 自动 fallback 到全局
  const { theme, isDark, setTheme } = useTheme();
  const { initializeProject, isGlobalLoading } = useProjectStore();
  const { show, ToastContainer } = useToast();
  
  const [activeTab, setActiveTab] = useState<CreationType>('no_think');
  const [content, setContent] = useState('');
  const [pageDescriptions, setPageDescriptions] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<File | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedPresetTemplateId, setSelectedPresetTemplateId] = useState<string | null>(null);
  const [isMaterialModalOpen, setIsMaterialModalOpen] = useState(false);
  const [isMaterialCenterOpen, setIsMaterialCenterOpen] = useState(false);
  const [isThemeMenuOpen, setIsThemeMenuOpen] = useState(false);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [userTemplates, setUserTemplates] = useState<UserTemplate[]>([]);
  const [referenceFiles, setReferenceFiles] = useState<ReferenceFile[]>([]);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [isFileSelectorOpen, setIsFileSelectorOpen] = useState(false);
  const [previewFileId, setPreviewFileId] = useState<string | null>(null);

  const [useTemplateStyle, setUseTemplateStyle] = useState(false);
  const [templateStyle, setTemplateStyle] = useState('');
  const [useExternalStyleSkill, setUseExternalStyleSkill] = useState(false);
  const [externalStyleSkillId, setExternalStyleSkillId] = useState('');
  const [externalStylePrompt, setExternalStylePrompt] = useState('');
  const [generationMode, setGenerationMode] = useState<GenerationMode>('fast');
  const [harnessTemplate, setHarnessTemplate] = useState<HarnessTemplate>('paper_operators');
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [isAspectRatioOpen, setIsAspectRatioOpen] = useState(false);
  const [noThinkScenario, setNoThinkScenario] = useState(NO_THINK_SELECT_OPTIONS.scenario[0]);
  const [noThinkDensity, setNoThinkDensity] = useState(NO_THINK_SELECT_OPTIONS.density[0]);
  const [noThinkPageCount, setNoThinkPageCount] = useState('10');
  const [noThinkStyleTemplate, setNoThinkStyleTemplate] = useState(NO_THINK_SELECT_OPTIONS.styleTemplate[0]);
  const [noThinkExtraInstruction, setNoThinkExtraInstruction] = useState('');
  const [renovationFile, setRenovationFile] = useState<File | null>(null);
  const [pptToPptReferenceFile, setPptToPptReferenceFile] = useState<File | null>(null);
  const [pptToPptStyleSource, setPptToPptStyleSource] = useState<PptToPptStyleSource>('original');
  const [renovationStyleSource, setRenovationStyleSource] = useState<RenovationStyleSource>('original');
  const renovationFileInputRef = useRef<HTMLInputElement>(null);
  const pptToPptFileInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const themeMenuRef = useRef<HTMLDivElement>(null);
  const modePanelRef = useRef<HTMLDivElement>(null);
  const pendingModeScrollYRef = useRef<number | null>(null);
  const pointerModeScrollYRef = useRef<number | null>(null);
  const [modePanelMinHeight, setModePanelMinHeight] = useState<number | null>(null);

  // 持久化草稿到 sessionStorage，确保跳转设置页后返回时内容不丢失
  useEffect(() => {
    if (content) {
      sessionStorage.setItem('home-draft-content', content);
    }
  }, [content]);

  useEffect(() => {
    if (pageDescriptions) {
      sessionStorage.setItem('home-draft-page-descriptions', pageDescriptions);
    }
  }, [pageDescriptions]);

  useEffect(() => {
    sessionStorage.setItem('home-draft-tab', activeTab);
  }, [activeTab]);

  useLayoutEffect(() => {
    const panel = modePanelRef.current;
    if (panel) {
      const nextHeight = Math.ceil(panel.getBoundingClientRect().height);
      if (nextHeight > 0) {
        setModePanelMinHeight((currentHeight) => Math.max(currentHeight ?? 0, nextHeight));
      }
    }

    if (pendingModeScrollYRef.current !== null) {
      const scrollY = pendingModeScrollYRef.current;
      const restoreScroll = () => window.scrollTo(window.scrollX, scrollY);
      restoreScroll();
      window.requestAnimationFrame(() => {
        restoreScroll();
        window.requestAnimationFrame(restoreScroll);
        window.setTimeout(() => {
          restoreScroll();
          pendingModeScrollYRef.current = null;
          document.documentElement.style.removeProperty('overflow-anchor');
        }, 120);
      });
    }
  }, [activeTab]);


  // 检查是否有当前项目 & 加载用户模板
  useEffect(() => {
    const projectId = localStorage.getItem('currentProjectId');
    setCurrentProjectId(projectId);

    // 加载用户模板列表（用于按需获取File）
    const loadTemplates = async () => {
      try {
        const response = await listUserTemplates();
        if (response.data?.templates) {
          setUserTemplates(response.data.templates);
        }
      } catch (error) {
        console.error('加载用户模板失败:', error);
      }
    };
    loadTemplates();
  }, []);

  const handleOpenMaterialModal = () => {
    // 在主页始终生成全局素材，不关联任何项目
    setIsMaterialModalOpen(true);
  };

  const textareaRef = useRef<MarkdownTextareaRef>(null);
  const [isMaterialSelectorOpen, setIsMaterialSelectorOpen] = useState(false);

  // Callback to insert at cursor position in the textarea
  const insertAtCursor = useCallback((markdown: string) => {
    textareaRef.current?.insertAtCursor(markdown);
  }, []);

  // 图片粘贴使用统一 hook（批量支持，不对非图片文件发出警告，由下方 handlePaste 处理文档）
  const { handlePaste: handleImagePaste, handleFiles: handleImageFiles, isUploading: isUploadingImage } = useImagePaste({
    projectId: null,
    setContent,
    showToast: show,
    warnUnsupportedTypes: false,
    insertAtCursor,
  });

  const handleMaterialSelect = useCallback((materials: Material[]) => {
    const markdown = buildMaterialsMarkdown(materials, setContent);
    textareaRef.current?.insertAtCursor(markdown + '\n');
  }, [setContent]);

  // 检测粘贴事件，图片走 hook，文档走独立逻辑
  const handlePaste = async (e: React.ClipboardEvent<HTMLElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    // 分类：图片 vs 文档 vs 不支持
    let hasImages = false;
    const docFiles: File[] = [];
    const unsupportedExts: string[] = [];

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind !== 'file') continue;
      const file = item.getAsFile();
      if (!file) continue;

      if (file.type.startsWith('image/')) {
        hasImages = true;
      } else {
        const fileExt = file.name.split('.').pop()?.toLowerCase();
        if (fileExt && ALLOWED_DOC_EXTENSIONS.includes(fileExt)) {
          docFiles.push(file);
        } else {
          unsupportedExts.push(fileExt || file.type);
        }
      }
    }

    // 图片交给 hook 处理（批量上传）
    if (hasImages) {
      handleImagePaste(e);
    }

    // 文档文件逐个上传
    if (docFiles.length > 0) {
      if (!hasImages) e.preventDefault();
      for (const file of docFiles) {
        await handleFileUpload(file);
      }
    }

    // 不支持的文件类型提示
    if (unsupportedExts.length > 0 && !hasImages && docFiles.length === 0) {
      show({ message: t('home.messages.unsupportedFileType', { type: unsupportedExts.join(', ') }), type: 'info' });
    }
  };

  // 上传文件
  // 在 Home 页面，文件始终上传为全局文件（不关联项目），因为此时还没有项目
  const handleFileUpload = useCallback(async (file: File) => {
    if (isUploadingFile) return;

    // 检查文件大小（前端预检查）
    const maxSize = 200 * 1024 * 1024; // 200MB
    if (file.size > maxSize) {
      show({ 
        message: t('home.messages.fileTooLarge', { size: (file.size / 1024 / 1024).toFixed(1) }), 
        type: 'error' 
      });
      return;
    }

    // 检查是否是PPT文件，提示建议使用PDF
    const fileExt = file.name.split('.').pop()?.toLowerCase();
    if (fileExt === 'ppt' || fileExt === 'pptx') 
      show({ message: `💡 ${t('home.messages.pptTip')}`, type: 'info' });
    
    setIsUploadingFile(true);
    try {
      // 在 Home 页面，始终上传为全局文件
      const response = await uploadReferenceFile(file, null);
      if (response?.data?.file) {
        const uploadedFile = response.data.file;
        setReferenceFiles(prev => [...prev, uploadedFile]);
        show({ message: t('home.messages.fileUploadSuccess'), type: 'success' });
        
        // 如果文件状态为 pending，自动触发解析
        if (uploadedFile.parse_status === 'pending') {
          try {
            const parseResponse = await triggerFileParse(uploadedFile.id);
            // 使用解析接口返回的文件对象更新状态
            if (parseResponse?.data?.file) {
              const parsedFile = parseResponse.data.file;
              setReferenceFiles(prev => 
                prev.map(f => f.id === uploadedFile.id ? parsedFile : f)
              );
            } else {
              // 如果没有返回文件对象，手动更新状态为 parsing（异步线程会稍后更新）
              setReferenceFiles(prev => 
                prev.map(f => f.id === uploadedFile.id ? { ...f, parse_status: 'parsing' as const } : f)
              );
            }
          } catch (parseError: any) {
            console.error('触发文件解析失败:', parseError);
            // 解析触发失败不影响上传成功提示
          }
        }
      } else {
        show({ message: t('home.messages.fileUploadFailed'), type: 'error' });
      }
    } catch (error: any) {
      console.error('文件上传失败:', error);
      
      // 特殊处理413错误
      if (error?.response?.status === 413) {
        show({
          message: t('home.messages.fileTooLarge', { size: (file.size / 1024 / 1024).toFixed(1) }),
          type: 'error'
        });
      } else {
        show({
          message: `${t('home.messages.fileUploadFailed')}: ${error?.response?.data?.error?.message || error.message || ''}`.replace(/: $/, ''),
          type: 'error'
        });
      }
    } finally {
      setIsUploadingFile(false);
    }
  }, [isUploadingFile, show, t]);

  // 拖拽进来的文档文件：按扩展名过滤后复用 handleFileUpload（逐个上传+自动触发解析）
  const handleDocumentFiles = useCallback(async (files: File[]) => {
    // 已有上传在进行时告知用户，避免文件被静默丢弃（handleFileUpload 的 isUploadingFile 守卫）
    if (isUploadingFile) {
      show({ message: t('home.messages.fileUploadInProgress'), type: 'info' });
      return;
    }

    const accepted: File[] = [];
    const rejected: string[] = [];
    for (const file of files) {
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (ext && ALLOWED_DOC_EXTENSIONS.includes(ext)) {
        accepted.push(file);
      } else {
        rejected.push(ext || file.type || file.name);
      }
    }

    if (rejected.length > 0) {
      // 去重扩展名，避免一次拖入多个同类型不支持文件时 toast 重复冗长
      show({
        message: t('home.messages.unsupportedFileType', {
          type: Array.from(new Set(rejected)).join(', '),
        }),
        type: 'info',
      });
    }

    for (const file of accepted) {
      await handleFileUpload(file);
    }
  }, [isUploadingFile, handleFileUpload, show, t]);

  // 从当前项目移除文件引用（不删除文件本身）
  const handleFileRemove = (fileId: string) => {
    setReferenceFiles(prev => prev.filter(f => f.id !== fileId));
  };

  // 文件状态变化回调
  const handleFileStatusChange = (updatedFile: ReferenceFile) => {
    setReferenceFiles(prev => 
      prev.map(f => f.id === updatedFile.id ? updatedFile : f)
    );
  };

  // 点击回形针按钮 - 打开文件选择器
  const handlePaperclipClick = () => {
    setIsFileSelectorOpen(true);
  };

  // 从选择器选择文件后的回调
  const handleFilesSelected = (selectedFiles: ReferenceFile[]) => {
    // 合并新选择的文件到列表（去重）
    setReferenceFiles(prev => {
      const existingIds = new Set(prev.map(f => f.id));
      const newFiles = selectedFiles.filter(f => !existingIds.has(f.id));
      // 合并时，如果文件已存在，更新其状态（可能解析状态已改变）
      const updated = prev.map(f => {
        const updatedFile = selectedFiles.find(sf => sf.id === f.id);
        return updatedFile || f;
      });
      return [...updated, ...newFiles];
    });
    show({ message: t('home.messages.filesAdded', { count: selectedFiles.length }), type: 'success' });
  };

  // 获取当前已选择的文件ID列表，传递给选择器（使用 useMemo 避免每次渲染都重新计算）
  const selectedFileIds = useMemo(() => {
    return referenceFiles.map(f => f.id);
  }, [referenceFiles]);

  // 文件选择变化
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      await handleFileUpload(files[i]);
    }

    // 清空 input，允许重复选择同一文件
    e.target.value = '';
  };

  const tabConfig: Record<VisibleCreationType, {
    icon: React.ReactNode;
    label: string;
    placeholder: string;
    description: string;
    example: string | null;
  }> = {
    agent: {
      icon: <Sparkles size={20} />,
      label: t('home.tabs.agent'),
      placeholder: t('home.placeholders.agent'),
      description: t('home.tabDescriptions.agent'),
      example: null as string | null,
    },
    no_think: {
      icon: <Sparkles size={20} />,
      label: t('home.tabs.no_think'),
      placeholder: t('home.placeholders.no_think'),
      description: t('home.tabDescriptions.no_think'),
      example: null as string | null,
    },
    outline: {
      icon: <FileText size={20} />,
      label: t('home.tabs.outline'),
      placeholder: t('home.placeholders.outline'),
      description: t('home.tabDescriptions.outline'),
      example: t('home.examples.outline'),
    },
    ppt_to_ppt: {
      icon: <FileEdit size={20} />,
      label: t('home.tabs.ppt_to_ppt'),
      placeholder: t('home.placeholders.ppt_to_ppt'),
      description: t('home.tabDescriptions.ppt_to_ppt'),
      example: null as string | null,
    },
    ppt_renovation: {
      icon: <RefreshCw size={20} />,
      label: t('home.tabs.ppt_renovation'),
      placeholder: '',
      description: t('home.tabDescriptions.ppt_renovation'),
      example: null as string | null,
    },
  };
  const currentTabConfig = tabConfig[(activeTab in tabConfig ? activeTab : 'agent') as VisibleCreationType];

  const captureModePanelHeight = useCallback(() => {
    const panel = modePanelRef.current;
    if (!panel) return;

    const currentHeight = Math.ceil(panel.getBoundingClientRect().height);
    if (currentHeight > 0) {
      setModePanelMinHeight((savedHeight) => Math.max(savedHeight ?? 0, currentHeight));
    }
  }, []);

  const handleTabPointerDown = useCallback(() => {
    pointerModeScrollYRef.current = window.scrollY;
    captureModePanelHeight();
  }, [captureModePanelHeight]);

  const handleTabChange = useCallback((type: VisibleCreationType) => {
    if (type === activeTab) return;

    captureModePanelHeight();

    pendingModeScrollYRef.current = pointerModeScrollYRef.current ?? window.scrollY;
    pointerModeScrollYRef.current = null;
    document.documentElement.style.setProperty('overflow-anchor', 'none');
    setActiveTab(type);
  }, [activeTab, captureModePanelHeight]);

  const handleTemplateSelect = async (templateFile: File | null, templateId?: string) => {
    // 总是设置文件（如果提供）
    if (templateFile) {
      setSelectedTemplate(templateFile);
    }
    
    // 处理模板 ID
    if (templateId) {
      // 判断是用户模板还是预设模板
      // 预设模板 ID 通常是 '1', '2', '3' 等短字符串
      // 用户模板 ID 通常较长（UUID 格式）
      if (templateId.length <= 3 && /^\d+$/.test(templateId)) {
        // 预设模板
        setSelectedPresetTemplateId(templateId);
        setSelectedTemplateId(null);
      } else {
        // 用户模板
        setSelectedTemplateId(templateId);
        setSelectedPresetTemplateId(null);
      }
    } else {
      // 如果没有 templateId，可能是直接上传的文件
      // 清空所有选择状态
      setSelectedTemplateId(null);
      setSelectedPresetTemplateId(null);
    }
  };

  const [isSubmitting, setIsSubmitting] = useState(false);

  const isPdfOrPptFile = (file: File | null) => {
    if (!file) return false;
    const name = file.name.toLowerCase();
    return name.endsWith('.pdf') || name.endsWith('.pptx') || name.endsWith('.ppt');
  };

  const handlePptToPptReferenceFile = (file: File | null) => {
    if (!file) return;
    if (!isPdfOrPptFile(file)) {
      show({ message: t('home.pptToPpt.onlyPdfPptx'), type: 'error' });
      return;
    }
    setPptToPptReferenceFile(file);
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext === 'ppt' || ext === 'pptx') {
      show({ message: `💡 ${t('home.messages.pptTip')}`, type: 'info' });
    }
  };

  const canUseExternalStyleSkill = activeTab !== 'ppt_renovation' && activeTab !== 'ppt_to_ppt';
  const canUseGenerationMode = activeTab !== 'agent' && activeTab !== 'ppt_renovation' && activeTab !== 'ppt_to_ppt';
  const usesHarnessVisualStyle = canUseGenerationMode && generationMode === 'harness' && harnessTemplate === 'paper_operators';
  const externalStyleSkillEnabled = canUseExternalStyleSkill && useExternalStyleSkill && !usesHarnessVisualStyle;

  const buildExternalStylePayload = () => {
    const raw = externalStylePrompt.trim();
    if (!raw) {
      return undefined;
    }
    try {
      return JSON.parse(raw);
    } catch {
      return { style_prompt: raw };
    }
  };

  const handleSubmit = async (eventOrOptions?: React.MouseEvent | { generateDescriptionsFromOutline?: boolean }) => {
    const generateDescriptionsFromOutline = Boolean(
      eventOrOptions &&
      'generateDescriptionsFromOutline' in eventOrOptions &&
      eventOrOptions.generateDescriptionsFromOutline
    );
    // For ppt_renovation, validate file instead of content
    if (activeTab === 'ppt_renovation') {
      if (!renovationFile) {
        show({ message: t('home.renovation.uploadFile'), type: 'error' });
        return;
      }
    } else if (activeTab === 'ppt_to_ppt') {
      if (!pptToPptReferenceFile) {
        show({ message: t('home.pptToPpt.uploadFile'), type: 'error' });
        return;
      }
      if (!content.trim()) {
        show({ message: t('home.messages.enterContent'), type: 'error' });
        return;
      }
      if (pptToPptStyleSource === 'template' && !selectedTemplate && !selectedTemplateId && !selectedPresetTemplateId && !templateStyle.trim()) {
        show({ message: t('home.pptToPpt.selectStyleTemplate'), type: 'error' });
        return;
      }
    } else if (activeTab === 'outline' && !content.trim()) {
      show({ message: t('home.content.emptyOutlineTip'), type: 'error' });
      return;
    } else if (activeTab !== 'no_think' && !content.trim()) {
      show({ message: t('home.messages.enterContent'), type: 'error' });
      return;
    }

    if (externalStyleSkillEnabled && !externalStyleSkillId.trim() && !externalStylePrompt.trim()) {
      show({ message: t('home.messages.externalSkillMissing'), type: 'error' });
      return;
    }

    // 检查是否有正在解析的文件
    const parsingFiles = referenceFiles.filter(f =>
      f.parse_status === 'pending' || f.parse_status === 'parsing'
    );
    if (parsingFiles.length > 0) {
      show({
        message: t('home.messages.filesParsing', { count: parsingFiles.length }),
        type: 'info'
      });
      return;
    }

    const failedFiles = referenceFiles.filter(f => f.parse_status === 'failed');
    if (failedFiles.length > 0) {
      show({
        message: t('home.messages.filesParseFailed', { count: failedFiles.length }),
        type: 'error',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      // PPT 翻新模式：走独立的上传+异步解析流程
      if (activeTab === 'ppt_renovation' && renovationFile) {
        let templateFile = selectedTemplate;
        if (!templateFile && (selectedTemplateId || selectedPresetTemplateId)) {
          const templateId = selectedTemplateId || selectedPresetTemplateId;
          if (templateId) {
            templateFile = await getTemplateFile(templateId, userTemplates);
          }
        }

        const useTemplateForRenovation = renovationStyleSource === 'template';
        const styleDesc = useTemplateForRenovation && templateStyle.trim() ? templateStyle.trim() : undefined;
        if (useTemplateForRenovation && !templateFile && !styleDesc) {
          show({ message: t('home.renovation.selectStyleTemplate'), type: 'error' });
          return;
        }

        const result = await createPptRenovationProject(renovationFile, {
          keepLayout: renovationStyleSource === 'original',
          templateStyle: styleDesc,
          templateImage: useTemplateForRenovation ? templateFile || undefined : undefined,
        });

        const projectId = result.data?.project_id;
        const taskId = result.data?.task_id;
        if (!projectId) {
          show({ message: t('home.messages.projectCreateFailed'), type: 'error' });
          return;
        }

        // Save project ID and task ID for DetailEditor to poll
        localStorage.setItem('currentProjectId', projectId);
        if (taskId) {
          localStorage.setItem('renovationTaskId', taskId);
        }

        // Clear draft
        sessionStorage.removeItem('home-draft-content');
        sessionStorage.removeItem('home-draft-page-descriptions');
        sessionStorage.removeItem('home-draft-tab');

        // Navigate to detail editor (will poll for task completion with skeleton UI)
        navigate(`/project/${projectId}/detail`);
        return;
      }

      if (activeTab === 'ppt_to_ppt' && pptToPptReferenceFile) {
        let templateFile = selectedTemplate;
        if (!templateFile && (selectedTemplateId || selectedPresetTemplateId)) {
          const templateId = selectedTemplateId || selectedPresetTemplateId;
          if (templateId) {
            templateFile = await getTemplateFile(templateId, userTemplates);
          }
        }

        const result = await createPptToPptProject(pptToPptReferenceFile, content.trim(), {
          contentType: 'notes',
          matchStrength: 'balanced',
          referenceScope: 'structure_and_style',
          styleSource: pptToPptStyleSource,
          templateStyle: pptToPptStyleSource === 'template' ? templateStyle.trim() || undefined : undefined,
          templateImage: pptToPptStyleSource === 'template' ? templateFile || undefined : undefined,
        });

        const projectId = result.data?.project_id;
        const taskId = result.data?.task_id;
        if (!projectId) {
          show({ message: t('home.messages.projectCreateFailed'), type: 'error' });
          return;
        }

        localStorage.setItem('currentProjectId', projectId);
        if (taskId) {
          localStorage.setItem('renovationTaskId', taskId);
        }

        sessionStorage.removeItem('home-draft-content');
        sessionStorage.removeItem('home-draft-page-descriptions');
        sessionStorage.removeItem('home-draft-tab');

        navigate(`/project/${projectId}/detail`);
        return;
      }

      // 如果有模板ID但没有File，按需加载
      let templateFile = selectedTemplate;
      if (!templateFile && (selectedTemplateId || selectedPresetTemplateId)) {
        const templateId = selectedTemplateId || selectedPresetTemplateId;
        if (templateId) {
          templateFile = await getTemplateFile(templateId, userTemplates);
        }
      }
      
      // External style Skill is mutually exclusive with native template/style inputs.
      const styleDesc = !externalStyleSkillEnabled && !usesHarnessVisualStyle && templateStyle.trim() ? templateStyle.trim() : undefined;
      const templateForProject = externalStyleSkillEnabled || usesHarnessVisualStyle ? undefined : templateFile || undefined;
      const visualOptions = externalStyleSkillEnabled
        ? {
            visual_strategy: 'external_skill' as const,
            external_style_skill_id: externalStyleSkillId.trim() || undefined,
            external_style_payload: buildExternalStylePayload(),
          }
        : {
            visual_strategy: 'native' as const,
          };

      // 传递参考文件ID列表，确保 AI 生成时能读取参考文件内容
      const refFileIds = referenceFiles
        .filter(f => f.parse_status === 'completed')
        .map(f => f.id);
      const submittedContent = activeTab === 'no_think' && !content.trim()
        ? `${noThinkScenario} PPT`
        : content;

      const noThinkOptions = activeTab === 'no_think'
        ? {
            scenario: noThinkScenario,
            density: noThinkDensity,
            page_count: noThinkPageCount.trim() ? `${noThinkPageCount.trim()}页` : undefined,
            style_template: noThinkStyleTemplate,
            extra_instruction: noThinkExtraInstruction.trim() || undefined,
          }
        : undefined;
      const generationOptions = canUseGenerationMode
        ? {
            generation_mode: generationMode,
            harness_template: generationMode === 'harness' ? harnessTemplate : undefined,
          }
        : undefined;

      await initializeProject(
        activeTab as 'no_think' | 'idea' | 'outline' | 'description',
        submittedContent,
        templateForProject,
        styleDesc,
        refFileIds.length > 0 ? refFileIds : undefined,
        aspectRatio,
        noThinkOptions,
        activeTab === 'outline' ? pageDescriptions : undefined,
        activeTab === 'outline' ? generateDescriptionsFromOutline : false,
        visualOptions,
        generationOptions
      );
      
      // 根据类型跳转到不同页面
      const projectId = localStorage.getItem('currentProjectId');
      if (!projectId) {
        show({ message: t('home.messages.projectCreateFailed'), type: 'error' });
        return;
      }
      
      // 关联未完成解析的参考文件（已完成的在 initializeProject 中关联）
      if (referenceFiles.length > 0) {
        const unassociatedFiles = referenceFiles.filter(f => f.parse_status !== 'completed');
        if (unassociatedFiles.length > 0) {
          devLog(`Associating ${unassociatedFiles.length} remaining reference files to project ${projectId}:`, unassociatedFiles);
          try {
            await Promise.all(
              unassociatedFiles.map(async file => {
                const response = await associateFileToProject(file.id, projectId);
                return response;
              })
            );
          } catch (error) {
            console.error('Failed to associate reference files:', error);
          }
        }
      }
      
      // 关联图片素材到项目（解析content中的markdown图片链接）
      const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
      const materialSource = `${submittedContent}\n${activeTab === 'outline' ? pageDescriptions : ''}`;
      const materialUrls: string[] = [];
      let match;
      while ((match = imageRegex.exec(materialSource)) !== null) {
        materialUrls.push(match[2]); // match[2] 是 URL
      }
      
      if (materialUrls.length > 0) {
        devLog(`Associating ${materialUrls.length} materials to project ${projectId}:`, materialUrls);
        try {
          const response = await associateMaterialsToProject(projectId, materialUrls);
          devLog('Materials associated successfully:', response);
        } catch (error) {
          console.error('Failed to associate materials:', error);
          // 不影响主流程，继续执行
        }
      } else {
        devLog('No materials to associate');
      }
      
      if (activeTab === 'outline' && (pageDescriptions.trim() || generateDescriptionsFromOutline)) {
        navigate(`/project/${projectId}/detail`);
      } else if (activeTab === 'idea' || activeTab === 'outline') {
        navigate(`/project/${projectId}/outline`);
      } else if (activeTab === 'description' || activeTab === 'no_think') {
        // 从描述/No Think 生成：直接跳到详情页（后端已生成页面描述）
        navigate(`/project/${projectId}/detail`);
      }
    } catch (error: any) {
      console.error('创建项目失败:', error);
      const msg = error?.response?.data?.error?.message || error?.message || t('home.messages.projectCreateFailed');
      show({ message: msg, type: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const noThinkSelects = [
    {
      label: t('home.noThink.scenario'),
      value: noThinkScenario,
      onChange: setNoThinkScenario,
      options: NO_THINK_SELECT_OPTIONS.scenario,
    },
    {
      label: t('home.noThink.density'),
      value: noThinkDensity,
      onChange: setNoThinkDensity,
      options: NO_THINK_SELECT_OPTIONS.density,
    },
    {
      label: t('home.noThink.styleTemplate'),
      value: noThinkStyleTemplate,
      onChange: setNoThinkStyleTemplate,
      options: NO_THINK_SELECT_OPTIONS.styleTemplate,
    },
  ];

  const copyTextToClipboard = async (text: string, copiedMessage: string) => {
    try {
      if (!text) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        show({ message: copiedMessage, type: 'success' });
        return;
      }
    } catch (error) {
      console.error('复制失败:', error);
    }

    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.top = '0';
      textarea.style.left = '0';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const copied = document.execCommand('copy');
      document.body.removeChild(textarea);
      if (copied) {
        show({ message: copiedMessage, type: 'success' });
      } else {
        throw new Error('execCommand copy failed');
      }
    } catch (error) {
      console.error('复制失败:', error);
      show({ message: t('home.messages.copyFailed'), type: 'error' });
    }
  };

  const fillOutlineSample = () => {
    setContent(t('home.examples.outline'));
  };

  const fillDescriptionSample = () => {
    setPageDescriptions(t('home.examples.description'));
  };

  return (
    <div className="app-surface min-h-screen dark:bg-background-primary relative overflow-hidden">

      {/* 导航栏 */}
      <nav className="app-chrome relative z-50 h-16 md:h-18 border-b">

        <div className="max-w-7xl mx-auto px-4 md:px-6 h-full flex items-center justify-between">
          <div className="flex min-w-0 items-center">
            <img
              src="/lantai-deck-agent-logo.png"
              alt="兰台 DeckAgent AI Presentation Agent Logo"
              className="h-11 w-[178px] object-contain object-left md:h-14 md:w-[290px] lg:w-[360px]"
            />
          </div>
          <div className="flex items-center gap-2 md:gap-3">
            {/* 桌面端：带文字的素材生成按钮 */}
            <Button
              variant="ghost"
              size="sm"
              icon={<ImagePlus size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={handleOpenMaterialModal}
              className="hidden sm:inline-flex hover:bg-banana-100/60 hover:shadow-sm hover:scale-105 transition-all duration-200 font-medium"
            >
              <span className="hidden md:inline">{t('nav.materialGenerate')}</span>
            </Button>
            {/* 手机端：仅图标的素材生成按钮 */}
            <Button
              variant="ghost"
              size="sm"
              icon={<ImagePlus size={16} />}
              onClick={handleOpenMaterialModal}
              className="sm:hidden hover:bg-banana-100/60 hover:shadow-sm hover:scale-105 transition-all duration-200"
              title={t('nav.materialGenerate')}
            />
            {/* 桌面端：带文字的素材中心按钮 */}
            <Button
              variant="ghost"
              size="sm"
              icon={<FolderOpen size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={() => setIsMaterialCenterOpen(true)}
              className="hidden sm:inline-flex hover:bg-banana-100/60 hover:shadow-sm hover:scale-105 transition-all duration-200 font-medium"
            >
              <span className="hidden md:inline">{t('nav.materialCenter')}</span>
            </Button>
            {/* 手机端：仅图标的素材中心按钮 */}
            <Button
              variant="ghost"
              size="sm"
              icon={<FolderOpen size={16} />}
              onClick={() => setIsMaterialCenterOpen(true)}
              className="sm:hidden hover:bg-banana-100/60 hover:shadow-sm hover:scale-105 transition-all duration-200"
              title={t('nav.materialCenter')}
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/history')}
              className="text-xs md:text-sm hover:bg-banana-100/60 hover:shadow-sm hover:scale-105 transition-all duration-200 font-medium"
            >
              <span className="hidden sm:inline">{t('nav.history')}</span>
              <span className="sm:hidden">{t('nav.history')}</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={<Settings size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={() => navigate('/settings')}
              className="text-xs md:text-sm hover:bg-banana-100/60 hover:shadow-sm hover:scale-105 transition-all duration-200 font-medium"
            >
              <span className="hidden md:inline">{t('nav.settings')}</span>
            </Button>
            {/* 分隔线 */}
            <div className="h-5 w-px bg-gray-300 dark:bg-border-primary mx-1" />
            {/* 语言切换按钮 */}
            <button
              onClick={() => i18n.changeLanguage(i18n.language?.startsWith('zh') ? 'en' : 'zh')}
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-600 dark:text-foreground-tertiary hover:text-gray-900 dark:hover:text-gray-100 hover:bg-banana-100/60 dark:hover:bg-background-hover rounded-md transition-all"
              title={t('settings.language.label')}
            >
              <Globe size={14} />
              <span>{i18n.language?.startsWith('zh') ? 'EN' : '中'}</span>
            </button>
            {/* 主题切换按钮 */}
            <div className="relative" ref={themeMenuRef}>
              <button
                onClick={() => setIsThemeMenuOpen(!isThemeMenuOpen)}
                className="flex items-center gap-1 p-1.5 text-gray-600 dark:text-foreground-tertiary hover:text-gray-900 dark:hover:text-gray-100 hover:bg-banana-100/60 dark:hover:bg-background-hover rounded-md transition-all"
                title={t('settings.theme.label')}
              >
                {theme === 'system' ? <Monitor size={16} /> : isDark ? <Moon size={16} /> : <Sun size={16} />}
                <ChevronDown size={12} className={`transition-transform ${isThemeMenuOpen ? 'rotate-180' : ''}`} />
              </button>
              {/* 主题下拉菜单 */}
              {isThemeMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setIsThemeMenuOpen(false)} />
                  <div className="absolute right-0 top-full mt-1 z-50 bg-white dark:bg-background-secondary border border-gray-200 dark:border-border-primary rounded-lg shadow-lg dark:shadow-none py-1 min-w-[120px]">
                    <button
                      onClick={() => { setTheme('light'); setIsThemeMenuOpen(false); }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-background-hover transition-colors ${theme === 'light' ? 'text-banana' : 'text-gray-700 dark:text-foreground-secondary'}`}
                    >
                      <Sun size={14} />
                      <span>{t('settings.theme.light')}</span>
                    </button>
                    <button
                      onClick={() => { setTheme('dark'); setIsThemeMenuOpen(false); }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-background-hover transition-colors ${theme === 'dark' ? 'text-banana' : 'text-gray-700 dark:text-foreground-secondary'}`}
                    >
                      <Moon size={14} />
                      <span>{t('settings.theme.dark')}</span>
                    </button>
                    <button
                      onClick={() => { setTheme('system'); setIsThemeMenuOpen(false); }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-background-hover transition-colors ${theme === 'system' ? 'text-banana' : 'text-gray-700 dark:text-foreground-secondary'}`}
                    >
                      <Monitor size={14} />
                      <span>{t('settings.theme.system')}</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容 */}
      <main className="relative max-w-5xl mx-auto px-3 md:px-4 py-8 md:py-12">
        {/* Hero 标题区 */}
        <div className="text-center mb-10 md:mb-16 space-y-4 md:space-y-6">
          {/*<div className="inline-flex items-center gap-2 px-4 py-2 bg-[#121212] text-white dark:bg-background-secondary backdrop-blur-sm rounded-full shadow-sm dark:shadow-none mb-4">*/}
          {/*  <span className="text-sm font-medium text-white/85 dark:text-foreground-secondary">{t('home.tagline')}</span>*/}
          {/*</div>*/}

          <h1 className="text-4xl md:text-6xl lg:text-7xl font-extrabold leading-tight">
            <span className="bg-gradient-to-r from-[#121212] via-[#84cc16] to-[#AFFF00] dark:from-banana-dark dark:via-banana dark:to-banana-light bg-clip-text text-transparent dark:italic" style={{
              backgroundSize: '200% auto',
              animation: 'gradient 3s ease infinite',
            }}>
              {i18n.language?.startsWith('zh') ? `${t('home.title')} · PPT Agent` : 'Lantai PPT Agent'}
            </span>
          </h1>

          <p className="text-lg md:text-xl text-gray-600 dark:text-foreground-secondary max-w-2xl mx-auto font-light">
            {t('home.subtitle')}
          </p>

          {/* 特性标签 */}
          <div className="flex flex-wrap items-center justify-center gap-2 md:gap-3 pt-4">
            {[
              { icon: <Sparkles size={14} className="text-yellow-600 dark:text-banana" />, label: t('home.features.oneClick') },
              { icon: <FileEdit size={14} className="text-blue-500 dark:text-blue-400" />, label: t('home.features.naturalEdit') },
              { icon: <Search size={14} className="text-orange-500 dark:text-orange-400" />, label: t('home.features.regionEdit') },

              { icon: <Paperclip size={14} className="text-green-600 dark:text-green-400" />, label: t('home.features.export') },
            ].map((feature, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-white/70 dark:bg-background-secondary backdrop-blur-sm rounded-full text-xs md:text-sm text-gray-700 dark:text-foreground-secondary border border-gray-200/50 dark:border-border-primary shadow-sm dark:shadow-none hover:shadow-md dark:hover:border-border-hover transition-all hover:scale-105 cursor-default"
              >
                {feature.icon}
                {feature.label}
              </span>
            ))}
          </div>
        </div>

        {/* 创建卡片 */}
        <Card className="p-4 md:p-10 bg-white/90 dark:bg-background-secondary backdrop-blur-xl dark:backdrop-blur-none shadow-2xl dark:shadow-none border-0 dark:border dark:border-border-primary hover:shadow-3xl dark:hover:shadow-none transition-all duration-300 dark:rounded-2xl">
          {/* 选项卡 */}
          <div className="grid grid-cols-2 gap-1.5 rounded-2xl border border-gray-200/70 bg-gray-100/70 p-1.5 shadow-inner dark:border-border-primary dark:bg-background-tertiary/80 sm:grid-cols-4 md:gap-2 mb-6 md:mb-8">
            {(Object.keys(tabConfig) as VisibleCreationType[]).map((type) => {
              const config = tabConfig[type];
              const isActive = activeTab === type;
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={isActive}
                  onPointerDown={handleTabPointerDown}
                  onClick={() => handleTabChange(type)}
                  className={`home-mode-tab group relative flex min-h-[48px] items-center justify-center gap-1.5 overflow-hidden rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-300 ease-out touch-manipulation md:gap-2 md:px-4 md:py-3 md:text-base ${
                    isActive
                      ? 'bg-white text-gray-950 shadow-sm ring-1 ring-black/5 dark:bg-background-elevated dark:text-white dark:ring-white/10'
                      : 'text-gray-600 hover:bg-white/70 hover:text-gray-950 dark:text-foreground-secondary dark:hover:bg-background-hover dark:hover:text-white'
                  }`}
                >
                  <span
                    className={`pointer-events-none absolute inset-x-3 top-1 h-0.5 origin-center rounded-full bg-banana-500 transition-all duration-300 dark:bg-banana ${
                      isActive ? 'scale-x-100 opacity-100' : 'scale-x-0 opacity-0'
                    }`}
                  />
                  <span className={`scale-90 transition-transform duration-300 md:scale-100 ${isActive ? 'text-banana-700 dark:text-banana' : 'group-hover:scale-100'}`}>
                    {config.icon}
                  </span>
                  <span className="truncate">{config.label}</span>
                </button>
              );
            })}
          </div>

          <div
            ref={modePanelRef}
            className="transition-[min-height] duration-300 ease-out"
            style={modePanelMinHeight ? { minHeight: modePanelMinHeight } : undefined}
          >
            <div key={activeTab} className="home-mode-panel">
              {/* 描述 */}
              <div className="relative">
                <p className="text-sm md:text-base mb-4 md:mb-6 leading-relaxed">
                  <span className="inline-flex items-center gap-2 text-gray-600 dark:text-foreground-tertiary">
                    <Lightbulb size={16} className="text-banana-600 dark:text-banana flex-shrink-0" />
                    <span className="font-semibold">
                      {currentTabConfig.description}
                    </span>
                    {currentTabConfig.example && (
                      <span className="relative group/tip inline-flex">
                        <HelpCircle size={15} className="text-gray-400 dark:text-foreground-tertiary hover:text-banana-600 dark:hover:text-banana cursor-help transition-colors" />
                        <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover/tip:block z-50 w-72 md:w-80 p-3 bg-white dark:bg-background-elevated border border-gray-200 dark:border-border-primary rounded-lg shadow-xl dark:shadow-none text-xs text-gray-700 dark:text-foreground-secondary whitespace-pre-line leading-relaxed">
                          {currentTabConfig.example}
                          <span className="absolute left-1/2 -translate-x-1/2 top-full -mt-px w-2 h-2 bg-white dark:bg-background-elevated border-r border-b border-gray-200 dark:border-border-primary rotate-45" />
                        </span>
                      </span>
                    )}
                  </span>
                </p>
              </div>

              {/* 输入区 - 带工具栏 */}
              <div className="mb-2">
            {activeTab === 'agent' ? (
              <AgentModePanel onOpenProject={(projectId) => navigate(`/project/${projectId}/detail`)} />
            ) : activeTab === 'ppt_to_ppt' ? (
              <div className="space-y-4">
                <div
                  className="border-2 border-dashed border-gray-300 dark:border-border-primary rounded-xl p-8 text-center cursor-pointer hover:border-banana-400 dark:hover:border-banana transition-colors duration-200"
                  onClick={() => pptToPptFileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handlePptToPptReferenceFile(e.dataTransfer.files[0] || null);
                  }}
                >
                  {pptToPptReferenceFile ? (
                    <div className="flex items-center justify-center gap-3">
                      <FileText size={24} className="text-banana-600 dark:text-banana" />
                      <div className="text-left">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">{pptToPptReferenceFile.name}</p>
                        <p className="text-xs text-gray-500 dark:text-foreground-tertiary">{(pptToPptReferenceFile.size / 1024 / 1024).toFixed(1)} MB</p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setPptToPptReferenceFile(null); }}
                        className="ml-2 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        x
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Upload size={32} className="mx-auto text-gray-400 dark:text-foreground-tertiary" />
                      <p className="text-sm text-gray-600 dark:text-foreground-secondary">{t('home.pptToPpt.uploadHint')}</p>
                      <p className="text-xs text-gray-400 dark:text-foreground-tertiary">{t('home.pptToPpt.formatHint')}</p>
                    </div>
                  )}
                </div>
                <input
                  ref={pptToPptFileInputRef}
                  type="file"
                  accept=".pdf,.pptx,.ppt"
                  onChange={(e) => {
                    handlePptToPptReferenceFile(e.target.files?.[0] || null);
                    e.target.value = '';
                  }}
                  className="hidden"
                />
                <div>
                  <p className="mb-2 text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
                    {t('home.pptToPpt.styleSource')}
                  </p>
                  <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1 dark:border-border-primary dark:bg-background-elevated">
                    {([
                      ['original', t('home.pptToPpt.reuseReferenceStyle')],
                      ['template', t('home.pptToPpt.chooseStyleTemplate')],
                    ] as const).map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setPptToPptStyleSource(value)}
                        className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                          pptToPptStyleSource === value
                            ? 'bg-banana-500 text-black shadow-sm dark:bg-banana'
                            : 'text-gray-600 hover:bg-gray-100 dark:text-foreground-secondary dark:hover:bg-background-hover'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <MarkdownTextarea
                  ref={textareaRef}
                  placeholder={currentTabConfig.placeholder}
                  value={content}
                  onChange={setContent}
                  onPaste={handlePaste}
                  onFiles={handleImageFiles}
                  onDocumentFiles={handleDocumentFiles}
                  onSelectFromLibrary={() => setIsMaterialSelectorOpen(true)}
                  rows={8}
                  className="text-sm md:text-base border-2 border-gray-200 dark:border-border-primary dark:bg-background-tertiary dark:text-white focus-within:border-banana-400 dark:focus-within:border-banana transition-colors duration-200"
                  toolbarRight={
                    <Button
                      size="sm"
                      onClick={handleSubmit}
                      loading={isSubmitting || isGlobalLoading}
                      disabled={!pptToPptReferenceFile}
                      className="shadow-sm dark:shadow-background-primary/30 text-xs md:text-sm px-3 md:px-4"
                    >
                      {t('common.next')}
                    </Button>
                  }
                />
              </div>
            ) : activeTab === 'ppt_renovation' ? (
              /* PPT 翻新：文件上传区 */
              <div className="space-y-4">
                <div
                  className="border-2 border-dashed border-gray-300 dark:border-border-primary rounded-xl p-8 text-center cursor-pointer hover:border-banana-400 dark:hover:border-banana transition-colors duration-200"
                  onClick={() => renovationFileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const file = e.dataTransfer.files[0];
                    if (file && (file.name.toLowerCase().endsWith('.pdf') || file.name.toLowerCase().endsWith('.pptx') || file.name.toLowerCase().endsWith('.ppt'))) {
                      setRenovationFile(file);
                      const ext = file.name.split('.').pop()?.toLowerCase();
                      if (ext === 'ppt' || ext === 'pptx') {
                        show({ message: `💡 ${t('home.messages.pptTip')}`, type: 'info' });
                      }
                    } else {
                      show({ message: t('home.renovation.onlyPdfPptx'), type: 'error' });
                    }
                  }}
                >
                  {renovationFile ? (
                    <div className="flex items-center justify-center gap-3">
                      <FileText size={24} className="text-banana-600 dark:text-banana" />
                      <div className="text-left">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">{renovationFile.name}</p>
                        <p className="text-xs text-gray-500 dark:text-foreground-tertiary">{(renovationFile.size / 1024 / 1024).toFixed(1)} MB</p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setRenovationFile(null); }}
                        className="ml-2 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Upload size={32} className="mx-auto text-gray-400 dark:text-foreground-tertiary" />
                      <p className="text-sm text-gray-600 dark:text-foreground-secondary">{t('home.renovation.uploadHint')}</p>
                      <p className="text-xs text-gray-400 dark:text-foreground-tertiary">{t('home.renovation.formatHint')}</p>
                    </div>
                  )}
                </div>
                <input
                  ref={renovationFileInputRef}
                  type="file"
                  accept=".pdf,.pptx,.ppt"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setRenovationFile(file);
                      const ext = file.name.split('.').pop()?.toLowerCase();
                      if (ext === 'ppt' || ext === 'pptx') {
                        show({ message: `💡 ${t('home.messages.pptTip')}`, type: 'info' });
                      }
                    }
                    e.target.value = '';
                  }}
                  className="hidden"
                />

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="mb-2 text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
                      {t('home.renovation.styleSource')}
                    </p>
                    <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1 dark:border-border-primary dark:bg-background-elevated">
                      {([
                        ['original', t('home.renovation.reuseOriginalStyle')],
                        ['template', t('home.renovation.chooseStyleTemplate')],
                      ] as const).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setRenovationStyleSource(value)}
                          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                            renovationStyleSource === value
                              ? 'bg-banana-500 text-black shadow-sm dark:bg-banana'
                              : 'text-gray-600 hover:bg-gray-100 dark:text-foreground-secondary dark:hover:bg-background-hover'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={handleSubmit}
                    loading={isSubmitting || isGlobalLoading}
                    disabled={!renovationFile}
                    className="shadow-sm dark:shadow-background-primary/30 text-xs md:text-sm px-3 md:px-4"
                  >
                    {t('common.next')}
                  </Button>
                </div>
              </div>
            ) : (
            <>
            {canUseGenerationMode && (
              <GenerationModePanel
                generationMode={generationMode}
                harnessTemplate={harnessTemplate}
                onGenerationModeChange={setGenerationMode}
                onHarnessTemplateChange={setHarnessTemplate}
                t={t}
              />
            )}
            {activeTab === 'outline' && (
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={fillOutlineSample}
                  className="shrink-0"
                >
                  {t('home.examples.fillOutline')}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => copyTextToClipboard(t('home.examples.outline'), t('home.messages.outlineCopied'))}
                  className="shrink-0"
                >
                  {t('home.examples.copyOutline')}
                </Button>
              </div>
            )}
            <MarkdownTextarea
              ref={textareaRef}
              placeholder={currentTabConfig.placeholder}
              value={content}
              onChange={setContent}
              onPaste={handlePaste}
              onFiles={handleImageFiles}
              onDocumentFiles={handleDocumentFiles}
              onSelectFromLibrary={() => setIsMaterialSelectorOpen(true)}
              rows={8}
              className="text-sm md:text-base border-2 border-gray-200 dark:border-border-primary dark:bg-background-tertiary dark:text-white focus-within:border-banana-400 dark:focus-within:border-banana transition-colors duration-200"
              toolbarLeft={
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={handlePaperclipClick}
                    className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-foreground-tertiary dark:hover:text-foreground-secondary dark:hover:bg-background-hover rounded transition-colors active:scale-95 touch-manipulation"
                    title={t('home.actions.selectFile')}
                  >
                    <Paperclip size={18} />
                  </button>
                  {/* 画面比例选择 */}
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsAspectRatioOpen(!isAspectRatioOpen)}
                      className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-foreground-tertiary dark:hover:text-foreground-secondary dark:hover:bg-background-hover rounded transition-colors"
                      title={i18n.language?.startsWith('zh') ? '画面比例' : 'Aspect Ratio'}
                    >
                      <span>{aspectRatio}</span>
                      <ChevronDown size={12} className={`transition-transform ${isAspectRatioOpen ? 'rotate-180' : ''}`} />
                    </button>
                    {isAspectRatioOpen && (
                      <>
                        <div className="fixed inset-0 z-40" onClick={() => setIsAspectRatioOpen(false)} />
                        <div className="absolute left-0 bottom-full mb-1 z-50 bg-white dark:bg-background-elevated border border-gray-200 dark:border-border-primary rounded-lg shadow-lg dark:shadow-none py-1 min-w-[80px]">
                          {ASPECT_RATIO_OPTIONS.map((opt) => (
                            <button
                              key={opt.value}
                              onClick={() => { setAspectRatio(opt.value); setIsAspectRatioOpen(false); }}
                              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 dark:hover:bg-background-hover transition-colors ${aspectRatio === opt.value ? 'text-banana font-semibold' : 'text-gray-700 dark:text-foreground-secondary'}`}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              }
              toolbarRight={
                <Button
                  size="sm"
                  onClick={handleSubmit}
                  loading={isSubmitting || isGlobalLoading}
                  disabled={
                    isUploadingImage ||
                    referenceFiles.some(f => f.parse_status === 'pending' || f.parse_status === 'parsing')
                  }
                  className="shadow-sm dark:shadow-background-primary/30 text-xs md:text-sm px-3 md:px-4"
                >
                  {referenceFiles.some(f => f.parse_status === 'pending' || f.parse_status === 'parsing')
                    ? t('home.actions.parsing')
                    : t('common.next')}
                </Button>
              }
            />
            {activeTab === 'no_think' && (
              <div className="mt-4 rounded-xl border border-gray-100 bg-white/60 p-3 dark:border-border-primary dark:bg-background-tertiary/60">
                <div className="mb-3 flex items-center gap-2">
                  <Sparkles size={16} className="text-banana-600 dark:text-banana" />
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                    快速 Harness
                  </h3>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {noThinkSelects.map((field) => (
                    <label key={field.label} className="block">
                      <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
                        {field.label}
                      </span>
                      <select
                        value={field.value}
                        onChange={(event) => field.onChange(event.target.value)}
                        className="h-9 w-full rounded-lg border border-gray-200 bg-white px-2 text-sm text-gray-800 outline-none transition focus:border-banana-400 focus:ring-2 focus:ring-banana-200 dark:border-border-primary dark:bg-background-elevated dark:text-foreground-primary dark:focus:border-banana"
                      >
                        {field.options.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
                      {t('home.noThink.pageCount')}
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={80}
                      step={1}
                      value={noThinkPageCount}
                      onChange={(event) => setNoThinkPageCount(event.target.value)}
                      className="h-9 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-banana-400 focus:ring-2 focus:ring-banana-200 dark:border-border-primary dark:bg-background-elevated dark:text-foreground-primary dark:focus:border-banana"
                    />
                  </label>
                  <label className="block sm:col-span-2 lg:col-span-4">
                    <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
                      {t('home.noThink.extraInstruction')}
                    </span>
                    <input
                      type="text"
                      value={noThinkExtraInstruction}
                      onChange={(event) => setNoThinkExtraInstruction(event.target.value)}
                      placeholder={t('home.noThink.extraPlaceholder')}
                      className="h-9 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition placeholder:text-gray-400 focus:border-banana-400 focus:ring-2 focus:ring-banana-200 dark:border-border-primary dark:bg-background-elevated dark:text-foreground-primary dark:placeholder:text-foreground-tertiary dark:focus:border-banana"
                    />
                  </label>
                </div>
              </div>
            )}
            {activeTab === 'outline' && (
              <div className="mt-4 rounded-xl border border-gray-200 bg-white/70 p-3 dark:border-border-primary dark:bg-background-tertiary/60">
                <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <label className="block text-sm font-semibold text-gray-800 dark:text-foreground-primary">
                      {t('home.content.descriptionLabel')}
                    </label>
                    <p className="mt-1 text-xs text-gray-500 dark:text-foreground-tertiary">
                      {t('home.content.descriptionHint')}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleSubmit({ generateDescriptionsFromOutline: true })}
                    loading={isSubmitting || isGlobalLoading}
                    disabled={
                      isUploadingImage ||
                      referenceFiles.some(f => f.parse_status === 'pending' || f.parse_status === 'parsing')
                    }
                    className="shrink-0 text-xs md:text-sm"
                  >
                    {t('home.content.generateDescriptions')}
                  </Button>
                </div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={fillDescriptionSample}
                    className="shrink-0"
                  >
                    {t('home.examples.fillDescription')}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => copyTextToClipboard(t('home.examples.description'), t('home.messages.descriptionCopied'))}
                    className="shrink-0"
                  >
                    {t('home.examples.copyDescription')}
                  </Button>
                </div>
                <textarea
                  value={pageDescriptions}
                  onChange={(event) => setPageDescriptions(event.target.value)}
                  onPaste={handlePaste}
                  placeholder={t('home.content.descriptionPlaceholder')}
                  rows={6}
                  className="w-full resize-y rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm leading-relaxed text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-banana-400 focus:ring-2 focus:ring-banana-200 dark:border-border-primary dark:bg-background-elevated dark:text-white dark:focus:border-banana"
                />
              </div>
            )}
            </>
            )}
          </div>

          {/* 隐藏的文件输入 */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.txt,.md"
            onChange={handleFileSelect}
            className="hidden"
          />

          <ReferenceFileList
            files={referenceFiles}
            onFileClick={setPreviewFileId}
            onFileDelete={handleFileRemove}
            onFileStatusChange={handleFileStatusChange}
            deleteMode="remove"
            className="mb-4"
            showToast={show}
          />

          {/* 模板选择 */}
          {(
            activeTab !== 'agent' && !usesHarnessVisualStyle && (
              (activeTab !== 'ppt_renovation' && activeTab !== 'ppt_to_ppt') ||
              (activeTab === 'ppt_renovation' && renovationStyleSource === 'template') ||
              (activeTab === 'ppt_to_ppt' && pptToPptStyleSource === 'template')
            )
          ) && (
            <div className="mb-6 md:mb-8 pt-4 border-t border-gray-100 dark:border-border-primary">
              <div className="flex flex-col gap-3 mb-3 md:mb-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <Palette size={18} className="text-orange-600 dark:text-banana flex-shrink-0" />
                  <h3 className="text-base md:text-lg font-semibold text-gray-900 dark:text-white">
                    {t('home.template.title')}
                  </h3>
                </div>
                <div className="flex flex-wrap items-center gap-4">
                  {canUseExternalStyleSkill && (
                    <label className="flex items-center gap-2 cursor-pointer group">
                      <span className="text-sm text-gray-600 dark:text-foreground-tertiary group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                        {t('home.template.useExternalSkill')}
                      </span>
                      <div className="relative">
                        <input
                          type="checkbox"
                          checked={useExternalStyleSkill}
                          onChange={(e) => {
                            setUseExternalStyleSkill(e.target.checked);
                            if (e.target.checked) {
                              setUseTemplateStyle(false);
                              setSelectedTemplate(null);
                              setSelectedTemplateId(null);
                              setSelectedPresetTemplateId(null);
                            }
                          }}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 dark:bg-background-hover peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-banana-300 dark:peer-focus:ring-banana/30 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white dark:after:bg-foreground-secondary after:border-gray-300 dark:after:border-border-hover after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-banana"></div>
                      </div>
                    </label>
                  )}
                  {!externalStyleSkillEnabled && (
                    <label className="flex items-center gap-2 cursor-pointer group">
                      <span className="text-sm text-gray-600 dark:text-foreground-tertiary group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                        {t('home.template.useTextStyle')}
                      </span>
                      <div className="relative">
                        <input
                          type="checkbox"
                          checked={useTemplateStyle}
                          onChange={(e) => {
                            setUseTemplateStyle(e.target.checked);
                            if (e.target.checked) {
                              setSelectedTemplate(null);
                              setSelectedTemplateId(null);
                              setSelectedPresetTemplateId(null);
                            }
                          }}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 dark:bg-background-hover peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-banana-300 dark:peer-focus:ring-banana/30 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white dark:after:bg-foreground-secondary after:border-gray-300 dark:after:border-border-hover after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-banana"></div>
                      </div>
                    </label>
                  )}
                </div>
                </div>

                {/* 根据模式显示不同的内容 */}
                {externalStyleSkillEnabled ? (
                <div className="space-y-3 rounded-lg border border-dashed border-orange-200 bg-orange-50/40 p-3 dark:border-banana/30 dark:bg-banana/5">
                  <p className="text-xs text-gray-600 dark:text-foreground-tertiary">
                    {t('home.template.externalHelper')}
                  </p>
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
                      {t('home.template.externalSkillId')}
                    </span>
                    <input
                      type="text"
                      value={externalStyleSkillId}
                      onChange={(event) => setExternalStyleSkillId(event.target.value)}
                      placeholder="ppt-style-pro"
                      className="h-9 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition placeholder:text-gray-400 focus:border-banana-400 focus:ring-2 focus:ring-banana-200 dark:border-border-primary dark:bg-background-elevated dark:text-foreground-primary dark:placeholder:text-foreground-tertiary dark:focus:border-banana"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-foreground-tertiary">
                      {t('home.template.externalPrompt')}
                    </span>
                    <textarea
                      value={externalStylePrompt}
                      onChange={(event) => setExternalStylePrompt(event.target.value)}
                      placeholder={t('home.template.externalPromptPlaceholder')}
                      rows={4}
                      className="w-full resize-y rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none transition placeholder:text-gray-400 focus:border-banana-400 focus:ring-2 focus:ring-banana-200 dark:border-border-primary dark:bg-background-elevated dark:text-foreground-primary dark:placeholder:text-foreground-tertiary dark:focus:border-banana"
                    />
                  </label>
                </div>
              ) : useTemplateStyle ? (
                <TextStyleSelector
                  value={templateStyle}
                  onChange={setTemplateStyle}
                  onToast={show}
                />
              ) : (
                <TemplateSelector
                  onSelect={handleTemplateSelect}
                  selectedTemplateId={selectedTemplateId}
                  selectedPresetTemplateId={selectedPresetTemplateId}
                  showUpload={true} // 在主页上传的模板保存到用户模板库
                  projectId={currentProjectId}
                />
              )}
            </div>
          )}
            </div>
          </div>

        </Card>
      </main>
      <ToastContainer />
      {/* 素材生成模态 - 在主页始终生成全局素材 */}
      <MaterialGeneratorModal
        projectId={null}
        isOpen={isMaterialModalOpen}
        onClose={() => setIsMaterialModalOpen(false)}
      />
      {/* 素材中心模态 */}
      <MaterialCenterModal
        isOpen={isMaterialCenterOpen}
        onClose={() => setIsMaterialCenterOpen(false)}
      />
      {/* 从素材库选择插入到文本框 */}
      <MaterialSelector
        isOpen={isMaterialSelectorOpen}
        onClose={() => setIsMaterialSelectorOpen(false)}
        onSelect={handleMaterialSelect}
        multiple
      />
      {/* 参考文件选择器 */}
      {/* 在 Home 页面，始终查询全局文件，因为此时还没有项目 */}
      <ReferenceFileSelector
        projectId={null}
        isOpen={isFileSelectorOpen}
        onClose={() => setIsFileSelectorOpen(false)}
        onSelect={handleFilesSelected}
        multiple={true}
        initialSelectedIds={selectedFileIds}
      />
      
      <FilePreviewModal fileId={previewFileId} onClose={() => setPreviewFileId(null)} />
      {/* Footer */}
      <Footer />
    </div>
  );
};
