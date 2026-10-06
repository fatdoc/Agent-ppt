import { describe,it,expect } from 'vitest';
import { message,receive,MAX_BYTES } from '../../../shared/pptistProtocol';
describe('PPTist bridge',()=>{
 const session='session_1234567890';
 const event=(data:unknown,origin=location.origin,source:Window|null=window)=>new MessageEvent('message',{data,origin,source});
 it('binds exact source origin and session',()=>{
  const d=message(session,'READY');
  expect(receive(event(d),window,session,location.origin)).toEqual(d);
  expect(receive(event(d,'https://evil.test'),window,session,location.origin)).toBeNull();
  expect(receive(event(d,location.origin,null),window,session,location.origin)).toBeNull();
  expect(receive(event(d),window,'expired_session_123',location.origin)).toBeNull();
 });
 it('rejects wrong versions payloads types and oversized messages',()=>{
  for(const d of [{...message(session,'READY'),protocol:'v2'},message(session,'LOAD_DOCUMENT'),message(session,'ERROR',{message:'x'.repeat(MAX_BYTES)}),message(session,'DOCUMENT_CHANGED',{slides:[],sequence:-1})]) expect(receive(event(d),window,session,location.origin)).toBeNull();
 });
});
