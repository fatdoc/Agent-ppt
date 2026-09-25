// Versioned same-origin bridge. The iframe is engineering isolation, not a sandbox.
export const PROTOCOL = 'banana-pptist/1' as const;
export const MAX_BYTES = 4 * 1024 * 1024;
export const TYPES = ['READY', 'LOAD_DOCUMENT', 'DOCUMENT_CHANGED', 'SAVE_RESULT', 'REQUEST_EXPORT', 'ERROR'] as const;
export type MessageType = typeof TYPES[number];
export interface EditorMessage { protocol: typeof PROTOCOL; session: string; type: MessageType; payload: Record<string, unknown> }
export function message(session: string, type: MessageType, payload: Record<string, unknown> = {}): EditorMessage {
  return { protocol: PROTOCOL, session, type, payload };
}
export function receive(event: MessageEvent, source: Window | null, session: string, origin: string): EditorMessage | null {
  if (!source || event.source !== source || event.origin !== origin) return null;
  const d = event.data;
  if (!d || typeof d !== 'object' || Array.isArray(d) || d.protocol !== PROTOCOL || d.session !== session || !/^[a-zA-Z0-9_-]{16,100}$/.test(session)) return null;
  if (!TYPES.includes(d.type) || !d.payload || typeof d.payload !== 'object' || Array.isArray(d.payload)) return null;
  if (Object.keys(d).sort().join(',') !== 'payload,protocol,session,type') return null;
  try { if (new TextEncoder().encode(JSON.stringify(d)).byteLength > MAX_BYTES) return null; } catch { return null; }
  const p=d.payload;
  if (d.type === 'LOAD_DOCUMENT' && (!Array.isArray(p.slides) || !p.slides.length || p.slides.length > 100 || typeof p.width !== 'number' || typeof p.height !== 'number' || p.width <= 0 || p.height <= 0)) return null;
  if (d.type === 'DOCUMENT_CHANGED' && (!Array.isArray(p.slides) || !Number.isSafeInteger(p.sequence) || p.sequence < 1)) return null;
  if (d.type === 'SAVE_RESULT' && (typeof p.ok !== 'boolean' || !Number.isSafeInteger(p.sequence))) return null;
  if (d.type === 'ERROR' && typeof p.message !== 'string') return null;
  return d;
}
