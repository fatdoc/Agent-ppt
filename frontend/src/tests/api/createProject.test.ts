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
        project_name: '智慧养老守护系统',
        industry_or_track: '人工智能',
        real_scene: '养老院',
        target_user: '老人和护理员',
        team_task_description: '四名学生分别负责评估、护理、记录和成果展示',
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
        project_name: '智慧养老守护系统',
        industry_or_track: '人工智能',
        real_scene: '养老院',
        target_user: '老人和护理员',
        team_task_description: '四名学生分别负责评估、护理、记录和成果展示',
      },
    });
  });
});
