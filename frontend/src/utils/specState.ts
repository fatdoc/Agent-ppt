import { createEmptySpec, emptyField, emptyListField } from '@/utils/initSpec';
import type { CompetitionProjectSpec, FieldState, ModifiedBy, SkillModule, SpecField, SpecListField, TeamMember } from '@/types/spec';
import type { PatchOp, PatchSource } from '@/types/patch';

const roleKeys = ['A', 'B', 'C', 'D'] as const;
const skillModuleIds = ['sm_01', 'sm_02', 'sm_03', 'sm_04'] as const;
const listFieldNames = new Set(['pain_points', 'deliverables', 'evidence_materials', 'innovation_points']);

type RoleKey = typeof roleKeys[number];

const isObject = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value);

export const isSpecField = (value: unknown): value is SpecField => (
  isObject(value)
  && 'value' in value
  && typeof value.state === 'string'
  && typeof value.last_modified_by === 'string'
);

const isSpecListField = (value: unknown): value is SpecListField => isSpecField(value) && Array.isArray(value.value);

const normalizeState = (value: unknown, hasValue: boolean): FieldState => {
  if (value === 'empty' || value === 'soft' || value === 'locked') return value;
  return hasValue ? 'soft' : 'empty';
};

const normalizeModifiedBy = (value: unknown): ModifiedBy => (value === 'user' ? 'user' : 'ai');

const asString = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
};

const asStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map((item) => asString(item).trim()).filter(Boolean);
  if (typeof value === 'string') {
    return value.split(/\n|；|;|、/).map((item) => item.trim()).filter(Boolean);
  }
  return [];
};

function wrapField(value: unknown, fallback?: SpecField): SpecField {
  if (isSpecField(value)) {
    const nextValue = asString(value.value);
    return {
      value: nextValue,
      state: normalizeState(value.state, Boolean(nextValue.trim())),
      last_modified_by: normalizeModifiedBy(value.last_modified_by),
      updated_at: typeof value.updated_at === 'number' ? value.updated_at : Date.now(),
    };
  }
  if (value === undefined && fallback) return { ...fallback };
  const nextValue = asString(value).trim();
  return {
    ...emptyField(),
    value: nextValue,
    state: nextValue ? 'soft' : 'empty',
  };
}

function wrapListField(value: unknown, fallback?: SpecListField): SpecListField {
  if (isSpecListField(value)) {
    const nextValue = asStringList(value.value);
    return {
      value: nextValue,
      state: normalizeState(value.state, nextValue.length > 0),
      last_modified_by: normalizeModifiedBy(value.last_modified_by),
      updated_at: typeof value.updated_at === 'number' ? value.updated_at : Date.now(),
    };
  }
  if (value === undefined && fallback) return { ...fallback, value: [...fallback.value] };
  const nextValue = asStringList(value);
  return {
    ...emptyListField(),
    value: nextValue,
    state: nextValue.length ? 'soft' : 'empty',
  };
}

const legacyRoleByKey = (rawRoles: unknown, key: RoleKey): Record<string, unknown> => {
  if (isObject(rawRoles) && isObject(rawRoles[key])) return rawRoles[key] as Record<string, unknown>;
  if (Array.isArray(rawRoles)) {
    return rawRoles.find((role) => isObject(role) && role.member === key) as Record<string, unknown> || {};
  }
  return {};
};

const normalizeTeamMember = (raw: Record<string, unknown>, fallback: TeamMember): TeamMember => ({
  role: wrapField(raw.role, fallback.role),
  responsibility: wrapField(raw.responsibility, fallback.responsibility),
  onsite_action: wrapField(raw.onsite_action, fallback.onsite_action),
  related_skill_modules: wrapField(
    Array.isArray(raw.related_skill_modules) ? raw.related_skill_modules.join('；') : raw.related_skill_modules,
    fallback.related_skill_modules,
  ),
});

