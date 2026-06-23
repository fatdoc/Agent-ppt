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
        color_tone: '蓝绿色',
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
      image_aspect_ratio: undefined,
      no_think_options: {
        scenario: '内部培训',
        color_tone: '蓝绿色',
        density: '简洁',
        page_count: '5页',
        style_template: '现代商务',
        extra_instruction: '适合新员工',
      },
    });
  });
});
