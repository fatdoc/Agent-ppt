import { describe, expect, it, vi, beforeEach } from 'vitest';
import { createProject } from '@/api/endpoints';
import { apiClient } from '@/api/client';

vi.mock('@/api/client', () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

describe('createProject API payload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.post).mockResolvedValue({ data: { data: { project_id: 'proj-1' } } });
  });

  it('sends no_think creation type and no_think_options when provided', async () => {
    await createProject({
      creation_type: 'no_think',
      idea_prompt: 'AI 工具入门',
      no_think_options: {
        scenario: '内部培训',
        density: '简洁',
        page_count: '5页',
        style_template: '现代商务',
        extra_instruction: '适合新员工',
      },
    });

    expect(apiClient.post).toHaveBeenCalledWith('/api/projects', {
      creation_type: 'no_think',
      idea_prompt: 'AI 工具入门',
      outline_text: undefined,
      description_text: undefined,
      template_style: undefined,
      generation_mode: undefined,
      harness_template: undefined,
      harness_payload: undefined,
      visual_strategy: undefined,
      external_style_skill_id: undefined,
      external_style_payload: undefined,
      image_aspect_ratio: undefined,
      no_think_options: {
        scenario: '内部培训',
        density: '简洁',
        page_count: '5页',
        style_template: '现代商务',
        extra_instruction: '适合新员工',
      },
    });
  });

  it('sends external visual strategy fields when provided', async () => {
    await createProject({
      creation_type: 'idea',
      idea_prompt: 'AI 工具入门',
      visual_strategy: 'external_skill',
      external_style_skill_id: 'ppt-style-pro',
      external_style_payload: {
        style_prompt: '外部 Skill 黑金风格',
      },
    });

    expect(apiClient.post).toHaveBeenCalledWith('/api/projects', expect.objectContaining({
      creation_type: 'idea',
      idea_prompt: 'AI 工具入门',
      visual_strategy: 'external_skill',
      external_style_skill_id: 'ppt-style-pro',
      external_style_payload: {
        style_prompt: '外部 Skill 黑金风格',
      },
    }));
  });

  it('sends harness generation mode fields when provided', async () => {
    await createProject({
      creation_type: 'idea',
      idea_prompt: 'AI 工具入门',
      template_style: '稳重科技风',
      generation_mode: 'harness',
      harness_template: 'paper_operators',
      visual_strategy: 'native',
    });

    expect(apiClient.post).toHaveBeenCalledWith('/api/projects', expect.objectContaining({
      creation_type: 'idea',
      idea_prompt: 'AI 工具入门',
      template_style: '稳重科技风',
      generation_mode: 'harness',
      harness_template: 'paper_operators',
      visual_strategy: 'native',
    }));
  });
});