const normalizeSkillModule = (raw: Record<string, unknown>, id: SkillModule['id'], fallback: SkillModule): SkillModule => ({
  id,
  skill_name: wrapField(raw.skill_name, fallback.skill_name),
  responsible_role: wrapField(raw.responsible_role, fallback.responsible_role),
  work_task: wrapField(raw.work_task, fallback.work_task),
  onsite_demo_action: wrapField(raw.onsite_demo_action, fallback.onsite_demo_action),
  verification_method: wrapField(raw.verification_method, fallback.verification_method),
  expected_evidence: wrapField(raw.expected_evidence, fallback.expected_evidence),
  tools_or_equipment: wrapField(raw.tools_or_equipment, fallback.tools_or_equipment),
});

const legacyModuleById = (rawModules: unknown, id: SkillModule['id'], index: number): Record<string, unknown> => {
  if (!Array.isArray(rawModules)) return {};
  return rawModules.find((module) => isObject(module) && module.id === id) as Record<string, unknown>
    || (isObject(rawModules[index]) ? rawModules[index] as Record<string, unknown> : {});
};

export function normalizeSpec(rawSpec: unknown): CompetitionProjectSpec {
  const fallback = createEmptySpec();
  const raw = isObject(rawSpec) ? rawSpec : {};
  const positioning = isObject(raw.project_positioning) ? raw.project_positioning : {};
  const problem = isObject(raw.problem_definition) ? raw.problem_definition : {};
  const validation = isObject(raw.result_validation) ? raw.result_validation : {};
  const value = isObject(raw.value_innovation) ? raw.value_innovation : {};

  return {
    ...fallback,
    competition_context: isObject(raw.competition_context) ? {
      competition_name: asString(raw.competition_context.competition_name) || fallback.competition_context!.competition_name,
      generation_goal: asString(raw.competition_context.generation_goal) || fallback.competition_context!.generation_goal,
      presentation_mode: asString(raw.competition_context.presentation_mode) || fallback.competition_context!.presentation_mode,
      audience: asStringList(raw.competition_context.audience).length ? asStringList(raw.competition_context.audience) : fallback.competition_context!.audience,
    } : fallback.competition_context,
    source_material: isObject(raw.source_material) ? {
      raw_text: asString(raw.source_material.raw_text),
      file_id: typeof raw.source_material.file_id === 'string' ? raw.source_material.file_id : null,
      filename: typeof raw.source_material.filename === 'string' ? raw.source_material.filename : null,
    } : fallback.source_material,
    project_positioning: {
      project_name: wrapField(positioning.project_name, fallback.project_positioning.project_name),
      subtitle: wrapField(positioning.subtitle, fallback.project_positioning.subtitle),
      track: wrapField(positioning.track || positioning.industry, fallback.project_positioning.track),
      real_scene: wrapField(positioning.real_scene, fallback.project_positioning.real_scene),
      service_object: wrapField(positioning.service_object, fallback.project_positioning.service_object),
      final_deliverable: wrapField(positioning.final_deliverable, fallback.project_positioning.final_deliverable),
      one_sentence_intro: wrapField(positioning.one_sentence_intro, fallback.project_positioning.one_sentence_intro),
    },
    problem_definition: {
      need_source: wrapField(problem.need_source, fallback.problem_definition.need_source),
      current_method: wrapField(problem.current_method, fallback.problem_definition.current_method),
      pain_points: wrapListField(problem.pain_points, fallback.problem_definition.pain_points),
      problem_consequences: wrapField(problem.problem_consequences, fallback.problem_definition.problem_consequences),
      project_goal: wrapField(problem.project_goal, fallback.problem_definition.project_goal),
    },
    team_roles: {
      A: normalizeTeamMember(legacyRoleByKey(raw.team_roles, 'A'), fallback.team_roles.A),
      B: normalizeTeamMember(legacyRoleByKey(raw.team_roles, 'B'), fallback.team_roles.B),
      C: normalizeTeamMember(legacyRoleByKey(raw.team_roles, 'C'), fallback.team_roles.C),
      D: normalizeTeamMember(legacyRoleByKey(raw.team_roles, 'D'), fallback.team_roles.D),
    },
    skill_modules: skillModuleIds.map((id, index) => normalizeSkillModule(
      legacyModuleById(raw.skill_modules, id, index),
      id,
      fallback.skill_modules[index],
    )),
    result_validation: {
      deliverables: wrapListField(validation.deliverables, fallback.result_validation.deliverables),
      evidence_materials: wrapListField(validation.evidence_materials, fallback.result_validation.evidence_materials),
      test_data: wrapField(validation.test_data, fallback.result_validation.test_data),
      before_after_comparison: wrapField(validation.before_after_comparison, fallback.result_validation.before_after_comparison),
      user_feedback: wrapField(validation.user_feedback, fallback.result_validation.user_feedback),
      quality_evaluation: wrapField(validation.quality_evaluation, fallback.result_validation.quality_evaluation),
    },
    value_innovation: {
      practical_value: wrapField(value.practical_value, fallback.value_innovation.practical_value),
      innovation_points: wrapListField(value.innovation_points, fallback.value_innovation.innovation_points),
      teaching_value: wrapField(value.teaching_value, fallback.value_innovation.teaching_value),
      vocational_scene_value: wrapField(value.vocational_scene_value, fallback.value_innovation.vocational_scene_value),
      sustainability: wrapField(value.sustainability, fallback.value_innovation.sustainability),
    },
    constraints: isObject(raw.constraints) ? {
      avoid: asStringList(raw.constraints.avoid),
      must_show: asStringList(raw.constraints.must_show),
    } : fallback.constraints,
  };
}

