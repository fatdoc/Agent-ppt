export type FieldState = 'empty' | 'soft' | 'locked';
export type ModifiedBy = 'ai' | 'user';

export interface SpecField<T = string> {
  value: T;
  state: FieldState;
  last_modified_by: ModifiedBy;
  updated_at: number;
}

export interface SpecListField {
  value: string[];
  state: FieldState;
  last_modified_by: ModifiedBy;
  updated_at: number;
}

export interface TeamMember {
  role: SpecField;
  responsibility: SpecField;
  onsite_action: SpecField;
  related_skill_modules: SpecField;
}

export interface SkillModule {
  id: 'sm_01' | 'sm_02' | 'sm_03' | 'sm_04';
  skill_name: SpecField;
  responsible_role: SpecField;
  work_task: SpecField;
  onsite_demo_action: SpecField;
  verification_method: SpecField;
  expected_evidence: SpecField;
  tools_or_equipment: SpecField;
}

export interface CompetitionProjectSpec {
  competition_context?: {
    competition_name: string;
    generation_goal: string;
    presentation_mode: string;
    audience: string[];
  };
  source_material?: {
    raw_text?: string;
    file_id?: string | null;
    filename?: string | null;
  };
  project_positioning: {
    project_name: SpecField;
    subtitle: SpecField;
    track: SpecField;
    real_scene: SpecField;
    service_object: SpecField;
    final_deliverable: SpecField;
    one_sentence_intro: SpecField;
  };
  problem_definition: {
    need_source: SpecField;
    current_method: SpecField;
    pain_points: SpecListField;
    problem_consequences: SpecField;
    project_goal: SpecField;
  };
  team_roles: {
    A: TeamMember;
    B: TeamMember;
    C: TeamMember;
    D: TeamMember;
  };
  skill_modules: SkillModule[];
  result_validation: {
    deliverables: SpecListField;
    evidence_materials: SpecListField;
    test_data: SpecField;
    before_after_comparison: SpecField;
    user_feedback: SpecField;
    quality_evaluation: SpecField;
  };
  value_innovation: {
    practical_value: SpecField;
    innovation_points: SpecListField;
    teaching_value: SpecField;
    vocational_scene_value: SpecField;
    sustainability: SpecField;
  };
  constraints?: {
    avoid?: string[];
    must_show?: string[];
  };
}
