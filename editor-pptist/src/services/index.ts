import axios from './axios'
import fetchRequest from './fetch'

// export const SERVER_URL = 'http://localhost:5000'
export const SERVER_URL = (import.meta.env.MODE === 'development') ? '/api' : 'https://server.pptist.cn'

interface ImageSearchPayload {
  query: string;
  orientation?: 'landscape' | 'portrait' | 'square' | 'all';
  locale?: 'zh' | 'en';
  order?: 'popular' | 'latest';
  size?: 'large' | 'medium' | 'small';
  image_type?: 'all' | 'photo' | 'illustration' | 'vector';
  page?: number;
  per_page?: number;
}

interface AIPPTOutlinePayload {
  content: string
  language: string
  provider: string
  model: string
}

interface AIPPTPayload {
  content: string
  language: string
  style: string
  provider: string
  model: string
}

interface AIWritingPayload {
  content: string
  command: string
}

export default {
  getMockData(filename: string): Promise<any> {
    throw new Error('在线素材与 AI 功能尚未接入'); return axios.get(`./mocks/${filename}.json`)
  },

  searchImage(body: ImageSearchPayload): Promise<any> {
    throw new Error('在线素材与 AI 功能尚未接入'); return axios.post(`${SERVER_URL}/tools/img_search`, body)
  },

  AIPPT_Outline({
    content,
    language,
    provider,
    model,
  }: AIPPTOutlinePayload): Promise<any> {
    throw new Error('在线 AI 功能尚未接入'); return fetchRequest(`${SERVER_URL}/tools/aippt_outline`, {
      method: 'POST',
      body: JSON.stringify({
        content,
        language,
        provider,
        model,
        stream: true,
      }),
    })
  },

  AIPPT({
    content,
    language,
    style,
    provider,
    model,
  }: AIPPTPayload): Promise<any> {
    throw new Error('在线 AI 功能尚未接入'); return fetchRequest(`${SERVER_URL}/tools/aippt`, {
      method: 'POST',
      body: JSON.stringify({
        content,
        language,
        provider,
        model,
        style,
        stream: true,
      }),
    })
  },

  AI_Writing({
    content,
    command,
  }: AIWritingPayload): Promise<any> {
    throw new Error('在线 AI 功能尚未接入'); return fetchRequest(`${SERVER_URL}/tools/ai_writing`, {
      method: 'POST',
      body: JSON.stringify({
        content,
        command,
        stream: true,
      }),
    })
  },
}