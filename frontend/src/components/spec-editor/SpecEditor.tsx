import React, { useEffect, useRef, useState } from 'react';
import { Lock, Plus, X } from 'lucide-react';
import type { CompetitionProjectSpec, SkillModule, SpecField, SpecListField, TeamMember } from '@/types/spec';
import type { PatchOp } from '@/types/patch';

interface SpecEditorProps {
  spec: CompetitionProjectSpec;
  onPatch: (op: PatchOp) => void;
  onUnlock: (path: string) => void;
}

interface FieldInputProps {
  field: SpecField;
  blockId: string;
  path: string;
  label: string;
  placeholder?: string;
  onPatch: (op: PatchOp) => void;
  onUnlock: (path: string) => void;
}

interface ListFieldInputProps {
  field: SpecListField;
  blockId: string;
  path: string;
  label: string;
  onPatch: (op: PatchOp) => void;
  onUnlock: (path: string) => void;
}

const roleLabels = ['A', 'B', 'C', 'D'] as const;
const newDraftRowId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;

export const SpecEditor: React.FC<SpecEditorProps> = ({ spec, onPatch, onUnlock }) => (
  <div className="spec-editor space-y-6">
    <div className="border-b border-slate-200 pb-4 dark:border-white/10">
      <h1 className="text-2xl font-black tracking-normal">大赛展示项目稿件</h1>
      <p className="mt-1 text-sm font-medium text-slate-500">Markdown 样式展示，底层只保存结构化字段</p>
    </div>
    <ProjectPositioningSection spec={spec} onPatch={onPatch} onUnlock={onUnlock} />
    <ProblemDefinitionSection spec={spec} onPatch={onPatch} onUnlock={onUnlock} />
    <TeamRolesSection spec={spec} onPatch={onPatch} onUnlock={onUnlock} />
    <SkillModulesSection spec={spec} onPatch={onPatch} onUnlock={onUnlock} />
    <ResultValidationSection spec={spec} onPatch={onPatch} onUnlock={onUnlock} />
    <ValueInnovationSection spec={spec} onPatch={onPatch} onUnlock={onUnlock} />
  </div>
);

const SpecSection: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section className="spec-section">
    <h2 className="mb-3 text-lg font-black tracking-normal">{title}</h2>
    <div className="space-y-2">{children}</div>
  </section>
);

const SpecSubsection: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="mt-4 border-l-2 border-slate-200 pl-3 dark:border-white/10">
    <h3 className="mb-2 text-base font-black">{title}</h3>
    <div className="space-y-2">{children}</div>
  </div>
);

export const SpecFieldInput: React.FC<FieldInputProps> = ({
  field,
  blockId,
  path,
  label,
  placeholder = '待补充',
  onPatch,
  onUnlock,
}) => {
  const [localValue, setLocalValue] = useState(field.value);

  useEffect(() => {
    setLocalValue(field.value);
  }, [field]);

  const handleBlur = () => {
    if (localValue !== field.value) {
      onPatch({ type: 'set', block_id: blockId, path, value: localValue, source: 'user' });
    }
  };

  return (
    <div className={`spec-field spec-field--${field.state} flex items-center gap-2 rounded-md px-2 py-1.5`}>
      <span className="spec-field__label shrink-0 text-sm font-bold text-slate-600 dark:text-foreground-secondary">- {label}：</span>
      <input
        aria-label={label}
        className="spec-field__input min-w-0 flex-1 bg-transparent text-sm leading-7 outline-none placeholder:text-slate-400"
        value={localValue}
        onChange={(event) => setLocalValue(event.target.value)}
        onBlur={handleBlur}
        placeholder={placeholder}
      />
      {field.state === 'locked' && (
        <button
          type="button"
          className="spec-field__unlock grid h-7 w-7 shrink-0 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-white/10 dark:hover:text-white"
          onClick={() => onUnlock(path)}
          title="此字段已锁定，点击允许 AI 修改"
          aria-label={`解锁${label}`}
        >
          <Lock size={15} />
        </button>
      )}
    </div>
  );
};

