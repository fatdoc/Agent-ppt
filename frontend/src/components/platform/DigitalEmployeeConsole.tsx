import { useMemo, useState } from 'react';
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Play,
  RotateCcw,
  Square,
  X,
  XCircle,
} from 'lucide-react';
import {
  DIGITAL_EMPLOYEES,
  getDigitalEmployeesForCompetition,
  getWorkflowForSupportLevel,
  usePlatform,
} from '@/platform';
import { useAgentTaskStore } from '@/store/useAgentTaskStore';

interface DigitalEmployeeConsoleProps {
  open: boolean;
  onClose: () => void;
}

export const DigitalEmployeeConsole = ({ open, onClose }: DigitalEmployeeConsoleProps) => {
  const { projectContext, competition } = usePlatform();
  const employees = useMemo(
    () => getDigitalEmployeesForCompetition(competition.id),
    [competition.id],
  );
  const [selectedId, setSelectedId] = useState('chief-planner');
  const [goal, setGoal] = useState('');
  const {
    tasks,
    activeWorkflowId,
    runEmployee,
    runRecommendedWorkflow,
    cancelWorkflow,
    retryTask,
    clearFinished,
  } = useAgentTaskStore();

  if (!open) return null;

  const selected = employees.find((item) => item.id === selectedId) ?? employees[0];
  const running = tasks.some((task) => task.status === 'RUNNING');
  const workflow = getWorkflowForSupportLevel(competition.supportLevel);
  const input = { goal, projectContext, competition };

  return (
    <>
      <button
        type="button"
        aria-label="关闭数字员工总控台"
        className="fixed inset-0 z-40 cursor-default bg-slate-950/20 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[720px] flex-col bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-slate-200 px-7 py-6">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-blue-600">
              <Bot size={18} /> 数字员工总控台
            </div>
            <h2 className="text-2xl font-bold text-slate-950">把业务目标交给专业角色</h2>
            <p className="mt-1 text-sm text-slate-500">
              {competition.name} · {projectContext.projectName || '尚未命名项目'}
            </p>
          </div>
          <button
            type="button"
            aria-label="关闭"
            onClick={onClose}
            className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
          >
            <X size={22} />
          </button>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-[240px_1fr]">
          <nav className="overflow-y-auto border-r border-slate-200 bg-slate-50/70 p-3">
            {employees.map((employee) => (
              <button
                type="button"
                key={employee.id}
                onClick={() => setSelectedId(employee.id)}
                className={`mb-1 w-full rounded-xl px-3 py-3 text-left transition ${
                  selected?.id === employee.id
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-700 hover:bg-white'
                }`}
              >
                <span className="block text-sm font-semibold">{employee.name}</span>
                <span className={`mt-0.5 block text-xs ${selected?.id === employee.id ? 'text-blue-100' : 'text-slate-500'}`}>
                  {employee.role}
                </span>
              </button>
            ))}
          </nav>

          <div className="overflow-y-auto p-7">
            {selected && (
              <>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-xl font-bold text-slate-950">{selected.name}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{selected.description}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                    {selected.invocationMode === 'BOTH' ? '手动 / 工作流' : '手动'}
                  </span>
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  {selected.capabilities.map((capability) => (
                    <span key={capability} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-600">
                      {capability}
                    </span>
                  ))}
                </div>

                <label className="mt-7 block text-sm font-semibold text-slate-800" htmlFor="employee-goal">
                  业务目标
                </label>
                <textarea
                  id="employee-goal"
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  placeholder={`例如：@${selected.name} 根据当前资料检查大纲并给出下一步。`}
                  className="mt-2 min-h-28 w-full resize-none rounded-xl border border-slate-200 bg-white p-3 text-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50"
                />

                {!projectContext.projectId && (
                  <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    请先在工作台关联或创建项目。数字员工只调用真实项目服务，不运行演示任务。
                  </p>
                )}

                <button
                  type="button"
                  disabled={!projectContext.projectId || running}
                  onClick={() => runEmployee(selected.id, input)}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {running ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
                  {running ? '正在调用真实服务' : `召唤${selected.name}`}
                </button>

                {workflow && (
                  <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/60 p-3">
                    <p className="text-sm font-semibold text-blue-900">{workflow.name}</p>
                    <p className="mt-1 text-xs leading-5 text-blue-700">{workflow.description}</p>
                    <p className="mt-2 text-xs text-blue-600">{workflow.steps.length} 个固定步骤 · 失败即停止 · 不会无限循环</p>
                    {activeWorkflowId ? (
                      <button type="button" onClick={cancelWorkflow} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-rose-200 bg-white px-3 py-2 text-xs font-semibold text-rose-700">
                        <Square size={14} /> 取消当前工作流
                      </button>
                    ) : (
                      <button type="button" disabled={!projectContext.projectId || running} onClick={() => runRecommendedWorkflow(input)} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-semibold text-blue-700 disabled:opacity-50">
                        <Play size={14} /> 执行推荐工作流
                      </button>
                    )}
                  </div>
                )}
              </>
            )}

            <section className="mt-8 border-t border-slate-200 pt-6">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-950">任务记录</h3>
                {tasks.some((task) => !['PENDING', 'RUNNING'].includes(task.status)) && (
                  <button
                    type="button"
                    onClick={clearFinished}
                    className="flex items-center gap-1 text-xs font-semibold text-blue-600"
                  >
                    清理已完成
                  </button>
                )}
              </div>

              {tasks.length === 0 ? (
                <p className="mt-3 text-sm text-slate-500">尚无执行任务。选择数字员工并输入目标后开始。</p>
              ) : (
                <div className="mt-3 divide-y divide-slate-100">
                  {tasks.map((task) => {
                    const employee = DIGITAL_EMPLOYEES.find((item) => item.id === task.employeeId);
                    return (
                      <div key={task.id} className="flex items-center gap-3 py-3">
                        {task.status === 'RUNNING' && <Loader2 className="animate-spin text-blue-600" size={18} />}
                        {task.status === 'PENDING' && <span className="h-3 w-3 rounded-full border-2 border-slate-300" />}
                        {task.status === 'SUCCESS' && <CheckCircle2 className="text-emerald-600" size={18} />}
                        {task.status === 'FAILED' && <XCircle className="text-rose-600" size={18} />}
                        {task.status === 'CANCELLED' && <Square className="text-slate-400" size={16} />}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-slate-800">{task.label || employee?.name}</p>
                          <p className="truncate text-xs text-slate-500">
                            {task.status === 'PENDING' ? '等待前序步骤' : task.status === 'RUNNING' ? `${employee?.name}正在执行` : task.status === 'SUCCESS' ? '真实服务已返回结果' : task.status === 'CANCELLED' ? '已取消' : task.errorMessage}
                          </p>
                        </div>
                        {task.status === 'FAILED' && (
                          <button type="button" onClick={() => retryTask(task.id, input)} className="p-1 text-blue-600" aria-label="重试任务">
                            <RotateCcw size={15} />
                          </button>
                        )}
                        <ChevronRight size={16} className="text-slate-300" />
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        </div>
      </aside>
    </>
  );
};
