import React, { useMemo, useState } from 'react';
import { ArrowLeft, BookOpen, Check, Copy, KeyRound, ShieldCheck } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import { Button } from '@/components/shared';
import { useT } from '@/hooks/useT';

const apiDocsI18n = {
  zh: {
    docs: {
      back: '返回环境配置',
      eyebrow: '开发者文档',
      title: '已有大纲 → 逐页描述 → 图片',
      subtitle: '通过一个异步 API 任务，把结构化 PPT 大纲转换为逐页描述和完整页图片。',
      version: '版本 v1',
      async: '异步任务',
      scope: '权限 ppt:generate',
      toc: '文档导航',
      nav: {
        overview: '概览', auth: '身份认证', submit: '提交生成',
        status: '查询状态', results: '获取结果', templates: '模板列表',
        errors: '错误处理', limits: '当前边界',
      },
      overviewTitle: '概览',
      overviewBody: '该接口只处理你已经准备好的大纲，不会重新生成大纲。后端会依次生成每页详细描述和页面图片，并使用 API 密钥所属账号的模型配置、用户模板和积分。',
      baseUrl: 'Base URL',
      flow: '调用流程',
      flowText: '1. 提交任务  →  2. 轮询状态  →  3. 读取逐页结果和图片',
      authTitle: '身份认证',
      authBody: '在环境配置页创建 API 密钥，然后使用 Bearer 认证。密钥明文只显示一次，不要放在浏览器代码、公开仓库或日志中。',
      authHeader: '请求头',
      submitTitle: '提交生成任务',
      submitMethod: 'POST /v1/ppt-generations',
      submitBody: '请求成功后返回 202 Accepted 和 generation_id。建议每次业务请求携带唯一 Idempotency-Key，网络重试时不会重复创建任务和扣除积分。',
      requestExample: '请求示例',
      fields: '核心参数',
      field: '字段', required: '必填', description: '说明',
      yes: '是', no: '否',
      fieldOutline: '大纲页面数组，1–30 页。每页 title 必填，points 为字符串数组，part 可选。',
      fieldTitle: '任务和项目名称，省略时使用第一页标题。',
      fieldVisual: '视觉设置：template_id、style、aspect_ratio。如都未指定，使用默认商务风格。',
      fieldOptions: '生成设置：language、detail_level、harness_template 和额外要求。',
      accepted: '202 响应示例',
      statusTitle: '查询任务状态',
      statusMethod: 'GET /v1/ppt-generations/{generation_id}',
      statusBody: '建议从 2–5 秒间隔开始轮询，并采用退避策略。当 status 变为 COMPLETED、PARTIAL 或 FAILED 时停止轮询。',
      statuses: '状态值',
      statusQueued: '已入队，等待执行。',
      statusProcessing: '正在生成逐页描述或图片。',
      statusCompleted: '全部页面生成成功。',
      statusPartial: '部分页面失败，仍可读取已生成结果。',
      statusFailed: '任务失败，查看 error_message。',
      resultsTitle: '获取逐页结果',
      resultsMethod: 'GET /v1/ppt-generations/{generation_id}/pages',
      resultsBody: '结果包含原大纲、生成的 description 和受保护的图片地址。请在下载图片时继续携带同一 Bearer 密钥。',
      imageDownload: '下载图片',
      templatesTitle: '查询用户模板',
      templatesMethod: 'GET /v1/templates',
      templatesBody: '返回密钥所属账号的模板列表。将 template_id 写入提交请求的 visual.template_id 即可使用。',
      errorsTitle: '错误处理',
      errorBody: '所有错误使用统一 JSON 格式。应用应同时判断 HTTP 状态码和 error.code，不要仅依赖人类可读的 message。',
      commonErrors: '常见状态码',
      error400: '参数结构或取值无效。',
      error401: '密钥缺失、无效、过期或已撤销。',
      error402: '账号积分不足，任务未创建。',
      error403: '密钥缺少 ppt:generate 权限。',
      error404: '任务、页面、图片或模板不存在，或不属于当前账号。',
      error409: '同一 Idempotency-Key 被用于不同请求体。',
      error500: '服务端执行异常。',
      limitsTitle: '当前版本边界',
      limits: '单次最多 30 页；任务为异步执行；暂不提供 webhook、取消和公开 API 重试接口。任务和返回的图片只能被同一账号的有效密钥访问。',
      copy: '复制', copied: '已复制',
    },
  },
  en: {
    docs: {
      back: 'Back to settings', eyebrow: 'Developer docs',
      title: 'Existing outline → slide descriptions → images',
      subtitle: 'Turn a structured PPT outline into detailed slide descriptions and full-slide images through one asynchronous API job.',
      version: 'Version v1', async: 'Async jobs', scope: 'Scope ppt:generate', toc: 'On this page',
      nav: { overview: 'Overview', auth: 'Authentication', submit: 'Submit generation', status: 'Check status', results: 'Get results', templates: 'List templates', errors: 'Errors', limits: 'Current limits' },
      overviewTitle: 'Overview', overviewBody: 'This API starts from an outline you already prepared; it does not regenerate the outline. It creates detailed descriptions and page images in sequence, using the API key owner\'s model settings, templates, and credits.',
      baseUrl: 'Base URL', flow: 'Request flow', flowText: '1. Submit job  →  2. Poll status  →  3. Read pages and images',
      authTitle: 'Authentication', authBody: 'Create an API key in Settings and use Bearer authentication. The plaintext key is shown only once. Never expose it in browser code, public repositories, or logs.', authHeader: 'Request header',
      submitTitle: 'Submit a generation job', submitMethod: 'POST /v1/ppt-generations', submitBody: 'A successful request returns 202 Accepted and a generation_id. Send a unique Idempotency-Key for each business request so network retries do not create duplicate jobs or charges.', requestExample: 'Request example', fields: 'Core parameters', field: 'Field', required: 'Required', description: 'Description', yes: 'Yes', no: 'No',
      fieldOutline: 'Array of 1–30 outline pages. Each page requires title; points is a string array and part is optional.', fieldTitle: 'Job and project title. Defaults to the first page title.', fieldVisual: 'Visual settings: template_id, style, and aspect_ratio. A default business style is used when none is provided.', fieldOptions: 'Generation settings: language, detail_level, harness_template, and extra requirements.', accepted: '202 response example',
      statusTitle: 'Check job status', statusMethod: 'GET /v1/ppt-generations/{generation_id}', statusBody: 'Start polling every 2–5 seconds and apply backoff. Stop when status becomes COMPLETED, PARTIAL, or FAILED.', statuses: 'Status values', statusQueued: 'Queued and waiting to run.', statusProcessing: 'Generating descriptions or images.', statusCompleted: 'All pages completed.', statusPartial: 'Some pages failed; completed results remain available.', statusFailed: 'The job failed. Inspect error_message.',
      resultsTitle: 'Get page results', resultsMethod: 'GET /v1/ppt-generations/{generation_id}/pages', resultsBody: 'Results include the original outline, generated description, and protected image URL. Continue sending the same Bearer key when downloading images.', imageDownload: 'Download an image',
      templatesTitle: 'List user templates', templatesMethod: 'GET /v1/templates', templatesBody: 'Returns templates owned by the API key account. Pass a template_id as visual.template_id when submitting a job.',
      errorsTitle: 'Errors', errorBody: 'All errors use one JSON format. Check both the HTTP status and error.code; do not depend only on the human-readable message.', commonErrors: 'Common status codes', error400: 'Invalid request structure or value.', error401: 'Key missing, invalid, expired, or revoked.', error402: 'Insufficient account credits; no job was created.', error403: 'Key lacks the ppt:generate scope.', error404: 'Job, page, image, or template does not exist or belongs to another account.', error409: 'The same Idempotency-Key was used with a different body.', error500: 'Server-side execution error.',
      limitsTitle: 'Current version limits', limits: 'Up to 30 pages per request. Jobs run asynchronously. Webhooks, cancellation, and a public retry endpoint are not yet available. Jobs and returned images are accessible only with a valid key from the same account.', copy: 'Copy', copied: 'Copied',
    },
  },
};

