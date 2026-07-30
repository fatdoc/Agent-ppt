export type CompetitionSupportLevel = 'FULL' | 'GENERIC' | 'COMING_SOON';

export interface CompetitionOption {
  id: string;
  name: string;
  enabled?: boolean;
}

export interface ScoreDimension {
  id: string;
  name: string;
  description: string;
  weight?: number;
}

export interface CompetitionConfig {
  id: string;
  name: string;
  shortName: string;
  supportLevel: CompetitionSupportLevel;
  enabled: boolean;
  competitionTypes: CompetitionOption[];
  tracks: CompetitionOption[];
  themes: CompetitionOption[];
  scoreDimensions?: ScoreDimension[];
  recommendedPageCount?: number;
  promptProfileId?: string;
  narrationProfileId?: string;
  outlineTemplateIds?: string[];
  pptTemplateIds?: string[];
  caseLibraryId?: string;
  unsupportedMessage?: string;
}

export interface PlatformProjectContext {
  projectId?: string;
  projectName: string;
  competitionId: string;
  competitionTypeId?: string;
  trackId?: string;
  themeId?: string;
  customTheme?: string;
  targetPageCount: number;
  outlineTemplateId?: string;
  pptTemplateId?: string;
  style: string;
  currentSectionId?: string;
  currentPageId?: string;
  selectedElementId?: string;
  activeScoreDimensionIds: string[];
}

export type OutlineTemplateScope = 'SYSTEM' | 'TEAM' | 'PRIVATE';
export type OutlineTemplateStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export interface OutlineTemplateSection {
  id: string;
  title: string;
  description?: string;
  recommendedPageCount: number;
  pageType?: string;
  purpose?: string;
  scoreDimensions?: string[];
  recommendedSpeaker?: string;
  materialRequirements?: string[];
  generationInstructions?: string;
  children?: OutlineTemplateSection[];
}

export interface OutlineTemplateVersion {
  version: number;
  createdAt: string;
  changeNote?: string;
  sections: OutlineTemplateSection[];
}

export interface OutlineTemplate {
  id: string;
  name: string;
  description?: string;
  competitionId?: string;
  competitionTypeId?: string;
  trackId?: string;
  themeId?: string;
  supportScope: OutlineTemplateScope;
  status: OutlineTemplateStatus;
  version: number;
  targetPageCount?: number;
  styleTags?: string[];
  sections: OutlineTemplateSection[];
  versions?: OutlineTemplateVersion[];
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export type AssetSource =
  | 'UPLOAD'
  | 'AI_GENERATED'
  | 'BACKGROUND_REMOVED'
  | 'SYSTEM'
  | 'TEMPLATE';

export interface ProjectAsset {
  id: string;
  projectId: string;
  type: string;
  name: string;
  url: string;
  thumbnailUrl?: string;
  competitionId?: string;
  trackId?: string;
  themeId?: string;
  source: AssetSource;
  pageId?: string;
  prompt?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

export type DigitalEmployeeInvocationMode = 'MANUAL' | 'WORKFLOW' | 'BOTH';

export interface DigitalEmployeeServiceMapping {
  type: string;
  endpoint?: string;
  handler?: string;
}

export interface DigitalEmployee {
  id: string;
  name: string;
  role: string;
  description: string;
  icon?: string;
  capabilities: string[];
  supportedCompetitions?: string[];
  invocationMode: DigitalEmployeeInvocationMode;
  serviceMapping: DigitalEmployeeServiceMapping[];
  enabled: boolean;
}

export type AgentTaskStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'CANCELLED';

export interface AgentTask {
  id: string;
  workflowId?: string;
  label?: string;
  projectId: string;
  employeeId: string;
  taskType: string;
  status: AgentTaskStatus;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorMessage?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
}

export interface AgentWorkflowStep {
  id: string;
  employeeId: string;
  taskType: string;
  label: string;
}

export interface AgentWorkflow {
  id: string;
  name: string;
  description: string;
  supportedLevels: CompetitionSupportLevel[];
  steps: AgentWorkflowStep[];
}
