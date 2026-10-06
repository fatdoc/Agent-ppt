import { render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { EditionProvider, useEdition } from './Edition';
import { apiClient } from '../api/client';
import i18n from '../i18n';
vi.mock('../api/client', () => ({ apiClient: { get: vi.fn() }, setAuthEdition: vi.fn() }));
vi.mock('../i18n', () => ({ default: { changeLanguage: vi.fn().mockResolvedValue(undefined) } }));
function Child(){ return <p>{useEdition()}</p>; }
beforeEach(()=>{ vi.clearAllMocks(); });
it('education forces Chinese before displaying pages even with a previous English preference',async()=>{
  vi.mocked(apiClient.get).mockResolvedValue({data:{data:{edition:'education'}}});
  render(<EditionProvider><Child/></EditionProvider>);
  await screen.findByText('education');
  expect(i18n.changeLanguage).toHaveBeenCalledWith('zh'); expect(document.documentElement.lang).toBe('zh-CN');
});
it('general edition keeps its existing language preference',async()=>{
  vi.mocked(apiClient.get).mockResolvedValue({data:{data:{edition:'general'}}});
  render(<EditionProvider><Child/></EditionProvider>);
  await screen.findByText('general'); expect(i18n.changeLanguage).not.toHaveBeenCalled();
});