interface CodeBlockProps {
  code: string;
  label?: string;
  copyLabel: string;
  copiedLabel: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ code, label, copyLabel, copiedLabel }) => {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="overflow-hidden rounded-lg border border-gray-800 bg-[#111514]">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-gray-400">{label || 'code'}</span>
        <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 text-xs text-gray-300 transition hover:text-white">
          {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          {copied ? copiedLabel : copyLabel}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-[12px] leading-6 text-gray-200"><code>{code}</code></pre>
    </div>
  );
};

const DocSection: React.FC<React.PropsWithChildren<{ id: string; title: string; endpoint?: string }>> = ({ id, title, endpoint, children }) => (
  <section id={id} className="scroll-mt-24 border-t border-gray-200 py-10 first:border-t-0 first:pt-0 dark:border-border-primary">
    <div className="mb-5">
      <h2 className="text-xl font-semibold text-gray-950 dark:text-foreground-primary">{title}</h2>
      {endpoint && <code className="mt-2 inline-block rounded bg-gray-100 px-2 py-1 font-mono text-sm text-emerald-800 dark:bg-background-hover dark:text-emerald-300">{endpoint}</code>}
    </div>
    {children}
  </section>
);

export const ApiDocsPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const t = useT(apiDocsI18n);
  const baseUrl = typeof window === 'undefined' ? 'https://your-domain.example' : window.location.origin;
  const backTarget = (location.state as { from?: string } | null)?.from || '/settings';

  const examples = useMemo(() => {
    const submit = `curl --request POST '${baseUrl}/v1/ppt-generations' \\
  --header 'Authorization: Bearer lt_live_xxx.yyy' \\
  --header 'Content-Type: application/json' \\
  --header 'Idempotency-Key: deck-20260723-001' \\
  --data-raw '{
    "title": "2026 年产品战略",
    "outline": [
      {
        "part": "开场",
        "title": "封面",
        "points": ["从产品价值到增长路径"]
      },
      {
        "part": "现状",
        "title": "我们面对的核心问题",
        "points": ["产品体验不一致", "获客成本持续上升"]
      },
      {
        "part": "策略",
        "title": "三个关键行动",
        "points": ["聚焦核心场景", "建立可复用能力", "统一增长指标"]
      }
    ],
    "visual": {
      "template_id": null,
      "style": "现代科技感，深色背景，绿色强调色，克制专业",
      "aspect_ratio": "16:9"
    },
    "options": {
      "language": "zh",
      "detail_level": "default",
      "description_requirements": "每页突出一个主要观点",
      "extra_requirements": "避免大段文字"
    }
  }'`;

    const accepted = `{
  "success": true,
  "message": "Generation queued",
  "data": {
    "generation_id": "20bb03c9-873c-4fce-b9f6-31018bb9ab32",
    "status": "QUEUED",
    "current_stage": "descriptions",
    "project_id": "e984b44f-3b70-42fb-84db-e3f3f9a3cc24",
    "error_message": null,
    "links": {
      "self": "/v1/ppt-generations/20bb03c9-873c-4fce-b9f6-31018bb9ab32",
      "pages": "/v1/ppt-generations/20bb03c9-873c-4fce-b9f6-31018bb9ab32/pages"
    }
  }
}`;

    const status = `curl '${baseUrl}/v1/ppt-generations/{generation_id}' \\
  --header 'Authorization: Bearer lt_live_xxx.yyy'`;

    const pages = `curl '${baseUrl}/v1/ppt-generations/{generation_id}/pages' \\
  --header 'Authorization: Bearer lt_live_xxx.yyy'`;

    const pagesResponse = `{
  "success": true,
  "data": {
    "generation_id": "20bb03c9-873c-4fce-b9f6-31018bb9ab32",
    "status": "COMPLETED",
    "pages": [
      {
        "page_id": "82610443-2dbf-4b84-9e8b-7f0280b465b4",
        "index": 1,
        "part": "开场",
        "title": "封面",
        "points": ["从产品价值到增长路径"],
        "description": "深色科技感封面……",
        "image": {
          "url": "/v1/ppt-generations/{generation_id}/pages/82610443-2dbf-4b84-9e8b-7f0280b465b4/image"
        },
        "status": "COMPLETED"
      }
    ]
  }
}`;

    const image = `curl '${baseUrl}/v1/ppt-generations/{generation_id}/pages/{page_id}/image' \\
  --header 'Authorization: Bearer lt_live_xxx.yyy' \\
  --output slide-01.png`;

    const templates = `curl '${baseUrl}/v1/templates' \\
  --header 'Authorization: Bearer lt_live_xxx.yyy'`;

    const error = `{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "outline page 1 requires title"
  }
}`;

    return { submit, accepted, status, pages, pagesResponse, image, templates, error };
  }, [baseUrl]);

  const navItems = [
    ['overview', t('docs.nav.overview')], ['authentication', t('docs.nav.auth')],
    ['submit', t('docs.nav.submit')], ['status', t('docs.nav.status')],
    ['results', t('docs.nav.results')], ['templates', t('docs.nav.templates')],
    ['errors', t('docs.nav.errors')], ['limits', t('docs.nav.limits')],
  ];

  const codeLabels = { copyLabel: t('docs.copy'), copiedLabel: t('docs.copied') };

  return (
    <div className="app-surface min-h-screen bg-gray-50 dark:bg-background-primary">
      <header className="sticky top-0 z-30 border-b border-gray-200 bg-white/95 backdrop-blur dark:border-border-primary dark:bg-background-primary/95">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6">
          <Button type="button" variant="ghost" size="sm" icon={<ArrowLeft size={17} />} onClick={() => navigate(backTarget)}>
            {t('docs.back')}
          </Button>
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-foreground-primary">
            <BookOpen size={17} className="text-emerald-600 dark:text-emerald-400" />
            API v1
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-10 md:px-6 md:py-14">
        <div className="border-b border-gray-200 pb-10 dark:border-border-primary">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-400">{t('docs.eyebrow')}</p>
          <h1 className="mt-3 max-w-4xl text-3xl font-bold tracking-tight text-gray-950 dark:text-foreground-primary md:text-5xl">{t('docs.title')}</h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-gray-600 dark:text-foreground-secondary md:text-lg">{t('docs.subtitle')}</p>
          <div className="mt-6 flex flex-wrap gap-2 text-xs font-medium">
            {[t('docs.version'), t('docs.async'), t('docs.scope')].map((label) => (
              <span key={label} className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-gray-700 dark:border-border-primary dark:bg-background-secondary dark:text-foreground-secondary">{label}</span>
            ))}
          </div>
        </div>

        <div className="mt-10 grid gap-10 lg:grid-cols-[190px_minmax(0,1fr)]">
          <aside className="hidden lg:block">
            <nav className="sticky top-24">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-foreground-tertiary">{t('docs.toc')}</p>
              <div className="space-y-1 border-l border-gray-200 dark:border-border-primary">
                {navItems.map(([id, label]) => (
                  <a key={id} href={`#${id}`} className="block border-l-2 border-transparent px-3 py-1.5 text-sm text-gray-600 transition hover:border-emerald-500 hover:text-gray-950 dark:text-foreground-secondary dark:hover:text-white">{label}</a>
                ))}
              </div>
            </nav>
          </aside>

          <main className="min-w-0">
            <DocSection id="overview" title={t('docs.overviewTitle')}>
              <p className="leading-7 text-gray-600 dark:text-foreground-secondary">{t('docs.overviewBody')}</p>
              <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-foreground-tertiary">{t('docs.baseUrl')}</p>
                  <code className="mt-2 block overflow-x-auto border-l-2 border-emerald-500 bg-emerald-50 px-3 py-2 font-mono text-sm text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">{baseUrl}</code>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-foreground-tertiary">{t('docs.flow')}</p>
                  <p className="mt-2 text-sm leading-6 text-gray-700 dark:text-foreground-secondary">{t('docs.flowText')}</p>
                </div>
              </div>
            </DocSection>

            <DocSection id="authentication" title={t('docs.authTitle')}>
              <div className="flex gap-3 border-l-4 border-emerald-500 bg-emerald-50 px-4 py-4 dark:bg-emerald-950/25">
                <ShieldCheck className="mt-0.5 shrink-0 text-emerald-700 dark:text-emerald-300" size={20} />
                <p className="text-sm leading-6 text-emerald-950 dark:text-emerald-100">{t('docs.authBody')}</p>
              </div>
              <div className="mt-5"><CodeBlock code="Authorization: Bearer lt_live_xxx.yyy" label={t('docs.authHeader')} {...codeLabels} /></div>
              <Button type="button" variant="secondary" size="sm" icon={<KeyRound size={16} />} onClick={() => navigate('/settings')} className="mt-4">{t('docs.back')}</Button>
            </DocSection>

            <DocSection id="submit" title={t('docs.submitTitle')} endpoint={t('docs.submitMethod')}>
              <p className="leading-7 text-gray-600 dark:text-foreground-secondary">{t('docs.submitBody')}</p>
              <h3 className="mb-3 mt-6 text-sm font-semibold text-gray-900 dark:text-foreground-primary">{t('docs.requestExample')}</h3>
              <CodeBlock code={examples.submit} label="curl" {...codeLabels} />

              <h3 className="mb-3 mt-8 text-sm font-semibold text-gray-900 dark:text-foreground-primary">{t('docs.fields')}</h3>
              <div className="overflow-x-auto border-y border-gray-200 dark:border-border-primary">
                <table className="w-full min-w-[620px] text-left text-sm">
                  <thead className="bg-gray-100/70 text-xs uppercase tracking-wider text-gray-500 dark:bg-background-secondary dark:text-foreground-tertiary">
                    <tr><th className="px-3 py-3">{t('docs.field')}</th><th className="px-3 py-3">{t('docs.required')}</th><th className="px-3 py-3">{t('docs.description')}</th></tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 text-gray-700 dark:divide-border-primary dark:text-foreground-secondary">
                    {[
                      ['outline', t('docs.yes'), t('docs.fieldOutline')], ['title', t('docs.no'), t('docs.fieldTitle')],
                      ['visual', t('docs.no'), t('docs.fieldVisual')], ['options', t('docs.no'), t('docs.fieldOptions')],
                    ].map(([field, required, description]) => (
                      <tr key={field}><td className="px-3 py-3 align-top font-mono text-emerald-800 dark:text-emerald-300">{field}</td><td className="px-3 py-3 align-top">{required}</td><td className="px-3 py-3 leading-6">{description}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3 className="mb-3 mt-8 text-sm font-semibold text-gray-900 dark:text-foreground-primary">{t('docs.accepted')}</h3>
              <CodeBlock code={examples.accepted} label="json" {...codeLabels} />
            </DocSection>

            <DocSection id="status" title={t('docs.statusTitle')} endpoint={t('docs.statusMethod')}>
              <p className="mb-5 leading-7 text-gray-600 dark:text-foreground-secondary">{t('docs.statusBody')}</p>
              <CodeBlock code={examples.status} label="curl" {...codeLabels} />
              <h3 className="mb-3 mt-7 text-sm font-semibold text-gray-900 dark:text-foreground-primary">{t('docs.statuses')}</h3>
              <dl className="divide-y divide-gray-200 border-y border-gray-200 text-sm dark:divide-border-primary dark:border-border-primary">
                {[
                  ['QUEUED', t('docs.statusQueued')], ['PROCESSING', t('docs.statusProcessing')], ['COMPLETED', t('docs.statusCompleted')],
                  ['PARTIAL', t('docs.statusPartial')], ['FAILED', t('docs.statusFailed')],
                ].map(([status, description]) => (
                  <div key={status} className="grid gap-1 py-3 sm:grid-cols-[130px_1fr]"><dt className="font-mono text-xs font-semibold text-emerald-800 dark:text-emerald-300">{status}</dt><dd className="text-gray-600 dark:text-foreground-secondary">{description}</dd></div>
                ))}
              </dl>
            </DocSection>

            <DocSection id="results" title={t('docs.resultsTitle')} endpoint={t('docs.resultsMethod')}>
              <p className="mb-5 leading-7 text-gray-600 dark:text-foreground-secondary">{t('docs.resultsBody')}</p>
              <CodeBlock code={examples.pages} label="curl" {...codeLabels} />
              <div className="mt-5"><CodeBlock code={examples.pagesResponse} label="json" {...codeLabels} /></div>
              <h3 className="mb-3 mt-7 text-sm font-semibold text-gray-900 dark:text-foreground-primary">{t('docs.imageDownload')}</h3>
              <CodeBlock code={examples.image} label="curl" {...codeLabels} />
            </DocSection>

            <DocSection id="templates" title={t('docs.templatesTitle')} endpoint={t('docs.templatesMethod')}>
              <p className="mb-5 leading-7 text-gray-600 dark:text-foreground-secondary">{t('docs.templatesBody')}</p>
              <CodeBlock code={examples.templates} label="curl" {...codeLabels} />
            </DocSection>

            <DocSection id="errors" title={t('docs.errorsTitle')}>
              <p className="mb-5 leading-7 text-gray-600 dark:text-foreground-secondary">{t('docs.errorBody')}</p>
              <CodeBlock code={examples.error} label="json" {...codeLabels} />
              <h3 className="mb-3 mt-7 text-sm font-semibold text-gray-900 dark:text-foreground-primary">{t('docs.commonErrors')}</h3>
              <dl className="divide-y divide-gray-200 border-y border-gray-200 text-sm dark:divide-border-primary dark:border-border-primary">
                {['400', '401', '402', '403', '404', '409', '500'].map((code) => (
                  <div key={code} className="grid gap-1 py-3 sm:grid-cols-[70px_1fr]"><dt className="font-mono font-semibold text-gray-900 dark:text-foreground-primary">{code}</dt><dd className="text-gray-600 dark:text-foreground-secondary">{t(`docs.error${code}`)}</dd></div>
                ))}
              </dl>
            </DocSection>

            <DocSection id="limits" title={t('docs.limitsTitle')}>
              <p className="border-l-4 border-amber-400 bg-amber-50 px-4 py-4 text-sm leading-7 text-amber-950 dark:bg-amber-950/25 dark:text-amber-100">{t('docs.limits')}</p>
            </DocSection>
          </main>
        </div>
      </div>
    </div>
  );
};
