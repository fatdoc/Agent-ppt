import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  generateAllNarrations: vi.fn(),
  generateOutline: vi.fn(),
  getProject: vi.fn(),
  listExports: vi.fn(),
  listMaterials: vi.fn(),
  listProjectReferenceFiles: vi.fn(),
  listUserStyleTemplates: vi.fn(),
}));

vi.mock('@/api/endpoints', () => apiMocks);

import {
  COMPETITIONS,
  SYSTEM_OUTLINE_TEMPLATES,
  canStartCompetitionWorkflow,
  findBestOutlineTemplate,
  getCompetitionConfig,
  getWorkflowForSupportLevel,
  type PlatformProjectContext,
} from '@/platform';
import { useAgentTaskStore } from '@/store/useAgentTaskStore';

const projectContext: PlatformProjectContext = {
  projectId: 'project-1',
  projectName: '智慧养老项目',
  competitionId: 'wvcc',
  competitionTypeId: 'championship',
  trackId: 'ai-application',
  themeId: 'ai-industry',
  targetPageCount: 39,
  style: '科技蓝',
  activeScoreDimensionIds: [],
};

describe('competition support architecture', () => {
  it('keeps exclusive score dimensions on the fully supported WVCC config', () => {
    const wvcc = getCompetitionConfig('wvcc');
    expect(wvcc.supportLevel).toBe('FULL');
    expect(wvcc.scoreDimensions).toHaveLength(5);
    expect(wvcc.recommendedPageCount).toBe(39);
    expect(
      COMPETITIONS.filter((competition) => competition.id !== 'wvcc')
        .every((competition) => !competition.scoreDimensions?.length),
    ).toBe(true);
  });

  it('blocks COMING_SOON while allowing FULL and GENERIC generation', () => {
    expect(canStartCompetitionWorkflow('wvcc')).toBe(true);
    expect(canStartCompetitionWorkflow('challenge-cup')).toBe(true);
    expect(canStartCompetitionWorkflow('career-planning')).toBe(false);
  });
});

describe('outline-template matching', () => {
  it('prefers the WVCC competition/type template over the platform generic template', () => {
    const matched = findBestOutlineTemplate(SYSTEM_OUTLINE_TEMPLATES, projectContext);
    expect(matched?.id).toBe('wvcc-championship-39');
    expect(matched?.targetPageCount).toBe(39);
  });

  it('falls back to the platform generic template without inventing competition data', () => {
    const matched = findBestOutlineTemplate(SYSTEM_OUTLINE_TEMPLATES, {
      competitionId: 'custom',
      competitionTypeId: 'custom',
    });
    expect(matched?.id).toBe('platform-generic');
    expect(
      matched?.sections.some((section) => section.scoreDimensions?.length),
    ).toBe(false);
  });
});

describe('deterministic digital-employee workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAgentTaskStore.setState({ tasks: [], activeWorkflowId: null });
    Object.values(apiMocks).forEach((mock) => mock.mockResolvedValue({ data: {} }));
    apiMocks.getProject.mockResolvedValue({ data: { pages: [] } });
    apiMocks.listExports.mockResolvedValue({ data: { files: [] } });
  });

  it('uses bounded workflows and excludes score inspection from GENERIC mode', () => {
    const full = getWorkflowForSupportLevel('FULL');
    const generic = getWorkflowForSupportLevel('GENERIC');
    expect(full?.steps.length).toBeLessThanOrEqual(8);
    expect(generic?.steps.length).toBeLessThanOrEqual(8);
    expect(full?.steps.some((step) => step.taskType === 'INSPECT_SCORE_COVERAGE')).toBe(true);
    expect(generic?.steps.some((step) => step.taskType === 'INSPECT_SCORE_COVERAGE')).toBe(false);
    expect(getWorkflowForSupportLevel('COMING_SOON')).toBeUndefined();
  });

  it('cancels pending workflow steps without starting a loop', async () => {
    let releaseFirstTask!: () => void;
    apiMocks.getProject.mockImplementationOnce(
      () => new Promise((resolve) => {
        releaseFirstTask = () => resolve({ data: { pages: [] } });
      }),
    );
    const competition = getCompetitionConfig('wvcc');
    const running = useAgentTaskStore.getState().runRecommendedWorkflow({
      goal: '生成参赛 PPT',
      projectContext,
      competition,
    });
    useAgentTaskStore.getState().cancelWorkflow();
    releaseFirstTask();
    await running;
    const workflowTasks = useAgentTaskStore.getState().tasks;
    expect(workflowTasks).toHaveLength(8);
    expect(workflowTasks.every((task) => task.status === 'CANCELLED')).toBe(true);
  });

  it('retries a failed task through the same mapped real service', async () => {
    apiMocks.getProject
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce({ data: { pages: [] } });
    const competition = getCompetitionConfig('wvcc');
    const input = { goal: '检查项目', projectContext, competition };
    await useAgentTaskStore.getState().runEmployee('chief-planner', input);
    const failed = useAgentTaskStore.getState().tasks[0];
    expect(failed.status).toBe('FAILED');
    await useAgentTaskStore.getState().retryTask(failed.id, input);
    expect(useAgentTaskStore.getState().tasks[0].status).toBe('SUCCESS');
  });
});