export const SpecListFieldInput: React.FC<ListFieldInputProps> = ({
  field,
  blockId,
  path,
  label,
  onPatch,
  onUnlock,
}) => {
  const [draftRows, setDraftRows] = useState<Array<{ id: string; value: string }>>([]);

  useEffect(() => {
    setDraftRows([]);
  }, [path]);

  const updateDraftRow = (id: string, value: string) => {
    setDraftRows((rows) => rows.map((row) => (row.id === id ? { ...row, value } : row)));
  };

  const removeDraftRow = (id: string) => {
    setDraftRows((rows) => rows.filter((row) => row.id !== id));
  };

  const commitDraftRow = (id: string) => {
    const draft = draftRows.find((row) => row.id === id);
    const value = draft?.value.trim() || '';
    removeDraftRow(id);
    if (value) {
      onPatch({ type: 'append', block_id: blockId, path, value, source: 'user' });
    }
  };

  return (
    <div className={`spec-list-field spec-field--${field.state} rounded-md px-2 py-2`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-sm font-black">{label}</h4>
        {field.state === 'locked' && (
          <button
            type="button"
            className="spec-field__unlock grid h-7 w-7 shrink-0 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            onClick={() => onUnlock(path)}
            title="此列表已锁定，点击允许 AI 修改"
            aria-label={`解锁${label}`}
          >
            <Lock size={15} />
          </button>
        )}
      </div>
      <div className="space-y-2">
        {field.value.length === 0 && draftRows.length === 0 && (
          <div className="text-sm text-slate-400">- 待补充</div>
        )}
        {field.value.map((item, index) => (
          <SpecListRow
            key={`${path}-${index}-${item}`}
            item={item}
            index={index}
            blockId={blockId}
            path={path}
            label={label}
            onPatch={onPatch}
          />
        ))}
        {draftRows.map((row, draftIndex) => (
          <SpecDraftListRow
            key={row.id}
            value={row.value}
            index={field.value.length + draftIndex}
            label={label}
            onChange={(value) => updateDraftRow(row.id, value)}
            onCommit={() => commitDraftRow(row.id)}
            onCancel={() => removeDraftRow(row.id)}
          />
        ))}
      </div>
      <button
        type="button"
        className="mt-2 inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-black text-blue-700 hover:bg-blue-50"
        onClick={() => setDraftRows((rows) => [...rows, { id: newDraftRowId(), value: '' }])}
      >
        <Plus size={14} />
        新增
      </button>
    </div>
  );
};

const SpecListRow: React.FC<{
  item: string;
  index: number;
  blockId: string;
  path: string;
  label: string;
  onPatch: (op: PatchOp) => void;
}> = ({ item, index, blockId, path, label, onPatch }) => {
  const [localValue, setLocalValue] = useState(item);

  useEffect(() => {
    setLocalValue(item);
  }, [item, path, index]);

  return (
    <div className="spec-list-field__row flex items-center gap-2">
      <span className="w-5 shrink-0 text-right text-sm font-bold text-slate-400">{index + 1}.</span>
      <input
        aria-label={`${label}${index + 1}`}
        className="min-w-0 flex-1 bg-transparent text-sm leading-7 outline-none placeholder:text-slate-400"
        value={localValue}
        onChange={(event) => setLocalValue(event.target.value)}
        onBlur={() => {
          if (localValue !== item) {
            onPatch({ type: 'set_at', block_id: blockId, path, index, value: localValue, source: 'user' });
          }
        }}
        placeholder="待补充"
      />
      <button
        type="button"
        className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-slate-400 hover:bg-red-50 hover:text-red-600"
        onClick={() => onPatch({ type: 'remove_at', block_id: blockId, path, index, source: 'user' })}
        aria-label={`删除${label}${index + 1}`}
      >
        <X size={15} />
      </button>
    </div>
  );
};

const SpecDraftListRow: React.FC<{
  value: string;
  index: number;
  label: string;
  onChange: (value: string) => void;
  onCommit: () => void;
  onCancel: () => void;
}> = ({ value, index, label, onChange, onCommit, onCancel }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const doneRef = useRef(false);

  const commitOnce = () => {
    if (doneRef.current) return;
    doneRef.current = true;
    onCommit();
  };

  const cancelOnce = () => {
    if (doneRef.current) return;
    doneRef.current = true;
    onCancel();
  };

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="spec-list-field__row flex items-center gap-2">
      <span className="w-5 shrink-0 text-right text-sm font-bold text-slate-400">{index + 1}.</span>
      <input
        ref={inputRef}
        aria-label={`新增${label}${index + 1}`}
        className="min-w-0 flex-1 bg-transparent text-sm leading-7 outline-none placeholder:text-slate-400"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={commitOnce}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
            event.preventDefault();
            commitOnce();
          }
          if (event.key === 'Escape') {
            event.preventDefault();
            cancelOnce();
          }
        }}
        placeholder={`输入${label}`}
      />
      <button
        type="button"
        className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-slate-400 hover:bg-red-50 hover:text-red-600"
        onMouseDown={(event) => event.preventDefault()}
        onClick={cancelOnce}
        aria-label={`取消新增${label}${index + 1}`}
      >
        <X size={15} />
      </button>
    </div>
  );
};

