import { create } from 'zustand';
import {
  generateAllNarrations,
  generateOutline,
  getProject,
  listExports,
  listMaterials,
  listProjectReferenceFiles,
  listUserStyleTemplates,
} from '@/api/endpoints';
import {
  DIGITAL_EMPLOYEES,
  WVCC_SCORE_DIMENSIONS,
  getWorkflowForSupportLevel,
  type AgentTask,
  type CompetitionConfig,
  type DigitalEmployee,
  type PlatformProjectContext,
} from '@/platform';

const cancelledWorkflows = new Set<string>();
const id = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

type TaskInput = {
  goal: string;
  projectContext: PlatformProjectContext;
  competition: CompetitionConfig;
};

const executeTask = async (
  employee: DigitalEmployee,
  taskType: string,
  input: TaskInput,
) => {
  const projectId = input.projectContext.projectId;
  if (!projectId) throw new Error('未关联项目');

  if (taskType === 'GENERATE_OUTLINE' || employee.id === 'outline-architect') {
    return generateOutline(projectId);
  }
  if (taskType === 'LIST_REFERENCE_FILES' || employee.id === 'content-analyst') {
    return listProjectReferenceFiles(projectId);
  }
  if (taskType === 'LIST_STYLE_TEMPLATES' || employee.id === 'visual-designer') {
    return listUserStyleTemplates();
  }
  if (taskType === 'LIST_MATERIALS' || employee.id === 'asset-creator') {
    return listMaterials(projectId);
  }
  if (taskType === 'GENERATE_NARRATIONS' || employee.id === 'speechwriter') {
    return generateAllNarrations(projectId);
  }
  if (taskType === 'DELIVERY_CHECK' || employee.id === 'delivery-engineer') {
    const [projectResponse, exportsResponse] = await Promise.all([
      getProject(projectId),
      listExports(projectId),
    ]);
    const project = projectResponse.data;
    return {
      pageCount: project?.pages.length ?? 0,
      missingImages: project?.pages.filter((page) => !page.generated_image_url && !page.generated_image_path).length ?? 0,
      missingNarrations: project?.pages.filter((page) => !page.narration_text).length ?? 0,
      exports: exportsResponse.data?.files.length ?? 0,
    };
  }
  if (taskType === 'INSPECT_SCORE_COVERAGE' || employee.id === 'score-inspector') {
    const projectResponse = await getProject(projectId);
    const text = (projectResponse.data?.pages ?? [])
      .map((page) => `${page.outline_content?.title ?? ''} ${(page.outline_content?.points ?? []).join(' ')}`)
      .join(' ');
    return {
      dimensions: WVCC_SCORE_DIMENSIONS.map((dimension) => ({
        id: dimension.id,
        name: dimension.name,
        configured: true,
        hasProjectContent: text.length > 0,
      })),
      note: '评分检查基于真实项目页面与世职赛配置，不为其他赛事生成评分结论。',
    };
  }
  return getProject(projectId);
};

interface AgentTaskState {
  tasks: AgentTask[];
  activeWorkflowId: string | null;
  runEmployee: (employeeId: string, input: TaskInput) => Promise<void>;
  runRecommendedWorkflow: (input: TaskInput) => Promise<void>;
  cancelWorkflow: () => void;
  retryTask: (taskId: string, input: TaskInput) => Promise<void>;
  clearFinished: () => void;
}

export const useAgentTaskStore = create<AgentTaskState>((set, get) => {
  const patchTask = (taskId: string, patch: Partial<AgentTask>) => {
    set((state) => ({
      tasks: state.tasks.map((task) => task.id === taskId ? { ...task, ...patch } : task),
    }));
  };

  const runOne = async (
    task: AgentTask,
    employee: DigitalEmployee,
    input: TaskInput,
  ) => {
    patchTask(task.id, { status: 'RUNNING', startedAt: new Date().toISOString() });
    try {
      const result = await executeTask(employee, task.taskType, input);
      if (task.workflowId && cancelledWorkflows.has(task.workflowId)) {
        patchTask(task.id, { status: 'CANCELLED', completedAt: new Date().toISOString() });
        return false;
      }
      patchTask(task.id, {
        status: 'SUCCESS',
        output: { result },
        completedAt: new Date().toISOString(),
      });
      return true;
    } catch (error) {
      patchTask(task.id, {
        status: 'FAILED',
        errorMessage: error instanceof Error ? error.message : '任务执行失败',
        completedAt: new Date().toISOString(),
      });
      return false;
    }
  };

  return {
    tasks: [],
    activeWorkflowId: null,

    runEmployee: async (employeeId, input) => {
      const employee = DIGITAL_EMPLOYEES.find((item) => item.id === employeeId);
      const projectId = input.projectContext.projectId;
      if (!employee || !projectId) return;
      const task: AgentTask = {
        id: id('agent'),
        label: employee.role,
        projectId,
        employeeId,
        taskType: employee.serviceMapping[0]?.type ?? 'GET_PROJECT',
        status: 'PENDING',
        input: { goal: input.goal, competitionId: input.competition.id },
        createdAt: new Date().toISOString(),
      };
      set((state) => ({ tasks: [task, ...state.tasks].slice(0, 40) }));
      await runOne(task, employee, input);
    },

    runRecommendedWorkflow: async (input) => {
      const projectId = input.projectContext.projectId;
      const workflow = getWorkflowForSupportLevel(input.competition.supportLevel);
      if (!projectId || !workflow) return;
      const workflowId = id('workflow');
      cancelledWorkflows.delete(workflowId);
      const tasks: AgentTask[] = workflow.steps.map((step) => ({
        id: id(step.id),
        workflowId,
        label: step.label,
        projectId,
        employeeId: step.employeeId,
        taskType: step.taskType,
        status: 'PENDING',
        input: {
          goal: input.goal,
          competitionId: input.competition.id,
          trackId: input.projectContext.trackId,
          themeId: input.projectContext.themeId,
        },
        createdAt: new Date().toISOString(),
      }));
      set((state) => ({
        activeWorkflowId: workflowId,
        tasks: [...tasks, ...state.tasks].slice(0, 40),
      }));
      for (const task of tasks) {
        if (cancelledWorkflows.has(workflowId)) {
          patchTask(task.id, { status: 'CANCELLED', completedAt: new Date().toISOString() });
          continue;
        }
        const employee = DIGITAL_EMPLOYEES.find((item) => item.id === task.employeeId);
        if (!employee) continue;
        const succeeded = await runOne(task, employee, input);
        if (!succeeded) break;
      }
      set({ activeWorkflowId: null });
    },

    cancelWorkflow: () => {
      const workflowId = get().activeWorkflowId;
      if (!workflowId) return;
      cancelledWorkflows.add(workflowId);
      set((state) => ({
        activeWorkflowId: null,
        tasks: state.tasks.map((task) =>
          task.workflowId === workflowId && ['PENDING', 'RUNNING'].includes(task.status)
            ? { ...task, status: 'CANCELLED', completedAt: new Date().toISOString() }
            : task),
      }));
    },

    retryTask: async (taskId, input) => {
      const task = get().tasks.find((item) => item.id === taskId);
      const employee = DIGITAL_EMPLOYEES.find((item) => item.id === task?.employeeId);
      if (!task || !employee) return;
      await runOne({ ...task, status: 'PENDING', errorMessage: undefined }, employee, input);
    },

    clearFinished: () => set((state) => ({
      tasks: state.tasks.filter((task) => ['PENDING', 'RUNNING'].includes(task.status)),
    })),
  };
});
