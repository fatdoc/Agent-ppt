import React, { useState } from 'react';
import { createAgentModePlan, generateAgentRemainingSlides, generateAgentStylePreview, setAgentSlideLock, updateAgentSlideContent, updateAgentSlideVisualPlan, type AgentModeDeckVersion } from '@/api/endpoints';
import { Button, useToast } from '@/components/shared';

interface AgentModePanelProps {
  onOpenProject: (projectId: string) => void;
}

export const AgentModePanel: React.FC<AgentModePanelProps> = ({ onOpenProject }) => {
  const { show } = useToast();
  const [topic, setTopic] = useState('AI 教育产品融资路演');
  const [audience, setAudience] = useState('投资人');
  const [pageCount, setPageCount] = useState(8);
  const [style, setStyle] = useState('Paper Operators 纸片人，中文标签清晰，适合路演正文页');
  const [plan, setPlan] = useState<AgentModeDeckVersion | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewTaskId, setPreviewTaskId] = useState<string | null>(null);
  const [batchTaskId, setBatchTaskId] = useState<string | null>(null);

  const createPlan = async () => {
    setLoading(true);
    try {
      const response = await createAgentModePlan({
        topic,
        audience,
        page_count: pageCount,
        style,
        generation_mode: 'harness',
        harness_template: 'paper_operators',
      });
      if (response.data) {
        setPlan(response.data);
        show({ message: 'Agent 计划已生成，请先确认计划和风格验证页', type: 'success' });
      }
    } catch (error) {
      show({ message: error instanceof Error ? error.message : 'Agent 计划生成失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const updateSlide = async (slide: Record<string, any>, patch: Record<string, any>) => {
    if (!plan) return;
    const nextPlan = { ...slide.slide_plan, ...patch };
    const response = await updateAgentSlideContent(plan.project_id, plan.deck_version_id, slide.slide_version_id, nextPlan);
    if (response.data) {
      setPlan({ ...plan, slides: plan.slides.map((item) => item.slide_version_id === slide.slide_version_id ? response.data! : item) });
    }
  };

  const updateVisual = async (slide: Record<string, any>, patch: Record<string, any>) => {
    if (!plan) return;
    const nextPlan = { ...(slide.visual_plan?.plan || {}), ...patch };
    const response = await updateAgentSlideVisualPlan(plan.project_id, plan.deck_version_id, slide.slide_version_id, nextPlan);
    if (response.data) {
      setPlan({ ...plan, slides: plan.slides.map((item) => item.slide_version_id === slide.slide_version_id ? response.data! : item) });
    }
  };

  const toggleLock = async (slide: Record<string, any>) => {
    if (!plan) return;
    const response = await setAgentSlideLock(plan.project_id, plan.deck_version_id, slide.slide_version_id, !slide.locked);
    if (response.data) {
      setPlan({ ...plan, slides: plan.slides.map((item) => item.slide_version_id === slide.slide_version_id ? response.data! : item) });
    }
  };

  const generatePreview = async (slideVersionIds?: string[]) => {
    if (!plan) return;
    const response = await generateAgentStylePreview(plan.project_id, plan.deck_version_id, slideVersionIds);
    if (response.data?.task_id) {
      setPreviewTaskId(response.data.task_id);
      show({ message: '已开始生成风格验证页：默认封面 + 典型内容页', type: 'success' });
    }
  };

  const generateRemaining = async () => {
    if (!plan) return;
    const response = await generateAgentRemainingSlides(plan.project_id, plan.deck_version_id);
    if (response.data?.task_id) {
      setBatchTaskId(response.data.task_id);
      show({ message: '已开始批量生成剩余页面，失败页面可单独重试', type: 'success' });
    }
  };

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-orange-200 bg-orange-50/50 p-4 dark:border-banana/30 dark:bg-banana/5">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="block">
            <span className="text-xs font-medium text-gray-600 dark:text-foreground-tertiary">主题</span>
            <input value={topic} onChange={(event) => setTopic(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-border-primary dark:bg-background-elevated dark:text-white" />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-gray-600 dark:text-foreground-tertiary">受众</span>
            <input value={audience} onChange={(event) => setAudience(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-border-primary dark:bg-background-elevated dark:text-white" />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-gray-600 dark:text-foreground-tertiary">页数</span>
            <input type="number" min={1} max={20} value={pageCount} onChange={(event) => setPageCount(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-border-primary dark:bg-background-elevated dark:text-white" />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-gray-600 dark:text-foreground-tertiary">风格</span>
            <input value={style} onChange={(event) => setStyle(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-border-primary dark:bg-background-elevated dark:text-white" />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={createPlan} disabled={loading}>{loading ? '生成中...' : '生成 Agent 计划'}</Button>
          {plan && <Button variant="secondary" onClick={() => onOpenProject(plan.project_id)}>打开项目</Button>}
        </div>
      </div>

      {plan && (
        <div className="space-y-4">
          <section className="rounded-xl border border-gray-200 p-4 dark:border-border-primary">
            <h3 className="font-semibold text-gray-900 dark:text-white">DeckVisualSystem</h3>
            <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-xs text-gray-700 dark:bg-background-secondary dark:text-foreground-secondary">{JSON.stringify(plan.visual_system?.system || plan.visual_system, null, 2)}</pre>
          </section>

          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-gray-900 dark:text-white">可编辑计划</h3>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => generatePreview()}>生成风格验证页</Button>
                <Button onClick={generateRemaining}>确认风格，生成剩余页面</Button>
              </div>
            </div>
            {previewTaskId && <p className="text-xs text-gray-500">风格验证任务：{previewTaskId}</p>}
            {batchTaskId && <p className="text-xs text-gray-500">批量生成任务：{batchTaskId}</p>}
            {plan.slides.map((slide, index) => (
              <article key={slide.slide_version_id} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-border-primary dark:bg-background-elevated">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-medium text-orange-700 dark:text-banana">第 {index + 1} 页 · {slide.status}{slide.locked ? ' · 已锁定' : ''}</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => toggleLock(slide)}>{slide.locked ? '解锁' : '锁定'}</Button>
                    <Button size="sm" variant="secondary" onClick={() => generatePreview([slide.slide_version_id])}>只重画此页预览</Button>
                  </div>
                </div>
                <input value={slide.slide_plan?.title || ''} onChange={(event) => updateSlide(slide, { title: event.target.value })} className="mt-3 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold dark:border-border-primary dark:bg-background-secondary dark:text-white" />
                <textarea value={slide.slide_plan?.main_message || ''} onChange={(event) => updateSlide(slide, { main_message: event.target.value })} rows={2} className="mt-2 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-border-primary dark:bg-background-secondary dark:text-white" />
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <textarea value={slide.visual_plan?.reader_takeaway || ''} onChange={(event) => updateVisual(slide, { reader_takeaway: event.target.value })} rows={3} className="rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-border-primary dark:bg-background-secondary dark:text-white" />
                  <textarea value={slide.visual_plan?.composition || ''} onChange={(event) => updateVisual(slide, { composition: event.target.value })} rows={3} className="rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-border-primary dark:bg-background-secondary dark:text-white" />
                </div>
                <p className="mt-2 text-xs text-gray-500">纸片人：{slide.visual_plan?.operator_required ? slide.visual_plan?.operator_family : '本页不强制'} · 标签：{(slide.visual_plan?.labels || []).join('、')}</p>
              </article>
            ))}
          </section>
        </div>
      )}
    </div>
  );
};