export const fieldValue = (field: SpecField | undefined): string => field?.value?.trim() || '';
export const listValue = (field: SpecListField | undefined): string[] => field?.value || [];

const nextStateForPatch = (current: FieldState, source: PatchSource): FieldState => {
  if (source === 'user') return 'locked';
  if (current === 'empty') return 'soft';
  return current;
};

const nextMeta = <T extends SpecField | SpecListField>(field: T, source: PatchSource): T => ({
  ...field,
  state: nextStateForPatch(field.state, source),
  last_modified_by: source,
  updated_at: Date.now(),
});

const skillPathMatch = (path: string) => path.match(/^skill_modules\[(sm_0[1-4])\]\.([a-z_]+)$/);
const teamPathMatch = (path: string) => path.match(/^team_roles\.([ABCD])\.([a-z_]+)$/);

function patchScalar(spec: CompetitionProjectSpec, path: string, value: string, source: PatchSource): void {
  const parts = path.split('.');
  const [section, field] = parts;
  if (section === 'project_positioning' && field in spec.project_positioning) {
    const key = field as keyof CompetitionProjectSpec['project_positioning'];
    spec.project_positioning[key] = { ...nextMeta(spec.project_positioning[key], source), value };
    return;
  }
  if (section === 'problem_definition' && field in spec.problem_definition && !listFieldNames.has(field)) {
    const key = field as keyof Omit<CompetitionProjectSpec['problem_definition'], 'pain_points'>;
    spec.problem_definition[key] = { ...nextMeta(spec.problem_definition[key], source), value };
    return;
  }
  if (section === 'result_validation' && field in spec.result_validation && !listFieldNames.has(field)) {
    const key = field as keyof Omit<CompetitionProjectSpec['result_validation'], 'deliverables' | 'evidence_materials'>;
    spec.result_validation[key] = { ...nextMeta(spec.result_validation[key], source), value };
    return;
  }
  if (section === 'value_innovation' && field in spec.value_innovation && !listFieldNames.has(field)) {
    const key = field as keyof Omit<CompetitionProjectSpec['value_innovation'], 'innovation_points'>;
    spec.value_innovation[key] = { ...nextMeta(spec.value_innovation[key], source), value };
    return;
  }
  const teamMatch = teamPathMatch(path);
  if (teamMatch) {
    const roleKey = teamMatch[1] as RoleKey;
    const fieldKey = teamMatch[2] as keyof TeamMember;
    if (fieldKey in spec.team_roles[roleKey]) {
      spec.team_roles[roleKey][fieldKey] = { ...nextMeta(spec.team_roles[roleKey][fieldKey], source), value };
    }
    return;
  }
  const moduleMatch = skillPathMatch(path);
  if (moduleMatch) {
    const module = spec.skill_modules.find((item) => item.id === moduleMatch[1]);
    const fieldKey = moduleMatch[2] as keyof Omit<SkillModule, 'id'>;
    if (module && fieldKey in module) {
      module[fieldKey] = { ...nextMeta(module[fieldKey], source), value };
    }
  }
}

