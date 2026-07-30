import type { CompetitionProjectSpec, ModifiedBy, SkillModule, SpecField, SpecListField, TeamMember } from '@/types/spec';

const skillModuleIds = ['sm_01', 'sm_02', 'sm_03', 'sm_04'] as const;

export function emptyField(lastModifiedBy: ModifiedBy = 'ai'): SpecField {
  return { value: '', state: 'empty', last_modified_by: lastModifiedBy, updated_at: Date.now() };
}

export function emptyListField(lastModifiedBy: ModifiedBy = 'ai'): SpecListField {
  return { value: [], state: 'empty', last_modified_by: lastModifiedBy, updated_at: Date.now() };
}

function emptyTeamMember(): TeamMember {
  return {
    role: emptyField(),
    responsibility: emptyField(),
    onsite_action: emptyField(),
    related_skill_modules: emptyField(),
  };
}

function emptySkillModule(id: SkillModule['id']): SkillModule {
  return {
    id,
    skill_name: emptyField(),
    responsible_role: emptyField(),
    work_task: emptyField(),
    onsite_demo_action: emptyField(),
    verification_method: emptyField(),
    expected_evidence: emptyField(),
    tools_or_equipment: emptyField(),
  };
}

export function createEmptySpec(): CompetitionProjectSpec {
  return {
    competition_context: {
      competition_name: '世界职业院校技能大赛/争夺赛',
      generation_goal: '1小时现场技能展示作战稿',
      presentation_mode: '现场展示',
      audience: ['评委', '企业导师', '现场观摩人员'],
    },
    source_material: { raw_text: '', file_id: null, filename: null },
    project_positioning: {
      project_name: emptyField(),
      subtitle: emptyField(),
      track: emptyField(),
      real_scene: emptyField(),
      service_object: emptyField(),
      final_deliverable: emptyField(),
      one_sentence_intro: emptyField(),
    },
    problem_definition: {
      need_source: emptyField(),
      current_method: emptyField(),
      pain_points: emptyListField(),
      problem_consequences: emptyField(),
      project_goal: emptyField(),
    },
    team_roles: {
      A: emptyTeamMember(),
      B: emptyTeamMember(),
      C: emptyTeamMember(),
      D: emptyTeamMember(),
    },
    skill_modules: skillModuleIds.map(emptySkillModule),
    result_validation: {
      deliverables: emptyListField(),
      evidence_materials: emptyListField(),
      test_data: emptyField(),
      before_after_comparison: emptyField(),
      user_feedback: emptyField(),
      quality_evaluation: emptyField(),
    },
    value_innovation: {
      practical_value: emptyField(),
      innovation_points: emptyListField(),
      teaching_value: emptyField(),
      vocational_scene_value: emptyField(),
      sustainability: emptyField(),
    },
    constraints: {
      avoid: ['营销路演', '融资汇报', '泛泛产品介绍', '虚构收益数据'],
      must_show: ['岗位现场', '服务对象', '四名选手动作', '技能模块', '成果证据'],
    },
  };
}
