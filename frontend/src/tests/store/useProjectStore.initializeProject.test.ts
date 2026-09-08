/**
 * initializeProject 测试 - 验证参考文件在 AI 生成前被关联到项目
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useProjectStore } from '@/store/useProjectStore'

// Track call order to verify files are associated before generation
const callOrder: string[] = []

const mockCreateProject = vi.fn()
const mockGetProject = vi.fn()
const mockAssociateFileToProject = vi.fn()
const mockUploadTemplate = vi.fn()
const mockGenerateFromDescription = vi.fn()
const mockDeleteProject = vi.fn()

vi.mock('@/api/endpoints', () => ({
  createProject: (...args: any[]) => {
    callOrder.push('createProject')
    return mockCreateProject(...args)
  },
  getProject: (...args: any[]) => {
    callOrder.push('getProject')
    return mockGetProject(...args)
  },
  associateFileToProject: (...args: any[]) => {
    callOrder.push('associateFileToProject')
    return mockAssociateFileToProject(...args)
  },
  uploadTemplate: (...args: any[]) => {
    callOrder.push('uploadTemplate')
    return mockUploadTemplate(...args)
  },
  generateFromDescription: (...args: any[]) => {
    callOrder.push('generateFromDescription')
    return mockGenerateFromDescription(...args)
  },
  deleteProject: (...args: any[]) => mockDeleteProject(...args),
  // Other mocks needed by the store
  updatePage: vi.fn(),
  updatePageDescription: vi.fn(),
  updatePageOutline: vi.fn(),
  generateOutline: vi.fn(),
  generateDescriptions: vi.fn(),
  generateImages: vi.fn(),
  getTaskStatus: vi.fn(),
  exportPPTX: vi.fn(),
  exportPDF: vi.fn(),
  getStoredOutputLanguage: vi.fn().mockResolvedValue('zh'),
}))

vi.mock('@/api/auth', () => ({
  refreshCredits: vi.fn(),
}))

vi.mock('@/utils', () => ({
  debounce: (fn: any) => fn,
  normalizeProject: (data: any) => data,
  normalizeErrorMessage: (msg: string) => msg,
}))

describe('initializeProject - reference file association', () => {
  beforeEach(() => {
    callOrder.length = 0
    vi.clearAllMocks()

    // Default mock responses
    mockCreateProject.mockResolvedValue({
      data: { project_id: 'proj-001' }
    })
    mockGetProject.mockResolvedValue({
      data: { id: 'proj-001', status: 'DRAFT', pages: [] }
    })
    mockAssociateFileToProject.mockResolvedValue({
      data: { file: { id: 'file-1', project_id: 'proj-001' } }
    })
    mockUploadTemplate.mockResolvedValue({ data: {} })
    mockGenerateFromDescription.mockResolvedValue({ data: {} })
    mockDeleteProject.mockResolvedValue({ data: {} })

    // Reset store
    const { result } = renderHook(() => useProjectStore())
    act(() => {
      result.current.setCurrentProject(null)
      result.current.setError(null)
      result.current.setGlobalLoading(false)
    })
  })

  it('should pass reference file IDs and associate them after project creation', async () => {
    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'idea',
        'Test idea prompt',
        undefined,
        undefined,
        ['file-1', 'file-2']
      )
    })

    expect(mockAssociateFileToProject).toHaveBeenCalledTimes(2)
    expect(mockAssociateFileToProject).toHaveBeenCalledWith('file-1', 'proj-001')
    expect(mockAssociateFileToProject).toHaveBeenCalledWith('file-2', 'proj-001')
  })

  it('should associate files BEFORE generating from description', async () => {
    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'description',
        'Full description text',
        undefined,
        undefined,
        ['file-1']
      )
    })

    // Verify call order: create → associate → generate
    const createIdx = callOrder.indexOf('createProject')
    const associateIdx = callOrder.indexOf('associateFileToProject')
    const generateIdx = callOrder.indexOf('generateFromDescription')

    expect(createIdx).toBeLessThan(associateIdx)
    expect(associateIdx).toBeLessThan(generateIdx)
  })

  it('should not call associateFileToProject when no file IDs provided', async () => {
    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject('idea', 'Test prompt')
    })

    expect(mockAssociateFileToProject).not.toHaveBeenCalled()
  })

  it('should not call associateFileToProject when empty array provided', async () => {
    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject('idea', 'Test prompt', undefined, undefined, [])
    })

    expect(mockAssociateFileToProject).not.toHaveBeenCalled()
  })

  it('should continue even if file association fails', async () => {
    mockAssociateFileToProject.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'idea',
        'Test prompt',
        undefined,
        undefined,
        ['file-1']
      )
    })

    // Should still complete successfully
    expect(result.current.currentProject).not.toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('should create no-think project and immediately generate outline plus descriptions', async () => {
    const mockGenerateOutline = vi.mocked((await import('@/api/endpoints')).generateOutline)
    mockGenerateOutline.mockResolvedValue({ data: {} })

    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'no_think',
        'AI 工具入门',
        undefined,
        undefined,
        undefined,
        '16:9',
        {
          scenario: '内部培训',
          density: '简洁',
          page_count: '5页',
          style_template: '现代商务',
          extra_instruction: '适合新员工',
        }
      )
    })

    expect(mockCreateProject).toHaveBeenCalledWith(expect.objectContaining({
      creation_type: 'no_think',
      idea_prompt: 'AI 工具入门',
      no_think_options: expect.objectContaining({
        scenario: '内部培训',
        page_count: '5页',
      }),
    }))
    expect(mockGenerateOutline).toHaveBeenCalledWith('proj-001')
  })

  it('should preserve a no-think project when generation times out', async () => {
    const mockGenerateOutline = vi.mocked((await import('@/api/endpoints')).generateOutline)
    mockGenerateOutline.mockRejectedValue(Object.assign(new Error('timeout of 300000ms exceeded'), {
      code: 'ECONNABORTED',
    }))

    const { result } = renderHook(() => useProjectStore())

    await expect(act(async () => {
      await result.current.initializeProject('no_think', 'AI 工具入门')
    })).rejects.toThrow('timeout')

    expect(mockDeleteProject).not.toHaveBeenCalled()
  })

  it('should surface a project 404 instead of leaving the page in permanent loading', async () => {
    mockGetProject.mockRejectedValue({
      response: {
        status: 404,
        data: { error: { message: '项目不存在或无权访问' } },
      },
    })
    localStorage.setItem('currentProjectId', 'missing-project')

    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.syncProject('missing-project')
    })

    expect(result.current.currentProject).toBeNull()
    expect(result.current.error).toBe('项目不存在或无权访问')
    expect(localStorage.getItem('currentProjectId')).toBeNull()
  })

  it('should pass external visual strategy without native template style', async () => {
    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'idea',
        'AI 工具入门',
        undefined,
        undefined,
        undefined,
        '16:9',
        undefined,
        undefined,
        false,
        {
          visual_strategy: 'external_skill',
          external_style_skill_id: 'ppt-style-pro',
          external_style_payload: { style_prompt: '外部 Skill 黑金风格' },
        }
      )
    })

    expect(mockCreateProject).toHaveBeenCalledWith(expect.objectContaining({
      idea_prompt: 'AI 工具入门',
      visual_strategy: 'external_skill',
      external_style_skill_id: 'ppt-style-pro',
      external_style_payload: { style_prompt: '外部 Skill 黑金风格' },
    }))
    expect(mockCreateProject.mock.calls[0][0]).not.toHaveProperty('template_style')
  })

  it('should pass harness generation mode without removing native style controls', async () => {
    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'idea',
        'AI 工具入门',
        undefined,
        '稳重科技风',
        undefined,
        '16:9',
        undefined,
        undefined,
        false,
        { visual_strategy: 'native' },
        {
          generation_mode: 'harness',
          harness_template: 'paper_operators',
        }
      )
    })

    expect(mockCreateProject).toHaveBeenCalledWith(expect.objectContaining({
      idea_prompt: 'AI 工具入门',
      template_style: '稳重科技风',
      visual_strategy: 'native',
      generation_mode: 'harness',
      harness_template: 'paper_operators',
    }))
  })

  it('should create outline-only content projects and generate outline when page descriptions are empty', async () => {
    const mockGenerateOutline = vi.mocked((await import('@/api/endpoints')).generateOutline)
    mockGenerateOutline.mockResolvedValue({ data: {} })

    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'outline',
        '第一页：封面\n第二页：方案',
        undefined,
        undefined,
        undefined,
        '16:9',
        undefined,
        ''
      )
    })

    expect(mockCreateProject).toHaveBeenCalledWith(expect.objectContaining({
      outline_text: '第一页：封面\n第二页：方案',
    }))
    expect(mockGenerateOutline).toHaveBeenCalledWith('proj-001')
    expect(mockGenerateFromDescription).not.toHaveBeenCalled()
  })

  it('should keep required outline and parse optional page descriptions when provided', async () => {
    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'outline',
        '第一页：封面\n第二页：方案',
        undefined,
        undefined,
        undefined,
        '16:9',
        undefined,
        '第一页：封面采用大标题居中\n\n第二页：方案采用三栏布局'
      )
    })

    expect(mockCreateProject).toHaveBeenCalledWith(expect.objectContaining({
      creation_type: 'outline',
      outline_text: '第一页：封面\n第二页：方案',
      description_text: '第一页：封面采用大标题居中\n\n第二页：方案采用三栏布局',
    }))
    expect(mockGenerateFromDescription).toHaveBeenCalledWith(
      'proj-001',
      '第一页：封面采用大标题居中\n\n第二页：方案采用三栏布局'
    )
  })

  it('should associate files before uploading template', async () => {
    const templateFile = new File(['dummy'], 'template.png', { type: 'image/png' })

    const { result } = renderHook(() => useProjectStore())

    await act(async () => {
      await result.current.initializeProject(
        'idea',
        'Test prompt',
        templateFile,
        undefined,
        ['file-1']
      )
    })

    const associateIdx = callOrder.indexOf('associateFileToProject')
    const templateIdx = callOrder.indexOf('uploadTemplate')

    expect(associateIdx).toBeLessThan(templateIdx)
  })
})