const ProjectPositioningSection: React.FC<SpecEditorProps> = ({ spec, onPatch, onUnlock }) => (
  <SpecSection title="一、项目定位">
    <SpecFieldInput label="项目名称" blockId="project_positioning" path="project_positioning.project_name" field={spec.project_positioning.project_name} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="副标题" blockId="project_positioning" path="project_positioning.subtitle" field={spec.project_positioning.subtitle} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="赛道/专业方向" blockId="project_positioning" path="project_positioning.track" field={spec.project_positioning.track} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="真实场景" blockId="project_positioning" path="project_positioning.real_scene" field={spec.project_positioning.real_scene} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="服务对象" blockId="project_positioning" path="project_positioning.service_object" field={spec.project_positioning.service_object} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="最终成果形态" blockId="project_positioning" path="project_positioning.final_deliverable" field={spec.project_positioning.final_deliverable} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="一句话介绍" blockId="project_positioning" path="project_positioning.one_sentence_intro" field={spec.project_positioning.one_sentence_intro} onPatch={onPatch} onUnlock={onUnlock} />
  </SpecSection>
);

const ProblemDefinitionSection: React.FC<SpecEditorProps> = ({ spec, onPatch, onUnlock }) => (
  <SpecSection title="二、真实问题与目标">
    <SpecFieldInput label="需求来源" blockId="problem_definition" path="problem_definition.need_source" field={spec.problem_definition.need_source} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="当前做法" blockId="problem_definition" path="problem_definition.current_method" field={spec.problem_definition.current_method} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecListFieldInput label="痛点" blockId="problem_definition" path="problem_definition.pain_points" field={spec.problem_definition.pain_points} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="问题后果" blockId="problem_definition" path="problem_definition.problem_consequences" field={spec.problem_definition.problem_consequences} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="项目目标" blockId="problem_definition" path="problem_definition.project_goal" field={spec.problem_definition.project_goal} onPatch={onPatch} onUnlock={onUnlock} />
  </SpecSection>
);

const TeamRolesSection: React.FC<SpecEditorProps> = ({ spec, onPatch, onUnlock }) => (
  <SpecSection title="三、四名选手分工">
    {roleLabels.map((roleKey) => {
      const role = spec.team_roles[roleKey];
      return (
        <SpecSubsection key={roleKey} title={`${roleKey} 选手`}>
          <TeamMemberFields role={role} roleKey={roleKey} onPatch={onPatch} onUnlock={onUnlock} />
        </SpecSubsection>
      );
    })}
  </SpecSection>
);

const TeamMemberFields: React.FC<{
  role: TeamMember;
  roleKey: typeof roleLabels[number];
  onPatch: (op: PatchOp) => void;
  onUnlock: (path: string) => void;
}> = ({ role, roleKey, onPatch, onUnlock }) => {
  const blockId = `team_roles.${roleKey}`;
  return (
    <>
      <SpecFieldInput label="角色" blockId={blockId} path={`${blockId}.role`} field={role.role} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="负责内容" blockId={blockId} path={`${blockId}.responsibility`} field={role.responsibility} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="现场动作" blockId={blockId} path={`${blockId}.onsite_action`} field={role.onsite_action} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="关联技能模块" blockId={blockId} path={`${blockId}.related_skill_modules`} field={role.related_skill_modules} onPatch={onPatch} onUnlock={onUnlock} />
    </>
  );
};