function resolveListField(spec: CompetitionProjectSpec, path: string): SpecListField | null {
  if (path === 'problem_definition.pain_points') return spec.problem_definition.pain_points;
  if (path === 'result_validation.deliverables') return spec.result_validation.deliverables;
  if (path === 'result_validation.evidence_materials') return spec.result_validation.evidence_materials;
  if (path === 'value_innovation.innovation_points') return spec.value_innovation.innovation_points;
  return null;
}

export function applySpecPatch(currentSpec: CompetitionProjectSpec, op: PatchOp): CompetitionProjectSpec {
  const spec = normalizeSpec(currentSpec);
  if (op.type === 'set') {
    patchScalar(spec, op.path, op.value, op.source);
    return spec;
  }

  const listField = resolveListField(spec, op.path);
  if (!listField) return spec;

  if (op.type === 'append') {
    listField.value = [...listField.value, op.value];
  } else if (op.type === 'remove_at') {
    listField.value = listField.value.filter((_, index) => index !== op.index);
  } else if (op.type === 'set_at') {
    listField.value = listField.value.map((item, index) => index === op.index ? op.value : item);
  }
  const updated = nextMeta(listField, op.source);
  listField.state = updated.state;
  listField.last_modified_by = updated.last_modified_by;
  listField.updated_at = updated.updated_at;
  return spec;
}

export function unlockSpecField(currentSpec: CompetitionProjectSpec, path: string): CompetitionProjectSpec {
  const spec = normalizeSpec(currentSpec);
  const update = (field: SpecField | SpecListField) => {
    field.state = field.value && (Array.isArray(field.value) ? field.value.length > 0 : String(field.value).trim()) ? 'soft' : 'empty';
    field.updated_at = Date.now();
  };
  const listField = resolveListField(spec, path);
  if (listField) {
    update(listField);
    return spec;
  }
  const before = JSON.stringify(spec);
  patchScalar(spec, path, getFieldValueAtPath(spec, path), 'ai');
  const afterPatch = JSON.stringify(spec);
  if (before !== afterPatch) {
    const field = getFieldAtPath(spec, path);
    if (field) update(field);
  }
  return spec;
}

export function getFieldAtPath(spec: CompetitionProjectSpec, path: string): SpecField | SpecListField | null {
  const parts = path.split('.');
  const [section, field] = parts;
  if (section === 'project_positioning' && field in spec.project_positioning) {
    return spec.project_positioning[field as keyof CompetitionProjectSpec['project_positioning']];
  }
  if (section === 'problem_definition' && field in spec.problem_definition) {
    return spec.problem_definition[field as keyof CompetitionProjectSpec['problem_definition']];
  }
  if (section === 'result_validation' && field in spec.result_validation) {
    return spec.result_validation[field as keyof CompetitionProjectSpec['result_validation']];
  }
  if (section === 'value_innovation' && field in spec.value_innovation) {
    return spec.value_innovation[field as keyof CompetitionProjectSpec['value_innovation']];
  }
  const teamMatch = teamPathMatch(path);
  if (teamMatch) {
    const roleKey = teamMatch[1] as RoleKey;
    const fieldKey = teamMatch[2] as keyof TeamMember;
    return spec.team_roles[roleKey][fieldKey] || null;
  }
  const moduleMatch = skillPathMatch(path);
  if (moduleMatch) {
    const module = spec.skill_modules.find((item) => item.id === moduleMatch[1]);
    const fieldKey = moduleMatch[2] as keyof Omit<SkillModule, 'id'>;
    return module?.[fieldKey] || null;
  }
  return null;
}

export function getFieldValueAtPath(spec: CompetitionProjectSpec, path: string): string {
  const field = getFieldAtPath(spec, path);
  if (!field) return '';
  return Array.isArray(field.value) ? field.value.join('；') : field.value;
}