const SkillModulesSection: React.FC<SpecEditorProps> = ({ spec, onPatch, onUnlock }) => (
  <SpecSection title="四、技能展示模块">
    {spec.skill_modules.map((module, index) => (
      <SpecSubsection key={module.id} title={`技能模块 ${index + 1}`}>
        <SkillModuleFields module={module} onPatch={onPatch} onUnlock={onUnlock} />
      </SpecSubsection>
    ))}
  </SpecSection>
);

const SkillModuleFields: React.FC<{
  module: SkillModule;
  onPatch: (op: PatchOp) => void;
  onUnlock: (path: string) => void;
}> = ({ module, onPatch, onUnlock }) => {
  const blockId = `skill_modules[${module.id}]`;
  return (
    <>
      <SpecFieldInput label="技能名称" blockId={blockId} path={`${blockId}.skill_name`} field={module.skill_name} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="负责角色" blockId={blockId} path={`${blockId}.responsible_role`} field={module.responsible_role} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="工作任务" blockId={blockId} path={`${blockId}.work_task`} field={module.work_task} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="现场演示动作" blockId={blockId} path={`${blockId}.onsite_demo_action`} field={module.onsite_demo_action} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="验证方式" blockId={blockId} path={`${blockId}.verification_method`} field={module.verification_method} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="预期证据" blockId={blockId} path={`${blockId}.expected_evidence`} field={module.expected_evidence} onPatch={onPatch} onUnlock={onUnlock} />
      <SpecFieldInput label="工具/设备/材料" blockId={blockId} path={`${blockId}.tools_or_equipment`} field={module.tools_or_equipment} onPatch={onPatch} onUnlock={onUnlock} />
    </>
  );
};

const ResultValidationSection: React.FC<SpecEditorProps> = ({ spec, onPatch, onUnlock }) => (
  <SpecSection title="五、成果验证">
    <SpecListFieldInput label="成果清单" blockId="result_validation" path="result_validation.deliverables" field={spec.result_validation.deliverables} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecListFieldInput label="证据材料" blockId="result_validation" path="result_validation.evidence_materials" field={spec.result_validation.evidence_materials} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="测试数据" blockId="result_validation" path="result_validation.test_data" field={spec.result_validation.test_data} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="优化前后对比" blockId="result_validation" path="result_validation.before_after_comparison" field={spec.result_validation.before_after_comparison} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="用户反馈" blockId="result_validation" path="result_validation.user_feedback" field={spec.result_validation.user_feedback} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="质量评价" blockId="result_validation" path="result_validation.quality_evaluation" field={spec.result_validation.quality_evaluation} onPatch={onPatch} onUnlock={onUnlock} />
  </SpecSection>
);

const ValueInnovationSection: React.FC<SpecEditorProps> = ({ spec, onPatch, onUnlock }) => (
  <SpecSection title="六、价值创新">
    <SpecFieldInput label="实用性" blockId="value_innovation" path="value_innovation.practical_value" field={spec.value_innovation.practical_value} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecListFieldInput label="创新点" blockId="value_innovation" path="value_innovation.innovation_points" field={spec.value_innovation.innovation_points} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="教学应用价值" blockId="value_innovation" path="value_innovation.teaching_value" field={spec.value_innovation.teaching_value} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="职业场景落地价值" blockId="value_innovation" path="value_innovation.vocational_scene_value" field={spec.value_innovation.vocational_scene_value} onPatch={onPatch} onUnlock={onUnlock} />
    <SpecFieldInput label="可持续性" blockId="value_innovation" path="value_innovation.sustainability" field={spec.value_innovation.sustainability} onPatch={onPatch} onUnlock={onUnlock} />
  </SpecSection>
);
